from __future__ import annotations

from src.site.redact import redact


def test_redact_strips_position_section():
    md = """# Energy Intel

## Movers

something

## Position Status

| Ticker | Shares | Last | Cost | P/L | Stop |
|---|---|---|---|---|---|
| PR | 100 | 15.50 | 15.00 | 50 | 14.25 |

## Peer Board

peer table here
"""
    out = redact(md)
    assert "Position Status" not in out
    assert "PR | 100" not in out
    assert "## Movers" in out
    assert "## Peer Board" in out
    assert "peer table here" in out


def test_redact_at_end_of_doc():
    md = """# Intel

## Movers

stuff

## Position Status

secret
"""
    out = redact(md)
    assert "Position Status" not in out
    assert "secret" not in out
    assert "## Movers" in out


def test_redact_missing_section_is_noop():
    md = "# Intel\n\n## Peer Board\n\ncontent\n"
    assert redact(md) == md


def test_redact_preserves_other_warnings():
    md = """## Movers

- **PR** ⚠️ moved +3%

## Position Status

secret

## Signals

- something firing
"""
    out = redact(md)
    assert "⚠️ moved +3%" in out
    assert "something firing" in out
    assert "secret" not in out
