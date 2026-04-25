"""Tests for the RSS source layer (Phase 4).

Uses a small XML fixture; no live HTTP. Skips if feedparser isn't installed
(local dev sandboxes occasionally lack sgmllib3k); CI installs the full
requirements.txt and runs everything.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("feedparser", reason="feedparser not installed")

from src.sources import headlines as headlines_source  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "headlines_sample.xml"


def test_parse_feed_extracts_items():
    body = FIXTURE.read_text()
    items = headlines_source.parse_feeds([("Sample", body)])
    titles = [i.title for i in items]
    assert "OPEC+ Holds Output Steady Through Q3" in titles
    assert "Headline With No Date" in titles
    by_title = {i.title: i for i in items}
    opec = by_title["OPEC+ Holds Output Steady Through Q3"]
    assert opec.source == "Sample"
    assert opec.url == "https://example.com/opec-q3"
    assert opec.published is not None
    assert opec.summary and "39.7 mb/d" in opec.summary


def test_fetch_drops_stale_items_outside_lookback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = FIXTURE.read_text()

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            return SimpleNamespace(text=body, raise_for_status=lambda: None)

    items = headlines_source.fetch(
        feeds={"Sample": "https://example.com/feed"},
        lookback_hours=72,
        session=FakeSession(),
        now=datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
    )
    titles = [i.title for i in items]
    assert "Old Stale Headline From Last Year" not in titles
    assert "OPEC+ Holds Output Steady Through Q3" in titles
    assert "Headline With No Date" in titles  # undated items survive


def test_fetch_dedupes_across_feeds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = FIXTURE.read_text()

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            return SimpleNamespace(text=body, raise_for_status=lambda: None)

    items = headlines_source.fetch(
        feeds={"A": "https://x", "B": "https://y"},
        lookback_hours=72,
        session=FakeSession(),
        now=datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
    )
    urls = [i.url for i in items]
    assert len(urls) == len(set(urls))


def test_fetch_continues_when_one_feed_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = FIXTURE.read_text()
    calls: dict[str, int] = {"a": 0, "b": 0}

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            if "a" in url:
                calls["a"] += 1
                raise RuntimeError("boom")
            calls["b"] += 1
            return SimpleNamespace(text=body, raise_for_status=lambda: None)

    items = headlines_source.fetch(
        feeds={"A": "https://a/feed", "B": "https://b/feed"},
        lookback_hours=72,
        session=FakeSession(),
        now=datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
    )
    assert items
    assert calls == {"a": 1, "b": 1}
