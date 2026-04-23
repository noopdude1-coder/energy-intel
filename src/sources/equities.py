"""Equity price fetcher via yfinance.

Returns a DataFrame indexed by ticker with last, 1D%, 5D%, YTD%, and 52-week
range position. Designed to degrade gracefully: a single bad ticker doesn't
poison the batch.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol

import pandas as pd

logger = logging.getLogger(__name__)


class PriceHistoryFetcher(Protocol):
    def __call__(self, tickers: list[str], period: str) -> pd.DataFrame: ...


def _yf_fetch(tickers: list[str], period: str) -> pd.DataFrame:
    import yfinance as yf  # deferred import so tests don't require it

    df = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    return df


def _pct(curr: float, prev: float) -> float | None:
    if prev is None or prev == 0 or pd.isna(prev) or pd.isna(curr):
        return None
    return float((curr / prev - 1.0) * 100.0)


def _extract_close_series(raw: pd.DataFrame, ticker: str) -> pd.Series:
    """Pull a clean Close series for `ticker` out of yfinance's multi-index frame."""
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(0):
            return raw[ticker]["Close"].dropna()
        if ticker in raw.columns.get_level_values(1):
            return raw.xs(ticker, axis=1, level=1)["Close"].dropna()
        return pd.Series(dtype=float)
    return raw["Close"].dropna() if "Close" in raw.columns else pd.Series(dtype=float)


def build_peer_board(
    tickers: Iterable[str],
    *,
    fetcher: PriceHistoryFetcher = _yf_fetch,
    today: datetime | None = None,
) -> pd.DataFrame:
    """Return a DataFrame indexed by ticker with summary columns.

    Columns: last, one_day_pct, five_day_pct, ytd_pct, range_52w_pct, low_52w, high_52w.
    ``range_52w_pct`` is where `last` sits within the 52w range (0.0 = low, 1.0 = high).
    """
    tickers = list(tickers)
    if not tickers:
        return pd.DataFrame()

    today = today or datetime.utcnow()
    year_start = datetime(today.year, 1, 1)

    try:
        raw = fetcher(tickers, "1y")
    except Exception as exc:  # noqa: BLE001
        logger.warning("equities fetch failed: %s", exc)
        return pd.DataFrame()

    rows: list[dict] = []
    for t in tickers:
        closes = _extract_close_series(raw, t)
        if closes.empty:
            logger.info("no data for %s", t)
            continue
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
        five_back = float(closes.iloc[-6]) if len(closes) >= 6 else None
        ytd_slice = closes[closes.index >= year_start]
        ytd_start = float(ytd_slice.iloc[0]) if not ytd_slice.empty else None
        low_52 = float(closes.min())
        high_52 = float(closes.max())
        rng = (last - low_52) / (high_52 - low_52) if high_52 > low_52 else None
        rows.append(
            {
                "ticker": t,
                "last": last,
                "one_day_pct": _pct(last, prev) if prev is not None else None,
                "five_day_pct": _pct(last, five_back) if five_back is not None else None,
                "ytd_pct": _pct(last, ytd_start) if ytd_start is not None else None,
                "low_52w": low_52,
                "high_52w": high_52,
                "range_52w_pct": rng,
            }
        )
    return pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame()


@dataclass
class Quote:
    ticker: str
    last: float
    one_day_pct: float | None


def quotes_from_board(board: pd.DataFrame) -> dict[str, Quote]:
    if board.empty:
        return {}
    return {
        t: Quote(ticker=t, last=row["last"], one_day_pct=row.get("one_day_pct"))
        for t, row in board.iterrows()
    }
