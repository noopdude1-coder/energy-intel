"""SEC EDGAR XBRL company-facts client.

Uses the free ``data.sec.gov/api/xbrl/companyfacts/CIK##########.json`` endpoint
— no key, but the SEC requires a descriptive ``User-Agent`` header.

The companyfacts payload is a nested dict of the form::

    {
      "cik": 1658566,
      "entityName": "Permian Resources Corp",
      "facts": {
        "us-gaap": {
          "NetCashProvidedByOperatingActivities": {
            "label": "...",
            "units": {
              "USD": [
                {"end": "2024-12-31", "val": 2500000000, "fy": 2024, "fp": "FY",
                 "form": "10-K", "filed": "2025-02-15", "frame": "CY2024"}
              ]
            }
          },
          ...
        }
      }
    }

We expose:
- ``fetch_company_facts(cik)`` → raw dict
- ``latest_fact(payload, tag, unit)`` → most recent value for a tag
- ``latest_annual(payload, tag, unit)`` → latest FY value
- ``ttm_sum(payload, tag, unit)`` → trailing 12 months sum for quarterly flow tags

Designed so every helper is a pure function over the payload — tests pass
canned JSON and never hit the network.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Protocol

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://data.sec.gov"
RAW_DIR = Path("data/raw")

# SEC requires a descriptive User-Agent. Override via the SEC_USER_AGENT
# env var (set as a GitHub Actions variable for CI). We treat an empty
# env value the same as missing — GitHub injects "" when the variable is
# undefined, which would otherwise become the literal UA and 403.
_FALLBACK_UA = "energy-intel github.com/noopdude1-coder/energy-intel admin@energy-intel.example"
_ENV_UA = os.environ.get("SEC_USER_AGENT", "").strip()
DEFAULT_UA = _ENV_UA or _FALLBACK_UA


class HttpGetter(Protocol):
    def __call__(self, url: str, headers: dict) -> requests.Response: ...


def _default_getter(url: str, headers: dict) -> requests.Response:
    return requests.get(url, headers=headers, timeout=20)


@dataclass
class SECClient:
    user_agent: str = DEFAULT_UA
    getter: HttpGetter = _default_getter

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def company_facts(self, cik: str) -> dict[str, Any]:
        cik10 = _normalize_cik(cik)
        url = f"{BASE_URL}/api/xbrl/companyfacts/CIK{cik10}.json"
        resp = self.getter(url, self._headers())
        resp.raise_for_status()
        return resp.json()


def _normalize_cik(cik: str | int) -> str:
    raw = str(cik).lstrip("CIK").strip()
    return raw.zfill(10)


def _cache_raw(cik: str, payload: dict) -> None:
    try:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        stamp = date.today().isoformat().replace("-", "")
        path = RAW_DIR / f"sec_{_normalize_cik(cik)}_{stamp}.json"
        path.write_text(json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        logger.debug("sec raw-cache failed: %s", exc)


def fetch_company_facts(cik: str, *, client: SECClient | None = None) -> dict[str, Any] | None:
    client = client or SECClient()
    try:
        payload = client.company_facts(cik)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SEC company_facts failed for %s: %s", cik, exc)
        return None
    _cache_raw(cik, payload)
    return payload


def _tag_units(payload: dict, tag: str, taxonomy: str = "us-gaap") -> dict | None:
    facts = payload.get("facts", {}).get(taxonomy, {})
    entry = facts.get(tag)
    if not entry:
        return None
    return entry.get("units", {})


def _iter_tag_values(
    payload: dict,
    tag: str,
    *,
    unit: str = "USD",
    taxonomy: str = "us-gaap",
) -> list[dict]:
    units = _tag_units(payload, tag, taxonomy)
    if not units:
        return []
    return list(units.get(unit, []))


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def latest_fact(
    payload: dict,
    tag: str,
    *,
    unit: str = "USD",
    taxonomy: str = "us-gaap",
    form: str | None = None,
) -> dict | None:
    """Return the most recently-filed entry for `tag`.

    If `form` is "10-K" or "10-Q", restrict to that filing type.
    Sort key is (end-date, filed-date) so a restatement wins over the original.
    """
    values = _iter_tag_values(payload, tag, unit=unit, taxonomy=taxonomy)
    if form is not None:
        values = [v for v in values if v.get("form") == form]
    if not values:
        return None
    values.sort(
        key=lambda v: (_parse_date(v.get("end")) or date.min, _parse_date(v.get("filed")) or date.min),
        reverse=True,
    )
    return values[0]


def latest_annual(payload: dict, tag: str, *, unit: str = "USD", taxonomy: str = "us-gaap") -> dict | None:
    """Latest full-year entry (fp='FY' or form='10-K')."""
    values = [
        v
        for v in _iter_tag_values(payload, tag, unit=unit, taxonomy=taxonomy)
        if v.get("fp") == "FY" or v.get("form") == "10-K"
    ]
    if not values:
        return None
    values.sort(key=lambda v: _parse_date(v.get("end")) or date.min, reverse=True)
    return values[0]


def ttm_sum(
    payload: dict,
    tag: str,
    *,
    unit: str = "USD",
    taxonomy: str = "us-gaap",
) -> tuple[float, date] | None:
    """Trailing-12-month sum for a flow tag (revenue, CapEx, OCF…).

    Strategy: if the latest annual (10-K) value is at least as recent as the
    latest quarterly (10-Q) value, return the annual directly. Otherwise sum
    the four most recent distinct-period quarterly entries.
    """
    values = _iter_tag_values(payload, tag, unit=unit, taxonomy=taxonomy)
    if not values:
        return None

    annual = [v for v in values if v.get("form") == "10-K"]
    annual.sort(key=lambda v: _parse_date(v.get("end")) or date.min, reverse=True)
    quarterly = [v for v in values if v.get("form") == "10-Q"]
    quarterly.sort(key=lambda v: _parse_date(v.get("end")) or date.min, reverse=True)

    latest_10k_end = _parse_date(annual[0].get("end")) if annual else None
    latest_10q_end = _parse_date(quarterly[0].get("end")) if quarterly else None

    if latest_10k_end and (not latest_10q_end or latest_10k_end >= latest_10q_end):
        return float(annual[0]["val"]), latest_10k_end

    if not quarterly:
        return None

    def is_quarterly_period(v: dict) -> bool:
        start = _parse_date(v.get("start"))
        end = _parse_date(v.get("end"))
        if not start or not end:
            return False
        delta = (end - start).days
        return 80 <= delta <= 100

    q_periods = [v for v in values if is_quarterly_period(v)]
    q_periods.sort(key=lambda v: _parse_date(v.get("end")) or date.min, reverse=True)
    seen: set[date] = set()
    unique: list[dict] = []
    for v in q_periods:
        e = _parse_date(v.get("end"))
        if e in seen or e is None:
            continue
        seen.add(e)
        unique.append(v)

    if len(unique) < 4:
        return None

    trailing_four = unique[:4]
    total = sum(float(v["val"]) for v in trailing_four)
    return total, (_parse_date(trailing_four[0].get("end")) or date.today())


def first_matching_tag(
    payload: dict,
    candidates: Iterable[str],
    *,
    taxonomy: str = "us-gaap",
) -> str | None:
    """Return the first tag in `candidates` that has any USD unit data.

    GAAP tag usage shifts across filers (e.g. ``PaymentsToAcquirePropertyPlantAndEquipment``
    vs. ``CapitalExpenditures``) so most metric computations try a prioritized list.
    """
    facts = payload.get("facts", {}).get(taxonomy, {})
    for tag in candidates:
        if tag in facts:
            return tag
    return None


def load_peer_ciks(config_path: Path) -> dict[str, str]:
    import yaml

    raw = yaml.safe_load(config_path.read_text()) or {}
    return {k.upper(): _normalize_cik(v) for k, v in (raw.get("ciks") or {}).items()}
