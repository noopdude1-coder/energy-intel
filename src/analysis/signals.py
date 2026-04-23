"""Rule-based signal flags.

Intentionally simple — each signal is a small pure function returning an
optional ``Signal`` so the brief can list whatever fired today.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    name: str
    detail: str


def brent_wti_spread(
    brent: float | None,
    wti: float | None,
    *,
    hi: float,
    lo: float,
) -> Signal | None:
    if brent is None or wti is None:
        return None
    spread = brent - wti
    if spread >= hi:
        return Signal(
            name="Brent-WTI spread wide",
            detail=f"${spread:.2f}/bbl (≥ ${hi:.2f}); favors US export economics",
        )
    if spread <= lo:
        return Signal(
            name="Brent-WTI spread tight",
            detail=f"${spread:.2f}/bbl (≤ ${lo:.2f}); US export arb compressed",
        )
    return None


def relative_strength_break(
    board: pd.DataFrame,
    *,
    a: str,
    b: str,
    window_days: int = 5,
    threshold_pct: float = 3.0,
) -> Signal | None:
    """Flag when `a` outperforms/underperforms `b` by >threshold over the window."""
    col = "five_day_pct"
    if board.empty or col not in board.columns:
        return None
    if a not in board.index or b not in board.index:
        return None
    a_move = board.loc[a, col]
    b_move = board.loc[b, col]
    if pd.isna(a_move) or pd.isna(b_move):
        return None
    diff = a_move - b_move
    if abs(diff) < threshold_pct:
        return None
    direction = "outperformed" if diff > 0 else "underperformed"
    return Signal(
        name=f"{a} vs {b} {direction}",
        detail=f"{a} {a_move:+.2f}% vs {b} {b_move:+.2f}% over {window_days}D ({diff:+.2f}pp)",
    )
