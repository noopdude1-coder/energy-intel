"""Static-site builder.

Reads ``briefs/*.md`` + ``briefs/peer_comp.md`` + ``data/peer_history.parquet``
and writes a self-contained site to ``site/``. Run::

    python -m src.site.build                       # outputs to ./site/
    python -m src.site.build --out dist/ --base-path energy-intel
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.site import history, redact, render

logger = logging.getLogger("energy_intel.site")

ROOT = Path(__file__).resolve().parent.parent.parent
BRIEFS_DIR = ROOT / "briefs"
PEER_COMP_PATH = BRIEFS_DIR / "peer_comp.md"
DEFAULT_OUT = ROOT / "site"

DATE_SLUG_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


@dataclass
class BriefRef:
    path: Path
    slug: str  # YYYY-MM-DD
    date_str: str  # Friday, April 17, 2026
    markdown: str
    preview: str


def discover_briefs() -> list[BriefRef]:
    refs: list[BriefRef] = []
    if not BRIEFS_DIR.exists():
        return refs
    for p in sorted(BRIEFS_DIR.glob("*.md"), reverse=True):
        if p.name == "peer_comp.md":
            continue
        slug = p.stem
        if not DATE_SLUG_RE.match(slug):
            continue
        raw = p.read_text()
        redacted = redact.redact(raw)
        try:
            dt = datetime.strptime(slug, "%Y-%m-%d")
            date_str = dt.strftime("%A, %B %-d, %Y")
        except ValueError:
            date_str = slug
        preview = render.extract_preview(redacted)
        refs.append(
            BriefRef(
                path=p,
                slug=slug,
                date_str=date_str,
                markdown=redacted,
                preview=preview,
            )
        )
    return refs


def _copy_assets(out_dir: Path) -> None:
    dst = out_dir / "assets"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(render.ASSETS_DIR, dst)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def build(*, out_dir: Path, base_path: str = "") -> None:
    env = render.make_env(base_path=base_path)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    def render_template(name: str, **ctx) -> str:
        tmpl = env.get_template(name)
        return tmpl.render(generated_at=generated_at, **ctx)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    _copy_assets(out_dir)

    briefs = discover_briefs()

    # Archive listing
    archive_items = [
        {
            "slug": b.slug,
            "date_str": b.date_str,
            "preview": b.preview,
            "search_blob": f"{b.slug} {b.date_str} {b.preview}",
        }
        for b in briefs
    ]
    _write(
        out_dir / "archive" / "index.html",
        render_template("archive.html", page_title="Archive", briefs=archive_items),
    )

    # Per-brief pages + home (= latest)
    for b in briefs:
        body_html = render.markdown_to_html(b.markdown)
        page = render_template(
            "brief.html",
            page_title=b.slug,
            date_str=b.date_str,
            brief_html=body_html,
        )
        _write(out_dir / "archive" / f"{b.slug}.html", page)

    if briefs:
        latest = briefs[0]
        body_html = render.markdown_to_html(latest.markdown)
        _write(
            out_dir / "index.html",
            render_template(
                "brief.html",
                page_title="Latest",
                date_str=latest.date_str,
                brief_html=body_html,
            ),
        )
    else:
        _write(
            out_dir / "index.html",
            render_template(
                "brief.html",
                page_title="Energy Intel",
                date_str="no briefs yet",
                brief_html="<p><em>No briefs have been generated yet.</em></p>",
            ),
        )

    # Peers page
    peer_md = PEER_COMP_PATH.read_text() if PEER_COMP_PATH.exists() else ""
    peer_html = render.markdown_to_html(peer_md) if peer_md else ""
    peer_history = history.load_peer_history()
    _write(
        out_dir / "peers" / "index.html",
        render_template(
            "peers.html",
            page_title="Peers",
            peer_report_html=peer_html,
            history_points=peer_history,
        ),
    )

    # Macro page
    charts = history.build_macro_charts()
    chart_dicts = [
        {
            "id": c.id,
            "title": c.title,
            "subtitle": c.subtitle,
            "label": c.label,
            "y_label": c.y_label,
            "color": c.color,
            "points": c.points,
            "time_unit": c.time_unit,
        }
        for c in charts
    ]
    _write(
        out_dir / "macro" / "index.html",
        render_template("macro.html", page_title="Macro", series=chart_dicts),
    )

    # Empty .nojekyll so GitHub Pages serves `_`-prefixed paths as-is if any.
    (out_dir / ".nojekyll").write_text("")

    logger.info(
        "built site at %s (%d briefs, %d macro charts, %d peer tickers)",
        out_dir,
        len(briefs),
        len(charts),
        len(peer_history),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the static site.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    parser.add_argument(
        "--base-path",
        default="",
        help="URL prefix; e.g. 'energy-intel' for github.io/energy-intel/",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    build(out_dir=Path(args.out), base_path=args.base_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
