"""Position risk: trailing stop distance and unrealized P/L.

The trailing-stop math has tests (per spec guardrail: "Money/position logic
requires tests.") and takes quotes as plain mappings so it's trivial to unit
test without any network dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass
class Holding:
    ticker: str
    shares: float
    cost_basis: float
    trailing_stop: float


@dataclass
class PositionStatus:
    ticker: str
    shares: float
    cost_basis: float
    trailing_stop: float
    last: float | None
    unrealized_pl: float | None
    unrealized_pct: float | None
    stop_distance_pct: float | None  # (last - stop) / last * 100, None if no price
    stop_warning: bool


def load_holdings(raw: list[dict]) -> list[Holding]:
    return [
        Holding(
            ticker=item["ticker"].upper(),
            shares=float(item["shares"]),
            cost_basis=float(item["cost_basis"]),
            trailing_stop=float(item["trailing_stop"]),
        )
        for item in raw
    ]


def evaluate(
    holdings: list[Holding],
    last_prices: Mapping[str, float],
    *,
    warning_pct: float = 2.0,
) -> list[PositionStatus]:
    out: list[PositionStatus] = []
    for h in holdings:
        last = last_prices.get(h.ticker)
        if last is None:
            out.append(
                PositionStatus(
                    ticker=h.ticker,
                    shares=h.shares,
                    cost_basis=h.cost_basis,
                    trailing_stop=h.trailing_stop,
                    last=None,
                    unrealized_pl=None,
                    unrealized_pct=None,
                    stop_distance_pct=None,
                    stop_warning=False,
                )
            )
            continue
        pl = (last - h.cost_basis) * h.shares
        pl_pct = (last / h.cost_basis - 1.0) * 100.0 if h.cost_basis else None
        stop_dist = (last - h.trailing_stop) / last * 100.0 if last else None
        warn = stop_dist is not None and stop_dist <= warning_pct
        out.append(
            PositionStatus(
                ticker=h.ticker,
                shares=h.shares,
                cost_basis=h.cost_basis,
                trailing_stop=h.trailing_stop,
                last=last,
                unrealized_pl=pl,
                unrealized_pct=pl_pct,
                stop_distance_pct=stop_dist,
                stop_warning=warn,
            )
        )
    return out
