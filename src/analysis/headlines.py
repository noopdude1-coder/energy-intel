"""Headline summarization for the Permian operator brief.

Calls Claude Haiku 4.5 to compress the day's energy headlines into 3-5 ranked
bullets. Falls back to a raw-bullet listing when no API key is available or
the call fails — the brief always ships, with or without LLM summarization.
"""
from __future__ import annotations

import logging
import os
from typing import Protocol

from src.sources.headlines import HeadlineItem

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """\
You are filtering energy news for a Permian Basin operator who trades energy equities.

The reader runs a Permian-focused intel tool. They trade names like PR, FANG, MTDR, OXY, EOG, COP. They want to know what would actually move their business or trades — not generic energy news.

Given today's raw headlines below, output 3-5 bullets ranked by signal-to-noise. Each bullet:
- Start with **[Source]** then a short headline restatement
- Append " — " plus a one-line "why it matters" tag for a Permian operator/trader
- Use markdown only, no preamble, no closing summary, no headers

Skip filler (random rate cuts, retail-investor pieces, generic ESG, listicles). Prioritize:
- OPEC+ decisions; Saudi/UAE/Russia production posture
- Permian-specific items (regulation, takeaway capacity, midstream, M&A)
- WTI/Brent spread drivers
- Major US shale operator earnings, M&A, capex changes
- Geopolitical events affecting global crude (Middle East, Russia/Ukraine, sanctions)

Output only the bullets. No headers, no intro, no outro.
"""


class _ClaudeClient(Protocol):
    @property
    def messages(self): ...  # noqa: D401


def _format_for_llm(items: list[HeadlineItem], limit: int = 30) -> str:
    lines = []
    for h in items[:limit]:
        line = f"[{h.source}] {h.title}"
        if h.summary:
            snippet = h.summary[:240].replace("\n", " ").strip()
            line += f" — {snippet}"
        lines.append(line)
    return "\n".join(lines)


def _fallback_bullets(items: list[HeadlineItem], limit: int = 6) -> str:
    if not items:
        return "_No headlines fetched._"
    lines = []
    for h in items[:limit]:
        lines.append(f"- **{h.source}** — [{h.title}]({h.url})")
    return "\n".join(lines)


def _load_client() -> _ClaudeClient | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # deferred import
    except ImportError:
        logger.warning("anthropic package not installed; headlines fallback to raw bullets")
        return None
    return anthropic.Anthropic()


def summarize(
    items: list[HeadlineItem],
    *,
    client: _ClaudeClient | None = None,
) -> str:
    """Return a markdown bullet list. Always returns something printable."""
    if not items:
        return "_No headlines fetched._"

    client = client if client is not None else _load_client()
    if client is None:
        logger.info("headlines: no Claude client; using raw-bullet fallback")
        return _fallback_bullets(items)

    formatted = _format_for_llm(items)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": formatted}],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("headlines: Claude call failed (%s); using raw-bullet fallback", exc)
        return _fallback_bullets(items)

    text = ""
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            text = block.text.strip()
            break
    if not text:
        logger.warning("headlines: empty Claude response; using raw-bullet fallback")
        return _fallback_bullets(items)
    return text
