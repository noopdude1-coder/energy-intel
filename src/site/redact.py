"""Strip position-sensitive content from a brief before public rendering.

The public dashboard must never expose the ``## Position Status`` section.
``positions.yml`` is gitignored, so briefs generated in CI already have a
placeholder — but a local ad-hoc run could leak position data into a
committed brief. This module is belt-and-suspenders against that.

Policy:
- Remove the entire ``## Position Status`` section (until the next ``## `` header).
- Leave every other section untouched.
"""
from __future__ import annotations

import re

SECTION_HEADER = re.compile(r"^##\s+", re.MULTILINE)


def redact(markdown: str) -> str:
    """Return `markdown` with the Position Status section removed."""
    pattern = re.compile(
        r"^##\s+Position Status\s*\n"  # section header
        r".*?"                          # body (non-greedy)
        r"(?=^##\s+|\Z)",               # up to next ## header or end of doc
        re.DOTALL | re.MULTILINE,
    )
    return pattern.sub("", markdown)
