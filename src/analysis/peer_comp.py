"""Peer board ranking + formatting helpers."""
from __future__ import annotations

import pandas as pd


def rank_by_one_day(board: pd.DataFrame) -> pd.DataFrame:
    if board.empty or "one_day_pct" not in board.columns:
        return board
    return board.sort_values("one_day_pct", ascending=False, na_position="last")


def flag_movers(board: pd.DataFrame, threshold_pct: float) -> list[str]:
    if board.empty or "one_day_pct" not in board.columns:
        return []
    return [
        t
        for t, row in board.iterrows()
        if row["one_day_pct"] is not None
        and not pd.isna(row["one_day_pct"])
        and abs(row["one_day_pct"]) >= threshold_pct
    ]
