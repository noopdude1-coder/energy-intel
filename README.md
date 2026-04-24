# energy-intel

Permian-focused daily energy intelligence brief. Pulls EIA, Baker Hughes, equity,
and macro data on a weekday schedule, composes a scannable markdown brief, and
commits it to the repo.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/positions.example.yml config/positions.yml   # fill in holdings, gitignored
export EIA_API_KEY=...
export FRED_API_KEY=...
python -m src.main                                     # writes briefs/YYYY-MM-DD.md
```

## Layout

- `src/sources/` — one module per data source (EIA, Baker Hughes, equities, macro).
- `src/analysis/` — peer comp, position risk, signal flags.
- `src/brief/` — Jinja2 templates and assembly.
- `src/main.py` — entrypoint invoked by the GitHub Actions cron.
- `config/watchlist.yml` — tickers, peers, thresholds (checked in).
- `config/positions.yml` — live holdings + stops (gitignored; never committed).
- `briefs/` — daily markdown output, committed by the Actions bot.
- `data/raw/` — date-stamped raw pulls for replay/debug (gitignored).

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Tests use recorded fixtures in `tests/fixtures/` and never hit live APIs.

## Peer unit economics (Phase 2)

On-demand run, post-earnings:

```bash
python -m src.peer_report
```

Pulls SEC EDGAR XBRL company facts for every ticker in `config/peer_ciks.yml`,
computes TTM OCF / CapEx / FCF / net debt / EBITDAX / ND-to-EBITDAX, writes
`briefs/peer_comp.md`, and appends the snapshot to `data/peer_history.parquet`.
No API key — SEC requires a descriptive `User-Agent`; override via the
`SEC_USER_AGENT` env var before running.

## Scheduling

`.github/workflows/daily-brief.yml` runs weekdays at 06:00 America/Chicago,
generates the brief, and commits it. Required repo secrets: `EIA_API_KEY`,
`FRED_API_KEY`.

## Public dashboard (Phase 3)

```bash
python -m src.site.build                            # writes ./site/
python -m src.site.build --base-path energy-intel   # for github.io/energy-intel/
```

Produces a static site with four pages:
- `/` — latest brief
- `/archive/` — every past brief, client-side search
- `/peers/` — peer unit economics table + FCF-yield history chart
- `/macro/` — rolling FRED series (WTI, Brent, HH, DXY, 10Y) plus EIA SPR and
  Permian production when keys are available

**Safety:** every brief runs through `src/site/redact.py` before rendering, which
strips the `## Position Status` section. Even if a brief was generated locally
with `positions.yml` populated and committed by mistake, position data never
reaches the public site.

Deploy is automatic via `.github/workflows/pages.yml`. To enable:
1. Settings → Pages → Build and deployment source = **GitHub Actions**.
2. Push anything that touches `briefs/`, `data/peer_history.parquet`, or
   `src/site/`.

## Roadmap

Phase 1 (shipped): daily brief on schedule.
Phase 2 (shipped): SEC-driven peer unit economics (FCF yield, net debt, ND/EBITDAX).
  Deferred to a future iteration: CapEx/BOE, hedged %, PV-10/EV, D&C/lateral ft —
  these live in custom XBRL extensions or narrative text and need per-filer parsers.
Phase 3 (shipped): GitHub Pages dashboard.
Phase 4: Geopolitical + LLM headline summarization.
