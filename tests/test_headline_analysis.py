"""Tests for the headline summarizer (no feedparser dependency)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from src.analysis import headlines as headline_analysis
from src.sources.headlines import HeadlineItem


def _items() -> list[HeadlineItem]:
    return [
        HeadlineItem(
            source="EIA",
            title="Permian production tops 6.4 mb/d",
            url="https://example.com/permian",
            published=datetime(2026, 4, 24, tzinfo=timezone.utc),
            summary="Delaware drove growth.",
        ),
        HeadlineItem(
            source="OilPrice",
            title="OPEC+ holds output steady",
            url="https://example.com/opec",
            published=datetime(2026, 4, 24, tzinfo=timezone.utc),
            summary=None,
        ),
    ]


def test_summarize_empty_returns_placeholder():
    assert headline_analysis.summarize([]) == "_No headlines fetched._"


def test_summarize_no_client_falls_back_to_raw_bullets(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = headline_analysis.summarize(_items())
    assert "**EIA**" in out
    assert "Permian production" in out
    assert "https://example.com/opec" in out


def test_summarize_uses_injected_client():
    captured: dict = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            text_block = SimpleNamespace(
                type="text", text="- **[EIA]** Permian +6.4 mb/d — bullish"
            )
            return SimpleNamespace(content=[text_block])

    fake_client = SimpleNamespace(messages=FakeMessages())
    out = headline_analysis.summarize(_items(), client=fake_client)
    assert out == "- **[EIA]** Permian +6.4 mb/d — bullish"
    assert captured["model"] == "claude-haiku-4-5"
    assert "Permian operator" in captured["system"]


def test_summarize_falls_back_when_claude_raises():
    class FakeMessages:
        def create(self, **kwargs):
            raise RuntimeError("rate limit")

    fake_client = SimpleNamespace(messages=FakeMessages())
    out = headline_analysis.summarize(_items(), client=fake_client)
    assert "**EIA**" in out  # raw fallback


def test_summarize_falls_back_when_response_has_no_text():
    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(content=[])

    fake_client = SimpleNamespace(messages=FakeMessages())
    out = headline_analysis.summarize(_items(), client=fake_client)
    assert "**EIA**" in out
