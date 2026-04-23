"""Baker Hughes weekly North America rig count.

The `/static-files/<UUID>` URLs that host the weekly XLSB/PDF are re-minted
every Friday, so we scrape the stable landing page at
``https://rigcount.bakerhughes.com/na-rig-count`` and read the tables that the
page renders server-side.

Two tables matter:
- US summary: has Oil / Gas / Total rows with current-week and WoW/YoY deltas.
- Major Basin Variances: one row per basin (Permian, DJ-Niobrara, Eagle Ford…)
  with current count and WoW/YoY deltas.

The WAF blocks default ``python-requests`` user-agents, so we set a realistic
browser UA. The scraper returns ``None`` on any failure — the brief degrades
gracefully with a "source unavailable" marker.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LANDING_URL = "https://rigcount.bakerhughes.com/na-rig-count"
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
RAW_DIR = Path("data/raw")


@dataclass
class RigCountSnapshot:
    as_of: date
    total_us: int
    permian: int
    permian_wow: int | None
    permian_yoy: int | None


class HtmlFetcher(Protocol):
    def __call__(self, url: str) -> str: ...


def _default_fetch(url: str) -> str:
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    session = requests.Session()
    session.headers.update(headers)
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


def _cache_raw_html(html: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat().replace("-", "")
    (RAW_DIR / f"baker_hughes_{stamp}.html").write_text(html)


def _parse_int(text: str) -> int | None:
    if text is None:
        return None
    cleaned = re.sub(r"[^\d\-]", "", text.strip())
    if cleaned in ("", "-"):
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _parse_date(text: str) -> date | None:
    """Find the first date-like substring in `text` and parse it."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})[\s/\-]+([A-Za-z]+|\d{1,2})[\s/\-,]+(\d{2,4})", text)
    if m:
        try:
            from dateutil import parser

            return parser.parse(m.group(0)).date()
        except Exception:  # noqa: BLE001
            return None
    m2 = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if m2:
        try:
            from dateutil import parser

            return parser.parse(m2.group(0)).date()
        except Exception:  # noqa: BLE001
            return None
    return None


def _find_us_total(soup: BeautifulSoup) -> int | None:
    """Locate the US total rig count.

    Heuristic: a table is the US summary if it has both an 'Oil' or 'Gas' row
    (whether in headers or as a row label) AND a 'Total' row. Return the first
    numeric cell from the Total row.
    """
    for table in soup.find_all("table"):
        row_labels: list[str] = []
        total_cells: list[str] | None = None
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            label = cells[0].get_text(" ", strip=True).lower()
            row_labels.append(label)
            if label == "total" or label.startswith("total"):
                total_cells = [c.get_text() for c in cells[1:]]
        has_oil_or_gas = any(lbl in ("oil", "gas") for lbl in row_labels)
        if total_cells and has_oil_or_gas:
            for raw in total_cells:
                val = _parse_int(raw)
                if val is not None:
                    return val
    return None


def _find_basin_row(soup: BeautifulSoup, basin: str) -> list[int | None] | None:
    """Return numeric cells from the row whose first cell equals `basin`."""
    target = basin.lower()
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            label = cells[0].get_text(" ", strip=True).lower()
            if label == target:
                return [_parse_int(c.get_text()) for c in cells[1:]]
    return None


def _find_as_of_date(soup: BeautifulSoup) -> date | None:
    """Look for 'Week ending' / 'as of' style strings anywhere on the page."""
    for pattern in (r"Week ending[^<\n]{0,40}", r"As of[^<\n]{0,40}"):
        match = re.search(pattern, soup.get_text(" "), re.IGNORECASE)
        if match:
            parsed = _parse_date(match.group(0))
            if parsed:
                return parsed
    return None


def parse_snapshot(html: str, *, today: date | None = None) -> RigCountSnapshot | None:
    """Parse the landing-page HTML into a snapshot. Returns None if parsing fails."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:  # noqa: BLE001
        soup = BeautifulSoup(html, "html.parser")

    total_us = _find_us_total(soup)
    permian_cells = _find_basin_row(soup, "Permian")

    if total_us is None or not permian_cells:
        logger.warning("baker_hughes: could not locate required cells in HTML")
        return None

    permian = permian_cells[0]
    if permian is None:
        logger.warning("baker_hughes: Permian row parsed but count cell missing")
        return None

    permian_wow = permian_cells[1] if len(permian_cells) > 1 else None
    permian_yoy = permian_cells[2] if len(permian_cells) > 2 else None

    as_of = _find_as_of_date(soup) or (today or date.today())

    return RigCountSnapshot(
        as_of=as_of,
        total_us=total_us,
        permian=permian,
        permian_wow=permian_wow,
        permian_yoy=permian_yoy,
    )


def fetch_latest(fetcher: HtmlFetcher = _default_fetch) -> RigCountSnapshot | None:
    try:
        html = fetcher(LANDING_URL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("baker_hughes fetch failed: %s", exc)
        return None
    try:
        _cache_raw_html(html)
    except Exception as exc:  # noqa: BLE001
        logger.debug("baker_hughes raw-cache write failed: %s", exc)
    return parse_snapshot(html)
