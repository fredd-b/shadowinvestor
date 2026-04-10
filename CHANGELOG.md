# Changelog

All notable changes to ShadowInvestor. Format loosely follows [Keep a Changelog](https://keepachangelog.com/) and uses semantic-ish dating since we're pre-1.0.

## [Unreleased] — 2026-04-10

### Added
- `docs/LEARNINGS.md` — institutional memory: do's, don'ts, gotchas, decisions, what broke and how it was fixed, constraints, patterns that work
- `docs/ARCHITECTURE.md` — full system architecture, service responsibilities, data flow, schema overview, tech stack rationale
- `docs/DEPLOYMENT.md` — Railway + Vercel deployment guide, including the GraphQL workaround for the broken Railway CLI auth
- `docs/CLI.md` — full `fesi` CLI command reference with workflows
- `docs/DECISION_FRAMEWORK.md` — canonical version of the decision framework (also rendered at `/framework` in the web app)
- `CHANGELOG.md` (this file)

### Fixed
- **CRITICAL:** SAVEPOINT pattern — `except IntegrityError` was caught inside `with conn.begin_nested()`, poisoning Postgres transactions. Moved exception handling outside the `with` block in `raw_items.py`, `prices.py`, `outcomes.py`.
- **CRITICAL:** Postgres dialect — `postgresql://` URLs defaulted to psycopg2 (not installed). Added `_normalize_url` rewrite to `postgresql+psycopg://` for psycopg v3.
- **Pipeline resilience** — wrapped each candidate/decision/digest phase in `conn.begin_nested()` so one failure doesn't kill the whole run.
- **Scheduler healthcheck** — removed `healthcheckPath` from `railway.toml` (applied to all services including the non-HTTP scheduler). Set per-service via GraphQL.

### Changed
- README.md — full rewrite to reflect Phase 1 + Phase 2 ship state (was still showing "Phase 0")

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
