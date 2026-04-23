"""Render the peer-economics markdown + accumulate history.

The peer_comp doc is updated on-demand (not daily) after each earnings wave.
Each run:
- Appends one row per ticker to ``data/peer_history.parquet`` stamped with
  ``as_of`` from the latest filing.
- Overwrites ``briefs/peer_comp.md`` with the current snapshot table.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analysis.unit_economics import PeerMetrics

logger = logging.getLogger(__name__)

HISTORY_PATH = Path("data/peer_history.parquet")
BRIEFS_DIR = Path("briefs")


def _fmt_millions(v: float | None) -> str:
    if v is None:
        return "—"
    return f"${v / 1e6:,.0f}M"


def _fmt_billions(v: float | None) -> str:
    if v is None:
        return "—"
    return f"${v / 1e9:,.2f}B"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:+.2f}%"


def _fmt_ratio(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.2f}x"


def render_markdown(rows: list[PeerMetrics], *, as_of: datetime) -> str:
    lines: list[str] = []
    lines.append("# Permian Peer Unit Economics")
    lines.append("")
    lines.append(f"_Generated {as_of.strftime('%Y-%m-%d %H:%M')} UTC. "
                 f"Source: SEC EDGAR XBRL company facts. "
                 f"TTM = trailing 4 quarters or latest 10-K._")
    lines.append("")
    lines.append("| Ticker | Filing | TTM OCF | TTM CapEx | FCF | FCF Yield | Net Debt | EBITDAX | ND/EBITDAX |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in rows:
        lines.append(
            "| {ticker} | {as_of} | {ocf} | {capex} | {fcf} | {fcfy} | {nd} | {ebx} | {lev} |".format(
                ticker=m.ticker,
                as_of=m.as_of.isoformat() if m.as_of else "—",
                ocf=_fmt_millions(m.ttm_ocf),
                capex=_fmt_millions(m.ttm_capex),
                fcf=_fmt_millions(m.fcf),
                fcfy=_fmt_pct(m.fcf_yield),
                nd=_fmt_billions(m.net_debt),
                ebx=_fmt_millions(m.ebitdax),
                lev=_fmt_ratio(m.net_debt_to_ebitdax),
            )
        )

    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- **CapEx/BOE, hedged %, PV-10, D&C/lateral ft** are intentionally "
        "omitted — those live in company-specific XBRL extensions or narrative text "
        "and would require per-filer parsers. Planned for a future iteration."
    )
    lines.append(
        "- **EBITDAX** here is Net Income + Interest + Tax + D&A + Exploration "
        "(TTM). If any component is missing from the filer's taxonomy usage, "
        "it is treated as zero; the resulting ratio should be read as a floor."
    )
    lines.append(
        "- **FCF Yield** uses the market cap supplied at run time; reruns against "
        "the same filings with fresh quotes will shift the yield."
    )
    return "\n".join(lines) + "\n"


def append_history(rows: list[PeerMetrics]) -> Path:
    """Append today's snapshot to ``data/peer_history.parquet``.

    One row per (ticker, as_of) — duplicates are deduplicated in favor of the
    latest run so re-running the day of a filing overwrites stale partials.
    """
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.DataFrame([m.to_row() for m in rows])
    new_df["run_at"] = datetime.now(timezone.utc)

    if HISTORY_PATH.exists():
        prior = pd.read_parquet(HISTORY_PATH)
        combined = pd.concat([prior, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = combined.drop_duplicates(
        subset=["ticker", "as_of"], keep="last"
    ).reset_index(drop=True)
    combined.to_parquet(HISTORY_PATH, index=False)
    logger.info("peer history now at %s (%d rows)", HISTORY_PATH, len(combined))
    return HISTORY_PATH


def write_markdown(body: str) -> Path:
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEFS_DIR / "peer_comp.md"
    path.write_text(body)
    return path
