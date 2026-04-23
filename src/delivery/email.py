"""Email delivery via Resend.

Uses the Resend HTTP API directly (no SDK) to keep the dependency set small.
A send is a no-op if ``RESEND_API_KEY`` or ``RESEND_TO`` is missing — this
matches the Phase 1 "graceful degradation" rule: the brief still ships to the
repo even if email isn't configured.

The markdown brief is sent as both plain text and a lightly-rendered HTML body
(headings + code blocks). This avoids pulling a heavy markdown library; GitHub
remains the canonical rendered view.
"""
from __future__ import annotations

import html
import logging
import os
import re
from dataclasses import dataclass
from typing import Protocol

import requests

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


class HttpPoster(Protocol):
    def __call__(self, url: str, json: dict, headers: dict, timeout: float) -> requests.Response: ...


@dataclass
class EmailConfig:
    api_key: str
    sender: str
    recipients: list[str]

    @classmethod
    def from_env(cls) -> "EmailConfig | None":
        api_key = os.environ.get("RESEND_API_KEY")
        sender = os.environ.get("RESEND_FROM", "energy-intel@resend.dev")
        to = os.environ.get("RESEND_TO")
        if not api_key or not to:
            return None
        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
        if not recipients:
            return None
        return cls(api_key=api_key, sender=sender, recipients=recipients)


def _markdown_to_html(md: str) -> str:
    """Minimal markdown → HTML. Handles headings, pipe tables, bold, and line breaks.

    Deliberately shallow: the repo-committed markdown on GitHub is the canonical
    view; this exists so the email isn't a wall of raw markdown syntax.
    """
    lines = md.splitlines()
    out: list[str] = []
    in_table = False

    def flush_table_row(row: str, *, header: bool) -> str:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        tag = "th" if header else "td"
        inner = "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in cells)
        return f"<tr>{inner}</tr>"

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1]):
            out.append("<table border='1' cellpadding='4' cellspacing='0'>")
            out.append(flush_table_row(line, header=True))
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                out.append(flush_table_row(lines[i], header=False))
                i += 1
            out.append("</table>")
            continue
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip() == "":
            out.append("")
        else:
            bolded = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(line))
            out.append(f"<p>{bolded}</p>")
        i += 1
    return "\n".join(out)


def _default_poster(url: str, json: dict, headers: dict, timeout: float) -> requests.Response:
    return requests.post(url, json=json, headers=headers, timeout=timeout)


def send_brief(
    config: EmailConfig,
    *,
    subject: str,
    markdown_body: str,
    poster: HttpPoster = _default_poster,
) -> bool:
    payload = {
        "from": config.sender,
        "to": config.recipients,
        "subject": subject,
        "text": markdown_body,
        "html": _markdown_to_html(markdown_body),
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = poster(RESEND_ENDPOINT, json=payload, headers=headers, timeout=15.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("email send failed: %s", exc)
        return False
    logger.info("email sent to %s", ", ".join(config.recipients))
    return True
