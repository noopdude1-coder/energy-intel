"""Quarterly peer-economics report entrypoint.

Run manually or on a post-earnings schedule::

    python -m src.peer_report

Pulls SEC EDGAR XBRL company facts for every ticker in ``config/peer_ciks.yml``,
computes unit economics, appends a snapshot to ``data/peer_history.parquet``,
and writes ``briefs/peer_comp.md``.

Market cap (for FCF yield) is best-effort via yfinance; if it fails the yield
column is blank and the rest of the report still ships.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.analysis import unit_economics
from src.brief import peer_comp
from src.sources import sec

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "peer_ciks.yml"

logger = logging.getLogger("energy_intel.peer_report")


def _market_cap(ticker: str) -> float | None:
    """Best-effort market cap via yfinance. None on any failure."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
    except Exception as exc:  # noqa: BLE001
        logger.debug("market cap lookup failed for %s: %s", ticker, exc)
        return None
    mc = info.get("marketCap") if isinstance(info, dict) else None
    return float(mc) if mc else None


def run() -> tuple[Path, Path]:
    ciks = sec.load_peer_ciks(CONFIG)
    if not ciks:
        raise SystemExit("config/peer_ciks.yml has no CIKs — nothing to do")

    client = sec.SECClient()
    results: list[unit_economics.PeerMetrics] = []

    for ticker, cik in ciks.items():
        logger.info("fetching %s (CIK %s)", ticker, cik)
        payload = sec.fetch_company_facts(cik, client=client)
        mc = _market_cap(ticker)
        metrics = unit_economics.compute(
            ticker=ticker, cik=cik, payload=payload, market_cap=mc
        )
        results.append(metrics)
        # SEC EDGAR rate limit: 10 req/sec. One peer per 200ms is plenty safe.
        time.sleep(0.2)

    now = datetime.now(timezone.utc)
    md = peer_comp.render_markdown(results, as_of=now)
    md_path = peer_comp.write_markdown(md)
    hist_path = peer_comp.append_history(results)
    return md_path, hist_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate peer unit-economics report.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    md_path, hist_path = run()
    print(md_path)
    print(hist_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
