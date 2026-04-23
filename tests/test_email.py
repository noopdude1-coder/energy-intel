"""Tests for Resend email delivery (no live HTTP)."""
from __future__ import annotations

from unittest.mock import MagicMock

from src.delivery import email


def test_from_env_missing_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("RESEND_TO", "me@example.com")
    assert email.EmailConfig.from_env() is None


def test_from_env_missing_recipient(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "k")
    monkeypatch.delenv("RESEND_TO", raising=False)
    assert email.EmailConfig.from_env() is None


def test_from_env_parses_recipients(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "k")
    monkeypatch.setenv("RESEND_TO", "a@x.com, b@x.com")
    monkeypatch.setenv("RESEND_FROM", "brief@x.com")
    cfg = email.EmailConfig.from_env()
    assert cfg is not None
    assert cfg.recipients == ["a@x.com", "b@x.com"]
    assert cfg.sender == "brief@x.com"


def test_send_brief_success():
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    poster = MagicMock(return_value=fake_resp)
    cfg = email.EmailConfig(api_key="k", sender="brief@x.com", recipients=["me@x.com"])

    ok = email.send_brief(
        cfg,
        subject="Energy Intel — 2026-04-23",
        markdown_body="# Hello\n\n**bold** text",
        poster=poster,
    )

    assert ok is True
    poster.assert_called_once()
    _, kwargs = poster.call_args
    payload = kwargs["json"]
    assert payload["from"] == "brief@x.com"
    assert payload["to"] == ["me@x.com"]
    assert payload["subject"] == "Energy Intel — 2026-04-23"
    assert "Hello" in payload["html"]
    assert "<strong>bold</strong>" in payload["html"]
    assert kwargs["headers"]["Authorization"] == "Bearer k"


def test_send_brief_handles_error():
    def boom(**_):
        raise RuntimeError("network")

    cfg = email.EmailConfig(api_key="k", sender="s@x.com", recipients=["r@x.com"])
    assert email.send_brief(cfg, subject="s", markdown_body="body", poster=boom) is False


def test_markdown_to_html_renders_table():
    md = "## Peer Board\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    rendered = email._markdown_to_html(md)
    assert "<h2>Peer Board</h2>" in rendered
    assert "<table" in rendered
    assert "<th>A</th>" in rendered
    assert "<td>1</td>" in rendered
