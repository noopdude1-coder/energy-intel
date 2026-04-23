"""Fixture-based tests for the Baker Hughes scraper. No live HTTP."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from src.sources import baker_hughes

FIXTURE = Path(__file__).parent / "fixtures" / "baker_hughes_landing.html"


def test_parse_snapshot_extracts_us_total_and_permian():
    html = FIXTURE.read_text()
    snap = baker_hughes.parse_snapshot(html)
    assert snap is not None
    assert snap.total_us == 583
    assert snap.permian == 337
    assert snap.permian_wow == -2
    assert snap.permian_yoy == -20
    assert snap.as_of == date(2026, 4, 17)


def test_parse_snapshot_returns_none_on_empty_html():
    assert baker_hughes.parse_snapshot("<html></html>") is None


def test_parse_snapshot_returns_none_when_permian_row_missing():
    html = """
    <html><body>
    <table><thead><tr><th>Oil</th><th>Gas</th><th>Total</th></tr></thead>
    <tbody><tr><td>Total</td><td>500</td><td>100</td><td>600</td></tr></tbody>
    </table>
    <table><tbody><tr><td>Eagle Ford</td><td>50</td></tr></tbody></table>
    </body></html>
    """
    assert baker_hughes.parse_snapshot(html) is None


def test_fetch_latest_uses_injected_fetcher(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    html = FIXTURE.read_text()
    snap = baker_hughes.fetch_latest(fetcher=lambda url: html)
    assert snap is not None
    assert snap.permian == 337
    # raw HTML cached for debug
    cached = list((tmp_path / "data" / "raw").glob("baker_hughes_*.html"))
    assert cached


def test_fetch_latest_handles_http_failure():
    def boom(url):
        raise RuntimeError("403 blocked by WAF")

    assert baker_hughes.fetch_latest(fetcher=boom) is None
