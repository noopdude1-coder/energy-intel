"""End-to-end render test for the brief template."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.analysis.position import PositionStatus
from src.analysis.signals import Signal
from src.brief.generate import BriefInputs, build_eia_section, render
from src.sources.macro import MacroSnapshot


def _macro() -> MacroSnapshot:
    return MacroSnapshot(
        values={"wti": 82.10, "brent": 85.40, "hh_gas": 2.15, "dxy": 104.8, "ten_year": 4.35},
        as_of={},
    )


def _board() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "last": [15.50, 170.0],
            "one_day_pct": [1.2, -0.8],
            "five_day_pct": [3.4, 1.1],
            "ytd_pct": [10.2, 5.1],
            "range_52w_pct": [0.55, 0.40],
            "low_52w": [12.0, 140.0],
            "high_52w": [19.0, 210.0],
        },
        index=["PR", "FANG"],
    )


def test_render_contains_key_sections():
    inputs = BriefInputs(
        as_of=datetime(2026, 4, 23, tzinfo=timezone.utc),
        macro=_macro(),
        peer_board=_board(),
        positions=[
            PositionStatus(
                ticker="PR",
                shares=100,
                cost_basis=15.00,
                trailing_stop=14.25,
                last=15.50,
                unrealized_pl=50.0,
                unrealized_pct=3.33,
                stop_distance_pct=8.06,
                stop_warning=False,
            )
        ],
        signals=[Signal(name="Brent-WTI spread wide", detail="$6.50/bbl")],
        rig_count=None,
        eia_section="",
        mover_threshold_pct=2.0,
        movers=[],
    )
    body = render(inputs)

    assert "# Energy Intel" in body
    assert "Position Status" in body
    assert "Peer Board" in body
    assert "Signals" in body
    assert "PR" in body
    assert "$82.10" in body  # WTI rendered


def test_render_degrades_when_sources_missing():
    inputs = BriefInputs(
        as_of=datetime(2026, 4, 23, tzinfo=timezone.utc),
        macro=MacroSnapshot({}, {}),
        peer_board=pd.DataFrame(),
        positions=[],
        signals=[],
        rig_count=None,
        eia_section="",
        mover_threshold_pct=2.0,
        movers=[],
    )
    body = render(inputs)
    assert "macro source unavailable" in body
    assert "equities source unavailable" in body


def test_build_eia_section_wednesday_includes_stocks():
    crude = pd.DataFrame(
        {
            "period": pd.to_datetime(["2026-04-17", "2026-04-10"]),
            "value": [456000.0, 458000.0],
        }
    )
    section = build_eia_section(
        weekday=2, crude_stocks=crude, spr=None, cushing=None, permian_prod=None
    )
    assert "Crude stocks" in section
    assert "WoW" in section


def test_build_eia_section_non_wednesday_skips_weekly():
    crude = pd.DataFrame(
        {"period": pd.to_datetime(["2026-04-17"]), "value": [456000.0]}
    )
    section = build_eia_section(
        weekday=0, crude_stocks=crude, spr=None, cushing=None, permian_prod=None
    )
    assert section == ""
