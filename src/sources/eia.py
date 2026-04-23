"""EIA v2 API client for weekly petroleum status and SPR.

Exposes small, typed fetch functions. Each returns a pandas DataFrame with a
`period` column (datetime) and one or more value columns. Raw JSON responses are
cached to ``data/raw/eia_<series>_<YYYYMMDD>.json`` for replay/debug.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.eia.gov/v2"
RAW_DIR = Path("data/raw")


@dataclass
class EIAClient:
    api_key: str
    session: requests.Session | None = None
    timeout: float = 20.0

    def __post_init__(self) -> None:
        self.session = self.session or requests.Session()

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "api_key": self.api_key}
        url = f"{BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


def _cache_raw(series_key: str, payload: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat().replace("-", "")
    path = RAW_DIR / f"eia_{series_key}_{stamp}.json"
    path.write_text(json.dumps(payload))


def _rows_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    data = payload.get("response", {}).get("data", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if "period" in df.columns:
        df["period"] = pd.to_datetime(df["period"])
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def fetch_weekly_crude_stocks(client: EIAClient, *, limit: int = 8) -> pd.DataFrame:
    """Weekly US commercial crude oil stocks, most recent `limit` weeks."""
    payload = client.get(
        "/petroleum/stoc/wstk/data/",
        params={
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "WCESTUS1",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": limit,
        },
    )
    _cache_raw("crude_stocks", payload)
    return _rows_to_frame(payload)


def fetch_spr_level(client: EIAClient, *, limit: int = 8) -> pd.DataFrame:
    """Weekly Strategic Petroleum Reserve level, most recent `limit` weeks."""
    payload = client.get(
        "/petroleum/stoc/wstk/data/",
        params={
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "WCSSTUS1",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": limit,
        },
    )
    _cache_raw("spr", payload)
    return _rows_to_frame(payload)


def fetch_cushing_stocks(client: EIAClient, *, limit: int = 8) -> pd.DataFrame:
    """Weekly Cushing, OK crude oil stocks."""
    payload = client.get(
        "/petroleum/stoc/wstk/data/",
        params={
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "W_EPC0_SAX_YCUOK_MBBL",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": limit,
        },
    )
    _cache_raw("cushing", payload)
    return _rows_to_frame(payload)


def fetch_permian_production(client: EIAClient, *, limit: int = 12) -> pd.DataFrame:
    """Monthly Permian region crude oil production from the Drilling Productivity Report."""
    payload = client.get(
        "/petroleum/crd/drpdp/data/",
        params={
            "frequency": "monthly",
            "data[0]": "value",
            "facets[region][]": "Permian Region",
            "facets[seriesId][]": "COPR",  # Crude Oil Production
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": limit,
        },
    )
    _cache_raw("permian_prod", payload)
    return _rows_to_frame(payload)


def load_client_from_env() -> EIAClient | None:
    key = os.environ.get("EIA_API_KEY")
    if not key:
        logger.warning("EIA_API_KEY not set; EIA source disabled")
        return None
    return EIAClient(api_key=key)
