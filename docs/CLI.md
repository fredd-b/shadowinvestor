# CLI Reference

The `fesi` CLI is the local interface to the ShadowInvestor backend. After `pip install -e .` (or `make install`), the `fesi` command is on your `$PATH`.

## Top-level commands

```bash
fesi --version
fesi --help
fesi status               # print runtime settings (mode, env, DB, key status)
fesi config-check         # load and validate every config/*.yaml
fesi init-db              # create all tables (idempotent) + load watchlist
```

## Sub-commands by group

### `fesi tickers` — watchlist management

```bash
fesi tickers list         # print watchlist tickers grouped by sector
```

### `fesi prices` — price data

```bash
fesi prices fetch <SYMBOL>           # fetch one ticker, last ~30 days from yfinance
fesi prices fetch <SYMBOL> --days 90 # fetch a longer range
fesi prices fetch-watchlist          # fetch all watchlist tickers
fesi prices fetch-watchlist --days 30
```

> Uses `yf.Ticker(symbol).history(period=...)` (not `yf.download`) — see LEARNINGS.md.

### `fesi ingest` — pull data from sources

```bash
fesi ingest sec-edgar          # 8-K / 6-K filings for watchlist tickers
fesi ingest fda                # FDA OpenFDA drug submissions (intermittently 500s)
fesi ingest clinicaltrials     # ClinicalTrials.gov v2, watchlist sponsors + China geo
fesi ingest wires              # PR Newswire / GlobeNewswire / BusinessWire RSS feeds
fesi ingest perplexity         # LLM web search per sector (needs PERPLEXITY_API_KEY)
fesi ingest all                # run all 5 in sequence
```

Each adapter is idempotent — re-running the same window inserts zero rows.

### `fesi run-pipeline` — full end-to-end cycle

```bash
fesi run-pipeline                       # default: 48h scan window, audible push alerts
fesi run-pipeline --window 24           # narrower window
fesi run-pipeline --silent              # don't ring/buzz on Pushover
```

This is the manual equivalent of one scheduled scan. It runs:
1. All ingest adapters
2. Normalize + dedupe
3. Classify + score (Claude or fallback)
4. Cross-reference boost
5. Decide (buy / no_buy with full reasoning, write to `decisions` table)
6. Render digest
7. Notify (file always, Pushover/Telegram if configured)

Output: JSON with `signals_created`, `decisions_buy`, `decisions_no_buy`, `errors`.

### `fesi outcomes` — daily T+N return computation

```bash
fesi outcomes update     # join signals → prices → write T+1, T+5, T+30, T+90 returns
```

Run daily after US market close. Updates the `outcomes` table for any signal that isn't yet `is_mature=1`.

### `fesi schedule` — long-running scheduler

```bash
fesi schedule run        # blocks; runs the 5-job schedule
```

Scheduled jobs (Asia/Dubai timezone):

| Time | Label | Silent? |
|---|---|---|
| 15:00 | `pre_market` (catches overnight US PRs + EU close + HK close) | no — alert on |
| 18:00 | `post_open` (catches US morning news flow) | no |
| 22:00 | `mid_session` (catches afternoon FDA decisions) | yes |
| 02:00 | `post_close` (catches 8-K filings, after-hours PRs) | yes (don't wake you) |
| 08:00 | `morning_catchup` (combines overnight findings) | no |
| 09:00 | `outcomes_daily` (runs `update_all_outcomes`) | n/a |

### `fesi api` — HTTP server

```bash
fesi api run                       # default port from $PORT > $API_PORT > 8000
fesi api run --port 8765           # explicit port override
fesi api run --reload              # auto-reload on file change (dev mode)
```

Starts the FastAPI app at `0.0.0.0:<port>`. Routes documented at `/docs` (FastAPI auto-generated).

### `fesi digest` — read past digests

```bash
fesi digest last         # print the most recent digest body
```

## CLI structure

```
fesi
├── --version
├── --help
├── status
├── config-check
├── init-db
├── tickers
│   └── list
├── prices
│   ├── fetch <symbol>
│   └── fetch-watchlist
├── ingest
│   ├── sec-edgar
│   ├── fda
│   ├── clinicaltrials
│   ├── wires
│   ├── perplexity
│   └── all
├── run-pipeline
├── outcomes
│   └── update
├── schedule
│   └── run
├── api
│   └── run
└── digest
    └── last
```

## Common workflows

### First-time local setup

```bash
make install            # uv venv + uv pip install -e ".[ml,dev]"
source .venv/bin/activate
cp .env.example .env    # then edit
fesi init-db            # creates data/fesi.db, loads watchlist
fesi config-check       # validates all YAML
fesi status
```

### One-shot pipeline run against real APIs

```bash
fesi prices fetch-watchlist --days 30   # ~30 sec for 19 tickers
fesi run-pipeline                        # ~60–120 sec
fesi digest last                         # see what was generated
```

### Inspect the local DB

```bash
python scripts/show_buys.py   # all shadow buy decisions with full reasoning
sqlite3 data/fesi.db ".tables"
sqlite3 data/fesi.db "SELECT count(*), action FROM decisions GROUP BY action;"
sqlite3 data/fesi.db "SELECT * FROM signals ORDER BY conviction_score DESC LIMIT 10;"
```

### Clean re-run (wipe everything, fetch fresh)

```bash
rm data/fesi.db
fesi init-db
fesi prices fetch-watchlist --days 30
fesi run-pipeline
```

> The SEC ticker → CIK cache (`data/sec_cik_map.json`) survives because it's just a lookup table.

### Run the long-lived scheduler locally (overnight test)

```bash
fesi schedule run     # blocks; ctrl-C to stop
```

You'll see jobs registered for each scheduled time. The next scheduled run will fire automatically.

### Run the local FastAPI + Next.js stack together

Terminal A (backend):
```bash
source .venv/bin/activate
fesi api run --port 8765
```

Terminal B (frontend):
```bash
cd web
echo "API_BASE_URL=http://127.0.0.1:8765
API_TOKEN=
SITE_PASSWORD=test" > .env.local
npm install
npm run dev          # → http://localhost:3001
```

Visit http://localhost:3001/login and enter `test`.
