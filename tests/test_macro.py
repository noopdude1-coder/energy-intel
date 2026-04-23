"""Tests for the macro (FRED) snapshot."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.sources import macro


class StubFred:
    def __init__(self, series_map: dict[str, pd.Series]):
        self.series_map = series_map

    def get_series(self, series_id: str) -> pd.Series:
        if series_id not in self.series_map:
            raise KeyError(series_id)
        return self.series_map[series_id]


def _series(values, start="2026-04-15"):
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_fetch_snapshot_pulls_all_series():
    client = StubFred(
        {
            macro.SERIES["wti"]: _series([78.5, 79.2, 80.1]),
            macro.SERIES["brent"]: _series([82.0, 83.5, 84.0]),
            macro.SERIES["hh_gas"]: _series([2.1, 2.2, 2.3]),
            macro.SERIES["dxy"]: _series([104.0, 104.5, 105.0]),
            macro.SERIES["ten_year"]: _series([4.1, 4.2, 4.25]),
        }
    )
    snap = macro.fetch_snapshot(client)
    assert snap.get("wti") == 80.1
    assert snap.get("brent") == 84.0
    assert snap.get("ten_year") == 4.25
    assert isinstance(snap.as_of["wti"], type(datetime(2026, 1, 1).date()))


def test_fetch_snapshot_tolerates_partial_failure():
    bad_series_map = {macro.SERIES["wti"]: _series([80.0])}
    # Missing Brent/HH etc — StubFred raises KeyError; fetch_snapshot must catch.
    snap = macro.fetch_snapshot(StubFred(bad_series_map))
    assert snap.get("wti") == 80.0
    assert snap.get("brent") is None


def test_no_client_returns_empty_snapshot(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    snap = macro.fetch_snapshot(client=None)
    assert snap.values == {}
    assert snap.as_of == {}
