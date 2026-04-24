"""Smoke test for the static site builder.

Verifies that a build against a synthetic briefs/ + peer_comp.md produces the
expected HTML tree, and that position data is never exposed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.site import build as site_build


@pytest.fixture
def seeded_repo(tmp_path, monkeypatch):
    """Create a minimal project tree with one brief + peer_comp, and chdir in."""
    (tmp_path / "briefs").mkdir()
    (tmp_path / "data").mkdir()

    (tmp_path / "briefs" / "2026-04-20.md").write_text(
        "# Energy Intel — Monday, April 20, 2026\n\n"
        "**Spot:** WTI $82.00\n\n"
        "## Movers\n\nNone.\n\n"
        "## Position Status\n\n"
        "| Ticker | Shares | Last |\n|---|---|---|\n| PR | 500 | 15.50 |\n\n"
        "## Peer Board\n\npeer data\n"
    )
    (tmp_path / "briefs" / "2026-04-21.md").write_text(
        "# Energy Intel — Tuesday, April 21, 2026\n\n"
        "**Spot:** WTI $83.00\n\n"
        "## Movers\n\nPR +3%.\n"
    )
    (tmp_path / "briefs" / "peer_comp.md").write_text(
        "# Permian Peer Unit Economics\n\n"
        "| Ticker | FCF |\n|---|---|\n| PR | $820M |\n"
    )
    monkeypatch.chdir(tmp_path)

    # Repoint BRIEFS_DIR / PEER_COMP_PATH which are computed at import time.
    monkeypatch.setattr(site_build, "BRIEFS_DIR", tmp_path / "briefs")
    monkeypatch.setattr(site_build, "PEER_COMP_PATH", tmp_path / "briefs" / "peer_comp.md")

    return tmp_path


def test_build_produces_expected_tree(seeded_repo, tmp_path):
    out = tmp_path / "site-out"
    site_build.build(out_dir=out)

    assert (out / "index.html").exists()
    assert (out / "archive" / "index.html").exists()
    assert (out / "archive" / "2026-04-20.html").exists()
    assert (out / "archive" / "2026-04-21.html").exists()
    assert (out / "peers" / "index.html").exists()
    assert (out / "macro" / "index.html").exists()
    assert (out / "assets" / "style.css").exists()
    assert (out / ".nojekyll").exists()


def test_home_is_latest_brief(seeded_repo, tmp_path):
    out = tmp_path / "site-out"
    site_build.build(out_dir=out)
    home = (out / "index.html").read_text()
    assert "April 21, 2026" in home
    assert "WTI $83.00" in home


def test_position_data_never_exposed(seeded_repo, tmp_path):
    out = tmp_path / "site-out"
    site_build.build(out_dir=out)
    for html in out.rglob("*.html"):
        text = html.read_text()
        assert "Position Status" not in text, f"leak in {html}"
        assert "500" not in text or "15.50" not in text, f"possible leak in {html}"


def test_archive_lists_both_briefs_newest_first(seeded_repo, tmp_path):
    out = tmp_path / "site-out"
    site_build.build(out_dir=out)
    archive = (out / "archive" / "index.html").read_text()
    # Both slugs linked
    assert "2026-04-20" in archive
    assert "2026-04-21" in archive
    # Latest listed first
    assert archive.index("2026-04-21") < archive.index("2026-04-20")


def test_peer_page_renders_report(seeded_repo, tmp_path):
    out = tmp_path / "site-out"
    site_build.build(out_dir=out)
    peers = (out / "peers" / "index.html").read_text()
    assert "Permian Peer Unit Economics" in peers
    assert "$820M" in peers


def test_empty_briefs_still_builds(tmp_path, monkeypatch):
    (tmp_path / "briefs").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(site_build, "BRIEFS_DIR", tmp_path / "briefs")
    monkeypatch.setattr(site_build, "PEER_COMP_PATH", tmp_path / "briefs" / "peer_comp.md")

    out = tmp_path / "site-out"
    site_build.build(out_dir=out)
    home = (out / "index.html").read_text()
    assert "No briefs have been generated yet" in home
