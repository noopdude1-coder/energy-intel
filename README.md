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

## Scheduling

`.github/workflows/daily-brief.yml` runs weekdays at 06:00 America/Chicago,
generates the brief, and commits it. Required repo secrets: `EIA_API_KEY`,
`FRED_API_KEY`.

## Roadmap

Phase 1 (this): daily brief shipping on schedule.
Phase 2: SEC-driven peer unit economics (CapEx/BOE, FCF yield, hedged %).
Phase 3: GitHub Pages dashboard.
Phase 4: Geopolitical + LLM headline summarization.
