"""Tests for peer_comp markdown rendering + parquet history."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from src.analysis.unit_economics import PeerMetrics
from src.brief import peer_comp


def _sample() -> list[PeerMetrics]:
    return [
        PeerMetrics(
            ticker="PR",
            cik="0001658566",
            entity_name="Permian Resources Corp",
            as_of=date(2025, 9, 30),
            ttm_ocf=2_840_000_000,
            ttm_capex=2_020_000_000,
            fcf=820_000_000,
            fcf_yield=0.082,
            market_cap=10_000_000_000,
            net_debt=4_000_000_000,
            ebitdax=2_701_000_000,
            net_debt_to_ebitdax=1.48,
        ),
        PeerMetrics(
            ticker="FANG",
            cik="0001539838",
            entity_name="Diamondback Energy, Inc.",
            as_of=None,
            ttm_ocf=None,
        ),
    ]


def test_render_markdown_includes_key_cells():
    md = peer_comp.render_markdown(_sample(), as_of=datetime(2026, 4, 23, tzinfo=timezone.utc))
    assert "Permian Peer Unit Economics" in md
    assert "| PR | 2025-09-30" in md
    assert "$820M" in md       # FCF formatting
    assert "+8.20%" in md      # FCF yield
    assert "$4.00B" in md      # Net debt formatting
    assert "1.48x" in md       # Leverage ratio
    assert "| FANG | — | —" in md  # degrades cleanly
    assert "Caveats" in md


def test_append_history_creates_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    peer_comp.append_history(_sample())
    peer_comp.append_history(_sample())  # re-run, should dedupe
    df = pd.read_parquet(tmp_path / "data" / "peer_history.parquet")
    assert len(df) == 2  # one per ticker, deduped on (ticker, as_of)
    assert set(df["ticker"]) == {"PR", "FANG"}


def test_write_markdown_overwrites(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    peer_comp.write_markdown("v1")
    peer_comp.write_markdown("v2")
    assert (tmp_path / "briefs" / "peer_comp.md").read_text() == "v2"
