"""Fixture-based tests for the EIA source. No live HTTP."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.sources import eia

FIXTURES = Path(__file__).parent / "fixtures"


class StubClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, path, params):
        self.calls.append((path, params))
        return self.payload


def test_fetch_weekly_crude_stocks_parses_fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = json.loads((FIXTURES / "eia_crude_stocks.json").read_text())
    client = StubClient(payload)

    df = eia.fetch_weekly_crude_stocks(client)

    assert not df.empty
    assert {"period", "value"}.issubset(df.columns)
    assert df["period"].dtype.kind == "M"  # datetime
    assert pd.api.types.is_numeric_dtype(df["value"])
    assert df.iloc[0]["value"] == 456789


def test_fetch_spr_level_caches_raw(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = json.loads((FIXTURES / "eia_spr.json").read_text())
    client = StubClient(payload)

    df = eia.fetch_spr_level(client)

    assert not df.empty
    cached = list((tmp_path / "data" / "raw").glob("eia_spr_*.json"))
    assert cached, "expected cached raw payload"


def test_empty_payload_returns_empty_frame():
    df = eia._rows_to_frame({"response": {"data": []}})
    assert df.empty


def test_load_client_from_env_missing(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    assert eia.load_client_from_env() is None
