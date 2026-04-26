"""RSS pulls for energy headlines.

Returns a deduped, time-bounded list of HeadlineItem from a small set of
public RSS feeds. Browser User-Agent on every request — some publishers gate
default Python UAs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

FEEDS: dict[str, str] = {
    "EIA": "https://www.eia.gov/rss/todayinenergy.xml",
    "OilPrice": "https://oilprice.com/rss/main",
    "Rigzone": "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
}

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


@dataclass
class HeadlineItem:
    source: str
    title: str
    url: str
    published: datetime | None
    summary: str | None


def _fetch_feed(name: str, url: str, *, session: requests.Session, timeout: float) -> str | None:
    try:
        resp = session.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("headlines: fetch failed for %s (%s): %s", name, url, exc)
        return None
    return resp.text


def _parse_feed(name: str, body: str) -> list[HeadlineItem]:
    import feedparser  # deferred import — keeps tests that don't touch this fast

    parsed = feedparser.parse(body)
    items: list[HeadlineItem] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue
        published: datetime | None = None
        struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if struct:
            try:
                published = datetime(*struct[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published = None
        summary = (entry.get("summary") or "").strip() or None
        items.append(
            HeadlineItem(source=name, title=title, url=url, published=published, summary=summary)
        )
    return items


def _cache_raw(name: str, body: str, *, as_of: datetime) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"headlines_{name.lower()}_{as_of.date().isoformat()}.xml"
        path.write_text(body)
    except OSError as exc:
        logger.debug("headlines: cache write failed for %s: %s", name, exc)


def fetch(
    *,
    feeds: dict[str, str] | None = None,
    lookback_hours: int = 36,
    max_per_feed: int = 12,
    session: requests.Session | None = None,
    timeout: float = 10.0,
    now: datetime | None = None,
) -> list[HeadlineItem]:
    """Fetch + parse all configured feeds, drop anything older than lookback.

    Items without a parseable timestamp are kept (RSS quality varies). De-duped
    by URL across feeds. Sorted newest-first.
    """
    feeds = feeds or FEEDS
    session = session or requests.Session()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)

    collected: list[HeadlineItem] = []
    for name, url in feeds.items():
        body = _fetch_feed(name, url, session=session, timeout=timeout)
        if body is None:
            continue
        _cache_raw(name, body, as_of=now)
        items = _parse_feed(name, body)
        kept = [h for h in items if h.published is None or h.published >= cutoff]
        collected.extend(kept[:max_per_feed])

    seen: set[str] = set()
    deduped: list[HeadlineItem] = []
    for h in collected:
        key = h.url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)

    deduped.sort(key=lambda h: h.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return deduped


def parse_feeds(bodies: Iterable[tuple[str, str]]) -> list[HeadlineItem]:
    """Test helper: parse a list of (source_name, raw_body) tuples directly."""
    out: list[HeadlineItem] = []
    for name, body in bodies:
        out.extend(_parse_feed(name, body))
    return out
