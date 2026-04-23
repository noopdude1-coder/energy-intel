"""Tests for the equities peer-board builder using a stub fetcher."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.sources import equities


def _build_raw(tickers: list[str], today: datetime) -> pd.DataFrame:
    idx = pd.date_range(end=today, periods=260, freq="B")
    frames = {}
    rng = np.random.default_rng(42)
    for i, t in enumerate(tickers):
        base = 100.0 + i * 10.0
        walk = rng.normal(loc=0.001 * (i + 1), scale=0.01, size=len(idx)).cumsum()
        close = base * (1.0 + walk)
        frames[t] = pd.DataFrame({"Close": close}, index=idx)
    return pd.concat(frames, axis=1)


def test_peer_board_shape_and_columns():
    today = datetime(2026, 4, 22)
    tickers = ["PR", "FANG", "XOM"]

    def fetcher(t, period):
        return _build_raw(t, today)

    board = equities.build_peer_board(tickers, fetcher=fetcher, today=today)

    assert set(board.index) == set(tickers)
    for col in ("last", "one_day_pct", "five_day_pct", "ytd_pct", "range_52w_pct"):
        assert col in board.columns

    for t in tickers:
        assert board.loc[t, "last"] > 0
        assert 0.0 <= board.loc[t, "range_52w_pct"] <= 1.0


def test_empty_tickers_returns_empty():
    board = equities.build_peer_board([])
    assert board.empty


def test_fetch_failure_returns_empty(caplog):
    def boom(t, period):
        raise RuntimeError("network dead")

    board = equities.build_peer_board(["PR"], fetcher=boom)
    assert board.empty
