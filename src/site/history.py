"""Time-series loaders for the dashboard.

Macro: fetch rolling-window FRED series at build time. FRED gives full history
free, so there's no need to persist snapshots — a fresh build always produces
up-to-date charts.

SPR / Permian production: fetch from EIA when the key is available.

Peer history: read the parquet accumulated by ``src.peer_report``.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.sources import eia as eia_source
from src.sources import macro as macro_source

logger = logging.getLogger(__name__)

PEER_HISTORY_PATH = Path("data/peer_history.parquet")


@dataclass
class ChartSpec:
    id: str
    title: str
    label: str
    y_label: str
    color: str
    points: list[dict[str, Any]]
    subtitle: str | None = None
    time_unit: str = "month"


def _fred_window(client, series_id: str, *, days: int) -> list[dict[str, Any]]:
    """Fetch a FRED series, trimmed to the most recent `days`, as chart points."""
    try:
        series = client.get_series(series_id).dropna()
    except Exception as exc:  # noqa: BLE001
        logger.warning("FRED %s fetch failed: %s", series_id, exc)
        return []
    if series.empty:
        return []
    cutoff = series.index[-1] - pd.Timedelta(days=days)
    trimmed = series[series.index >= cutoff]
    return [
        {"x": idx.strftime("%Y-%m-%d"), "y": float(val)}
        for idx, val in trimmed.items()
    ]


def build_macro_charts(*, window_days: int = 730) -> list[ChartSpec]:
    client = _load_fred_client()
    eia_client = eia_source.load_client_from_env()

    charts: list[ChartSpec] = []

    if client is not None:
        fred_specs = [
            ("wti", macro_source.SERIES["wti"], "WTI spot", "$ / bbl", "#c53030"),
            ("brent", macro_source.SERIES["brent"], "Brent spot", "$ / bbl", "#6b46c1"),
            ("hh", macro_source.SERIES["hh_gas"], "Henry Hub spot", "$ / MMBtu", "#dd6b20"),
            ("dxy", macro_source.SERIES["dxy"], "USD (broad)", "index", "#2b6cb0"),
            ("ten_year", macro_source.SERIES["ten_year"], "10Y Treasury", "%", "#2f855a"),
        ]
        for chart_id, series_id, title, y_label, color in fred_specs:
            points = _fred_window(client, series_id, days=window_days)
            if points:
                charts.append(
                    ChartSpec(
                        id=chart_id,
                        title=title,
                        label=title,
                        y_label=y_label,
                        color=color,
                        points=points,
                        subtitle=f"FRED series {series_id}, trailing {window_days // 365} years",
                    )
                )
    else:
        logger.info("FRED disabled — no macro charts")

    if eia_client is not None:
        charts.extend(_eia_charts(eia_client))

    return charts


def _eia_charts(client) -> list[ChartSpec]:
    out: list[ChartSpec] = []
    try:
        spr = eia_source.fetch_spr_level(client, limit=156)  # ~3y weekly
        if not spr.empty:
            spr = spr.sort_values("period")
            out.append(
                ChartSpec(
                    id="spr",
                    title="Strategic Petroleum Reserve",
                    label="SPR",
                    y_label="thousand barrels",
                    color="#1a365d",
                    points=[{"x": p.strftime("%Y-%m-%d"), "y": float(v)} for p, v in zip(spr["period"], spr["value"])],
                    subtitle="Weekly, EIA",
                    time_unit="month",
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("EIA SPR history fetch failed: %s", exc)

    try:
        permian = eia_source.fetch_permian_production(client, limit=60)  # 5y monthly
        if not permian.empty:
            permian = permian.sort_values("period")
            out.append(
                ChartSpec(
                    id="permian",
                    title="Permian crude production",
                    label="Permian",
                    y_label="bpd",
                    color="#744210",
                    points=[{"x": p.strftime("%Y-%m-%d"), "y": float(v)} for p, v in zip(permian["period"], permian["value"])],
                    subtitle="Monthly, EIA Drilling Productivity Report",
                    time_unit="month",
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("EIA Permian history fetch failed: %s", exc)

    return out


def _load_fred_client():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    try:
        from fredapi import Fred

        return Fred(api_key=key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fred init failed: %s", exc)
        return None


def load_peer_history() -> dict[str, list[dict[str, Any]]]:
    """Return {ticker: [{as_of, fcf_yield, ...}, ...]} for chart consumption."""
    if not PEER_HISTORY_PATH.exists():
        return {}
    try:
        df = pd.read_parquet(PEER_HISTORY_PATH)
    except Exception as exc:  # noqa: BLE001
        logger.warning("peer history read failed: %s", exc)
        return {}
    if df.empty or "fcf_yield" not in df.columns:
        return {}
    df = df.dropna(subset=["fcf_yield", "as_of"]).sort_values("as_of")
    out: dict[str, list[dict]] = {}
    for ticker, group in df.groupby("ticker"):
        out[str(ticker)] = [
            {
                "as_of": _as_iso(row["as_of"]),
                "fcf_yield": float(row["fcf_yield"]),
            }
            for _, row in group.iterrows()
        ]
    return out


def _as_iso(value: Any) -> str:
    if isinstance(value, (pd.Timestamp, date)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return str(value)
