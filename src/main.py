"""Daily brief entrypoint.

Run locally: ``python -m src.main``
CI runs this from ``.github/workflows/daily-brief.yml`` and commits the output.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.analysis import peer_comp, position, signals
from src.brief.generate import BriefInputs, build_eia_section, render
from src.sources import baker_hughes, eia, equities, macro

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
BRIEFS_DIR = ROOT / "briefs"

logger = logging.getLogger("energy_intel")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _safe(fn, *, label: str, default):
    """Call fn(); on any exception log and return default. Keeps the brief shipping."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", label, exc)
        return default


def run(*, as_of: datetime | None = None) -> Path:
    as_of = as_of or datetime.now(timezone.utc)

    watchlist = _load_yaml(CONFIG_DIR / "watchlist.yml")
    positions_cfg = _load_yaml(CONFIG_DIR / "positions.yml")

    tickers = sorted(
        {
            *watchlist.get("peers", []),
            *watchlist.get("majors", []),
            *watchlist.get("benchmarks", []),
        }
    )
    thresholds = watchlist.get("thresholds", {})
    mover_threshold = float(thresholds.get("mover_abs_pct", 2.0))
    stop_warning = float(thresholds.get("stop_warning_pct", 2.0))
    brent_wti_hi = float(thresholds.get("brent_wti_spread_hi", 6.0))
    brent_wti_lo = float(thresholds.get("brent_wti_spread_lo", 2.0))

    board = _safe(
        lambda: equities.build_peer_board(tickers, today=as_of),
        label="equities.build_peer_board",
        default=pd.DataFrame(),
    )

    last_prices: dict[str, float] = (
        board["last"].to_dict() if not board.empty and "last" in board.columns else {}
    )

    holdings = position.load_holdings(positions_cfg.get("holdings", []))
    position_status = position.evaluate(holdings, last_prices, warning_pct=stop_warning)

    macro_snap = _safe(macro.fetch_snapshot, label="macro.fetch_snapshot", default=macro.MacroSnapshot({}, {}))

    eia_client = eia.load_client_from_env()
    crude_stocks = (
        _safe(lambda: eia.fetch_weekly_crude_stocks(eia_client), label="eia.crude_stocks", default=None)
        if eia_client
        else None
    )
    spr = (
        _safe(lambda: eia.fetch_spr_level(eia_client), label="eia.spr", default=None)
        if eia_client
        else None
    )
    cushing = (
        _safe(lambda: eia.fetch_cushing_stocks(eia_client), label="eia.cushing", default=None)
        if eia_client
        else None
    )
    permian_prod = (
        _safe(lambda: eia.fetch_permian_production(eia_client), label="eia.permian_prod", default=None)
        if eia_client
        else None
    )

    eia_section = build_eia_section(
        weekday=as_of.weekday(),
        crude_stocks=crude_stocks,
        spr=spr,
        cushing=cushing,
        permian_prod=permian_prod,
    )

    rig_count = _safe(baker_hughes.fetch_latest, label="baker_hughes.fetch_latest", default=None)

    mover_tickers = peer_comp.flag_movers(board, mover_threshold)
    movers = [
        {
            "ticker": t,
            "last": board.loc[t, "last"],
            "one_day_pct": board.loc[t, "one_day_pct"],
        }
        for t in mover_tickers
    ]

    firing: list[signals.Signal] = []
    bwti = signals.brent_wti_spread(
        macro_snap.get("brent"),
        macro_snap.get("wti"),
        hi=brent_wti_hi,
        lo=brent_wti_lo,
    )
    if bwti:
        firing.append(bwti)
    rs = signals.relative_strength_break(board, a="PR", b="FANG")
    if rs:
        firing.append(rs)

    inputs = BriefInputs(
        as_of=as_of,
        macro=macro_snap,
        peer_board=peer_comp.rank_by_one_day(board),
        positions=position_status,
        signals=firing,
        rig_count=rig_count,
        eia_section=eia_section,
        mover_threshold_pct=mover_threshold,
        movers=movers,
    )

    body = render(inputs)

    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRIEFS_DIR / f"{as_of.date().isoformat()}.md"
    out_path.write_text(body)
    logger.info("wrote %s (%d bytes)", out_path, len(body))
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the daily energy brief.")
    parser.add_argument("--date", help="ISO date to stamp on the brief (default: today UTC)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    as_of = datetime.now(timezone.utc)
    if args.date:
        as_of = datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc)

    path = run(as_of=as_of)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
