from __future__ import annotations

import pandas as pd

from src.analysis import signals


def test_brent_wti_spread_wide():
    sig = signals.brent_wti_spread(90.0, 80.0, hi=6.0, lo=2.0)
    assert sig is not None
    assert "wide" in sig.name.lower()


def test_brent_wti_spread_tight():
    sig = signals.brent_wti_spread(82.0, 80.5, hi=6.0, lo=2.0)
    assert sig is not None
    assert "tight" in sig.name.lower()


def test_brent_wti_spread_neutral():
    sig = signals.brent_wti_spread(84.0, 80.0, hi=6.0, lo=2.0)
    assert sig is None


def test_brent_wti_spread_handles_none():
    assert signals.brent_wti_spread(None, 80.0, hi=6.0, lo=2.0) is None
    assert signals.brent_wti_spread(84.0, None, hi=6.0, lo=2.0) is None


def test_relative_strength_break_triggers():
    board = pd.DataFrame(
        {"five_day_pct": [5.0, 1.0]},
        index=["PR", "FANG"],
    )
    sig = signals.relative_strength_break(board, a="PR", b="FANG", threshold_pct=3.0)
    assert sig is not None
    assert "outperformed" in sig.name


def test_relative_strength_break_no_trigger():
    board = pd.DataFrame(
        {"five_day_pct": [2.0, 1.0]},
        index=["PR", "FANG"],
    )
    assert signals.relative_strength_break(board, a="PR", b="FANG", threshold_pct=3.0) is None
