"""Markdown → HTML + Jinja environment for the static site."""
from __future__ import annotations

from pathlib import Path

import markdown as md_lib
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"
ASSETS_DIR = Path(__file__).parent / "assets"


def make_env(*, base_path: str = "") -> Environment:
    """Create a Jinja env that knows how to build relative links + asset URLs.

    ``base_path`` prefixes every link; use it when serving from a subdirectory
    (e.g. ``/energy-intel/`` on GitHub Pages for non-user-sites).
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )
    prefix = base_path.strip("/")
    pre = f"/{prefix}/" if prefix else "/"

    def link(path: str) -> str:
        path = path.lstrip("/")
        return f"{pre}{path}"

    def asset(name: str) -> str:
        return link(f"assets/{name}")

    env.globals.update(link=link, asset=asset)
    return env


def markdown_to_html(src: str) -> str:
    return md_lib.markdown(src, extensions=["tables", "fenced_code", "sane_lists"])


def extract_preview(md_text: str, *, max_chars: int = 140) -> str:
    """Pull a short single-line preview from the brief: first non-header line."""
    for raw in md_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("|") or line.startswith("---"):
            continue
        if line.startswith("_") and line.endswith("_"):
            continue
        plain = line.replace("**", "").replace("`", "")
        return plain[: max_chars - 1] + "…" if len(plain) > max_chars else plain
    return ""
