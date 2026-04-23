"""FRED macro series: DXY, 10Y, WTI spot, Henry Hub spot.

Returns a dict of ``{name: (latest_value, as_of_date)}`` so the brief can
display a one-line header without extra munging.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

logger = logging.getLogger(__name__)

SERIES = {
    "wti": "DCOILWTICO",      # WTI spot, $/bbl
    "brent": "DCOILBRENTEU",  # Brent spot, $/bbl
    "hh_gas": "DHHNGSP",      # Henry Hub spot, $/MMBtu
    "dxy": "DTWEXBGS",        # Broad trade-weighted USD (proxy for DXY)
    "ten_year": "DGS10",      # 10Y Treasury yield, %
}


class FredLike(Protocol):
    def get_series(self, series_id: str) -> pd.Series: ...


@dataclass
class MacroSnapshot:
    values: dict[str, float]
    as_of: dict[str, date]

    def get(self, name: str) -> float | None:
        return self.values.get(name)


def _load_fred() -> FredLike | None:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        logger.warning("FRED_API_KEY not set; macro source disabled")
        return None
    from fredapi import Fred  # deferred import

    return Fred(api_key=key)


def fetch_snapshot(client: FredLike | None = None) -> MacroSnapshot:
    client = client or _load_fred()
    values: dict[str, float] = {}
    as_of: dict[str, date] = {}
    if client is None:
        return MacroSnapshot(values=values, as_of=as_of)

    for name, series_id in SERIES.items():
        try:
            series = client.get_series(series_id).dropna()
        except Exception as exc:  # noqa: BLE001
            logger.warning("FRED fetch failed for %s: %s", name, exc)
            continue
        if series.empty:
            continue
        values[name] = float(series.iloc[-1])
        last_idx = series.index[-1]
        as_of[name] = last_idx.date() if hasattr(last_idx, "date") else last_idx
    return MacroSnapshot(values=values, as_of=as_of)
