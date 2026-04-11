# Changelog

All notable changes to ShadowInvestor. Format loosely follows [Keep a Changelog](https://keepachangelog.com/) and uses semantic-ish dating since we're pre-1.0.

## [Phase 3.1] — 2026-04-11

### Added
- **Technical Analysis** — `src/fesi/analysis/ta.py`: SMA(20/50/200), RSI(14), trend detection. Pure Python, no external TA library. API: `GET /api/tickers/{symbol}/indicators`. Ticker detail page shows color-coded indicators (overbought/oversold, price vs SMA arrows, trend).
- **Custom Research Topics** — `research_topics` table + CRUD store. Users create research queries from the UI (max 8 active, $2/month worst case). Runs on schedule: "daily" at morning_catchup, "every_run" for all 5 runs. API: full CRUD at `/api/research/topics`. Frontend: TopicManager component with add/run/delete.
- **Per-Ticker Daily Research** — `PerplexityAdapter.fetch_ticker_research()` runs dedicated Perplexity queries for invested/considering tickers at morning_catchup (once/day). Cost: ~$0.30/month.
- **Price Fetch Endpoint** — `POST /api/prices/fetch-watchlist` fetches yfinance prices for all watchlist tickers remotely. 1,166 bars fetched for 19 tickers on prod.
- **run_label plumbing** — scheduler now passes label (pre_market, morning_catchup, etc.) through to pipeline, enabling per-run-type query customization.
- 8 new TA tests (48 total)

### Fixed
- **sell_qty undefined** — sell endpoint was crashing with NameError; fixed to `actual_sold`
- **Triple PerplexityAdapter** — pipeline was creating 3 separate instances (3 rate limiters, 9 YAML reads); now reuses one
- **JSON schema duplication** — extracted `_EVENT_JSON_SCHEMA` + `_JSON_INSTRUCTIONS` constants shared by all 3 prompt builders

## [Phase 3.0] — 2026-04-11

### Added
- **Position lifecycle** — `positions` table + `src/fesi/store/positions.py`: open, close (full/partial), unrealized P&L tracking. Pipeline auto-opens positions on engine buy decisions.
- **Shadow sell execution** — `execute_shadow_sell()` records virtual sell trades in the trades table.
- **BUY/SKIP/WATCH recommendations** — signal detail page shows colored recommendation banner with entry/stop/target prices and engine reasoning. Joined from decisions table.
- **Discoveries endpoint** — `GET /api/discoveries` surfaces signals mentioning tickers not yet on the watchlist.
- **Portfolio rewrite** — total rewrite with: invested/unrealized/realized P&L summary cards, open positions table with sell buttons, closed positions trade journal.
- **SellButton component** — sell all or partial with confirmation dialog.
- 7 new API endpoints (positions CRUD, sell, discoveries, enhanced signal detail)

### Fixed
- **trades.decision_id** — made nullable for manual sells (was NOT NULL, blocking every sell)
- **plan_position()** — called with positional args but function is keyword-only; fixed to keyword args
- **close_position validation** — shares_to_sell=0 was doing full close; now validates properly
- **pnl_pct** — was using total cost basis for partial closes; now uses remaining cost basis
- **Portfolio** — fetches all positions in 1 API call instead of 3 sequential

## [Phase 2.7] — 2026-04-11

### Added
- **Dynamic watchlist** — `lifecycle_status` (monitoring/considering/invested/paused/archived), `added_by` (yaml/user), `updated_at` on tickers table. UI: AddTickerForm + status badges.
- **Signal user actions** — `user_action` field on signals (invest/skip/watch_pullback). SignalActionButtons component on every signal detail page.
- **User actions audit trail** — `user_actions` table + store. Every action Fred takes is logged.
- **Schema upgrade** — `_upgrade_schema()` in db.py handles ALTER TABLE for existing databases.
- 6 new API endpoints: watchlist CRUD + signal actions + activity feed.

## [Phase 2.6] — 2026-04-10

### Added
- **Perplexity API ingest adapter** — 5th data source. LLM-grounded web search with 6 sector-specific queries per pipeline run (~30 queries/day, ~$0.03/day with `sonar` model). Self-disables if `PERPLEXITY_API_KEY` is not set.
- `src/fesi/ingest/perplexity.py` — new adapter with structured JSON output, bracket-matching fallback parser for trailing prose, cross-source dedup via normalize layer
- `src/fesi/ingest/http.py::post_json()` — shared POST helper with tenacity retry (longer backoff for LLM APIs)
- `fesi ingest perplexity` CLI command
- `tests/test_perplexity_adapter.py` — 8 new tests (40 total, was 32)
- `docs/LEARNINGS.md` — institutional memory: do's, don'ts, gotchas, decisions, what broke
- `docs/ARCHITECTURE.md`, `docs/CLI.md`, `docs/DEPLOYMENT.md`, `docs/DECISION_FRAMEWORK.md`, `CHANGELOG.md`

### Fixed
- **CRITICAL:** SAVEPOINT pattern — `except IntegrityError` was caught inside `with conn.begin_nested()`, poisoning Postgres transactions. Moved exception handling outside the `with` block in `raw_items.py`, `prices.py`, `outcomes.py`.
- **CRITICAL:** Postgres dialect — `postgresql://` URLs defaulted to psycopg2 (not installed). Added `_normalize_url` rewrite to `postgresql+psycopg://` for psycopg v3.
- **Pipeline resilience** — wrapped each candidate/decision/digest phase in `conn.begin_nested()` so one failure doesn't kill the whole run.
- **Scheduler healthcheck** — removed `healthcheckPath` from `railway.toml` (applied to all services including the non-HTTP scheduler). Set per-service via GraphQL.
- **Perplexity parser** — hardened JSON extraction with bracket-matching fallback when Perplexity appends prose after JSON arrays
- **Code dedup** — extracted `strip_md_fence()` as a shared public function in `llm.py` (was duplicated in perplexity.py)

### Changed
- README.md — full rewrite to reflect Phase 1 + Phase 2 ship state (was still showing "Phase 0")
- **Claude classifier now primary in production** — `ANTHROPIC_API_KEY` set on Railway, Claude is the primary classification path (deterministic fallback remains for local dev / CI)
- **Production fully operational** — Railway API + scheduler + Postgres all running, 186+ signals in prod DB, scheduler firing 5x/day

## [Phase 2.5] — 2026-04-09

### Added
- **Code review pass** — three parallel review agents flagged ~15 issues; fixed all of them.
- `web/src/lib/format.ts` — shared `formatTimestamp`, `formatUsd`, `formatPrice`, `formatCount` helpers (replaces 12+ inline duplicates across pages)
- `web/src/components/StatRow.tsx` — `StatRow` (flex) + `StatTile` (grid) reusable components (replaces 13 hand-rolled `dt/dd` rows in admin page + 8 inline `Stat` cards in signal detail)
- `web/src/lib/types.ts` — typed unions: `Mode = "shadow" | "paper" | "live"`, `Action = "buy" | "no_buy" | "sell" | "hold"`, `Sector = ...`

### Fixed
- **CRITICAL:** `scripts/railway_deploy.py:287` — copy-paste bug `upsert_variable(..., env_id and sched_id, ...)` was passing the wrong arg as `service_id`. Fixed to pass `sched_id` directly. The boolean short-circuit happened to make it work, but the intent was clearly wrong.
- `web/src/app/api/admin/run-pipeline/route.ts` — stopped forwarding raw upstream error messages to the browser. Now logs server-side and returns a generic 502.
- `scripts/railway_deploy.py::gql()` — exception now extracts `errors[0].message` instead of dumping the full GraphQL payload (which leaked internal API shapes).
- `Dockerfile` — removed duplicate `HEALTHCHECK` (Railway already runs its own probe via `railway.toml`). Was wasting in-container `curl` calls every 30s.
- `src/fesi/config.py` — `Settings.api_port` now uses `pydantic.AliasChoices("PORT", "API_PORT")` so Railway's `$PORT` env var flows naturally into Settings instead of being read inline in `cli.py`.
- `src/fesi/cli.py::api_run` — removed inline `os.environ.get("PORT")` since Settings now handles it.

## [Phase 2.0–2.4] — 2026-04-09

### Added
- **SQLAlchemy abstraction** — replaces raw `sqlite3` across the entire store layer. Same code runs against SQLite (dev) and Postgres (Railway prod). Schema definitions moved to `src/fesi/store/schema.py` as the single source of truth. `metadata.create_all()` replaces the SQL migration files and is dialect-aware.
- **`raw_items_signals` junction table** — replaces the SQLite-specific `json_each` query for finding unprocessed raw items. Cross-DB portable.
- **FastAPI HTTP layer** at `src/fesi/api/` — 17 routes exposing signals, decisions, tickers, portfolio, sources, digests, pipeline-trigger, status, health. Bearer-token auth via `API_TOKEN` env var. CORS env-var driven. New CLI: `fesi api run`.
- **Dockerfile + railway.toml** — multi-arch Python 3.12 slim base, libpq for psycopg, `/health` endpoint for Railway probes. Same image runs both the api and scheduler services with different start commands.
- **Next.js 16 frontend** in `web/` — Server Components fetch from the Railway API via a typed client. 10 pages: signals (with day/conviction filters), portfolio, tickers (grouped by sector), per-ticker drill-down, source health, digest list, digest reader, framework doc, admin (with one-click "Run pipeline" button), per-signal detail. Site-wide password gate via Next.js 16's `proxy.ts` (formerly `middleware.ts`).
- **`scripts/railway_deploy.py`** — provisions the Railway stack (Postgres, api service, scheduler service, env vars, public domain) via the Railway GraphQL API directly. Bypasses the broken Railway CLI auth flow.
- **`scripts/wire_vercel.py`** — updates Vercel env vars to point at Railway after the API URL is known, then triggers a redeploy.

### Deployed
- **Vercel frontend live** at https://shadowinvestor.vercel.app
- **Railway backend live** at https://shadowinvestor-api-production.up.railway.app — Postgres + API + scheduler all running

### Fixed during deploy
- Railway-runtime shell-form CMD bug (`${PORT:-8000}` not expanded) — switched to pure exec form `CMD ["fesi", "api", "run"]` reading `$PORT` in Python via `Settings.api_port`. Fixed in commits `0831d5f` and `b14af08`.
- Railway template variable `${{Postgres.DATABASE_URL}}` not resolving when set via API — `scripts/railway_deploy.py` now reads Postgres credentials directly and constructs `DATABASE_URL` literally.
- Railway managed Postgres template wasn't being used — provisioning via `serviceCreate(image: "ghcr.io/railwayapp-templates/postgres-ssl:latest")` doesn't auto-set `POSTGRES_PASSWORD`/`POSTGRES_USER`/`POSTGRES_DB`/`PGDATA` like the dashboard "Add Postgres" template does. Script now sets all required env vars manually.
- Railway deploys stuck on stale commit SHA — `serviceInstanceDeployV2` redeploys whatever Railway has cached as latest, not the latest git commit. Script now passes explicit `commitSha` from `git rev-parse HEAD`.
- Next.js 16 build failing on `useSearchParams()` — wrapped login page form in `<Suspense>` boundary.
- TypeScript inferring `Record<string, never[]>` in tickers page reducer — declared accumulator type explicitly.

## [Phase 1] — 2026-04-09

### Added
Full signal pipeline that runs end-to-end against real APIs. **49 Python files, ~5k LOC, 32 passing tests.** First live run produced 5 real shadow buys with $4,952 deployed across 2 sectors and 0 errors.

- **Multi-source ingest** — `src/fesi/ingest/`:
  - `sec_edgar.py` — 8-K/6-K filings via the EDGAR submissions JSON API. Includes ticker → CIK lookup with 7-day cache.
  - `fda_openfda.py` — drug submissions / approvals from OpenFDA. (Intermittently 500s.)
  - `clinicaltrials.py` — ClinicalTrials.gov v2 API, filtered to watchlist sponsors + China geographic sweep.
  - `wires.py` — RSS aggregator across 5 feeds (PR Newswire health/energy/financial, GlobeNewswire, BusinessWire). Uses Firefox UA to bypass PR Newswire's bot block.
- **Intelligence layer** — `src/fesi/intelligence/`:
  - `normalize.py` — fuzzy-title dedup at 0.85 similarity, multi-source grouping
  - `llm.py` — Claude API + deterministic fallback. Fallback uses pattern matching from `config/catalysts.yaml` plus 2-grams from each catalyst's `display_name`. Pipeline runs end-to-end without an Anthropic key.
  - `classifier.py`, `scorer.py` — public interfaces wrapping `llm.py`
  - `cross_ref.py` — corroboration boost (1.0× → 1.15× → 1.30×)
- **Storage layer** — `src/fesi/store/`:
  - `schema.sql` (later moved to `schema.py` in Phase 2)
  - One module per table: `tickers`, `raw_items`, `signals`, `decisions`, `prices`, `outcomes`, `digests`
- **Decision layer** — `src/fesi/decision/`:
  - `engine.py` — main decision logic (conviction threshold + watchlist boost)
  - `risk_gates.py` — 4 hard gates
  - `sizing.py` — conviction-scaled fixed-risk position sizing
- **Execution** — `src/fesi/execute/shadow.py` — virtual fills written to `trades` table
- **Digest** — `src/fesi/digest/`:
  - `render.py` — markdown matching Fred's Perplexity prompt format (Top 10 / Emerging / Watchlist / Follow-up / Shadow Portfolio sections)
  - `notify.py` — Pushover (urgent push) + Telegram (full digest) + always-on file output to `logs/digests/`
- **Operations** — `src/fesi/ops/`:
  - `pipeline.py` — end-to-end orchestrator
  - `scheduler.py` — APScheduler with 5 daily jobs in Asia/Dubai timezone
  - `dashboard.py` — Streamlit dashboard (legacy local dev tool)
- **CLI** — `fesi tickers list`, `fesi prices fetch[--watchlist]`, `fesi ingest <source>`, `fesi run-pipeline`, `fesi outcomes update`, `fesi schedule run`, `fesi digest last`
- **Tests** — 32 tests covering smoke + normalize + classifier fallback + cross-ref + decision engine + digest render + e2e pipeline. All passing.
- **Watchlist aliases system** — `WatchlistTicker.aliases: list[str]` for matching former names / former tickers. Added because BeiGene → BeOne Medicines (BGNE → ONC) renaming broke direct ticker resolution.

### Watchlist seeded
19 tickers across 4 sectors:
- **China biotech (10):** ONC (BeOne Medicines, formerly BeiGene), LEGN, HCM, ZLAB, 1801.HK Innovent, 9926.HK Akeso, 9995.HK RemeGen, 1877.HK Junshi
- **Uranium (4):** CCJ, NXE, DNN, UEC
- **AI infra (3):** NVDA, SMCI, VRT
- **Crypto-to-AI pivots (4):** CIFR, IREN, WULF, CORZ

### Removed
- I-Mab (IMAB) and LianBio (LIAN) from initial seed — both restructured in 2024-2025 and no longer on Yahoo Finance.

## [Phase 0] — 2026-04-09

### Added
- Project scaffold: `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`, `src/fesi/`, `tests/`, `config/`
- 5 YAML configs validated by Pydantic: `sectors.yaml`, `catalysts.yaml`, `risk.yaml`, `sources.yaml`, `watchlist.yaml`
- 6 sectors defined (including the dedicated `china_biotech_us_pipeline` category)
- 28 catalyst types with sectors, typical impact, direction, patterns
- Risk policy v0: $2K/trade, $10K/month, 4 gates, cash-only, no margin
- 16 data sources defined (6 active free + 10 paid/social to enable later)
- SQLite schema with ML-ready feature columns frozen at signal creation time
- Initial 4-test smoke suite

### Decisions made (architecture)
- **Shadow Portfolio approach** instead of historical news backtest. The pipeline runs live in `MODE=shadow` and journals every decision for forward backtest.
- **ML-ready schema from day 1.** Every signal row stores a 12-field feature vector at creation time (point-in-time correct).
- **China-biotech-to-FDA as a dedicated 6th sector.** Most US analysts don't follow Chinese biotechs closely; the disclosure patterns and out-licensing playbook are distinct enough to deserve their own scoring priors.
- **Local-first → Railway/Vercel/RunPod.** Phase 1 ran on Mac with SQLite + APScheduler before any cloud touch.
- **Interactive Brokers (DFSA Dubai branch)** as the broker — verified for UAE residents, AED funding via FAB, 160+ markets including HKEX and TSX-V.
- **Risk policy** confirmed with Fred: max $2K/trade, max $10K/month, cash-only, no margin, no options, no shorts.
