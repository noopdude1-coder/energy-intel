"""Assemble the daily brief from source + analysis outputs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.analysis.position import PositionStatus
from src.analysis.signals import Signal
from src.brief.templates import BRIEF_TEMPLATE, make_env
from src.sources.baker_hughes import RigCountSnapshot
from src.sources.macro import MacroSnapshot


@dataclass
class BriefInputs:
    as_of: datetime
    macro: MacroSnapshot
    peer_board: pd.DataFrame
    positions: list[PositionStatus]
    signals: list[Signal]
    rig_count: RigCountSnapshot | None
    eia_section: str
    mover_threshold_pct: float
    movers: list[dict[str, Any]]
    headlines_section: str = ""


def render(inputs: BriefInputs) -> str:
    env = make_env()
    tmpl = env.from_string(BRIEF_TEMPLATE)

    peer_rows: list[dict[str, Any]] = []
    if not inputs.peer_board.empty:
        for ticker, row in inputs.peer_board.iterrows():
            peer_rows.append({"ticker": ticker, **row.to_dict()})

    rendered = tmpl.render(
        date_str=inputs.as_of.strftime("%A, %B %d, %Y"),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        macro=inputs.macro,
        peer_board_rows=peer_rows,
        positions=[asdict(p) for p in inputs.positions],
        signals=inputs.signals,
        rig_count=inputs.rig_count,
        eia_section=inputs.eia_section,
        mover_threshold=f"{inputs.mover_threshold_pct:.1f}",
        movers=inputs.movers,
        headlines_section=inputs.headlines_section,
    )
    return rendered.rstrip() + "\n"


def build_eia_section(
    *,
    weekday: int,
    crude_stocks: pd.DataFrame | None,
    spr: pd.DataFrame | None,
    cushing: pd.DataFrame | None,
    permian_prod: pd.DataFrame | None,
) -> str:
    """Return a markdown snippet summarizing whatever EIA data is fresh today.

    Called with `weekday` 0=Mon..6=Sun so we only surface weekly petroleum on
    Wednesday (when the report drops) without hardcoding a date check here.
    """
    lines: list[str] = []

    if weekday == 2 and crude_stocks is not None and not crude_stocks.empty:
        latest = crude_stocks.iloc[0]
        prior = crude_stocks.iloc[1] if len(crude_stocks) > 1 else None
        delta = None
        if prior is not None and pd.notna(prior.get("value")):
            delta = float(latest["value"]) - float(prior["value"])
        line = f"**Crude stocks ({latest['period'].date()}):** {float(latest['value']):,.0f} kb"
        if delta is not None:
            sign = "+" if delta >= 0 else "-"
            line += f" ({sign}{abs(delta):,.0f} kb WoW)"
        lines.append(line)

    if weekday == 2 and cushing is not None and not cushing.empty:
        latest = cushing.iloc[0]
        lines.append(
            f"**Cushing stocks ({latest['period'].date()}):** "
            f"{float(latest['value']):,.0f} kb"
        )

    if spr is not None and not spr.empty:
        latest = spr.iloc[0]
        lines.append(
            f"**SPR level ({latest['period'].date()}):** "
            f"{float(latest['value']):,.0f} kb"
        )

    if permian_prod is not None and not permian_prod.empty:
        latest = permian_prod.iloc[0]
        lines.append(
            f"**Permian production ({latest['period'].strftime('%b %Y')}):** "
            f"{float(latest['value']):,.0f} bpd"
        )

    return "\n".join(lines)
