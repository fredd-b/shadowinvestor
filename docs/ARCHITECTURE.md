# Architecture

ShadowInvestor is a personal catalyst-driven trading signal system. This doc explains the moving parts and how they connect.

## High-level diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                            DATA SOURCES                                │
│   SEC EDGAR · FDA OpenFDA · ClinicalTrials.gov v2 · RSS wires          │
│   Perplexity web search (sectors + custom topics + per-ticker daily)   │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │ httpx + retries + rate limits
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          INGEST LAYER                                  │
│  src/fesi/ingest/{sec_edgar,fda_openfda,clinicaltrials,wires,perplexity}.py │
│  Each adapter: fetch → list[RawItem] → store/raw_items.py              │
│  Dedup by (source, source_id) UNIQUE + content_hash                    │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       INTELLIGENCE LAYER                               │
│  normalize.py    — fuzzy-title dedup at 0.85 similarity, group items   │
│  llm.py          — Claude API OR deterministic fallback (no key needed)│
│  classifier.py   — assign catalyst_type from 28-type taxonomy          │
│  scorer.py       — assign impact (1-5) × probability (1-5)             │
│  cross_ref.py    — corroboration boost: 1.0×/1.15×/1.30×               │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                                 │
│  src/fesi/store/{tickers,raw_items,signals,decisions,prices,           │
│                  outcomes,digests}.py                                  │
│  SQLAlchemy 2.0 core. SQLite locally, Postgres on Railway prod.        │
│  Schema in store/schema.py — single source of truth for both backends. │
│  Every signal row stores a frozen ML feature vector at creation time.  │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         DECISION LAYER                                 │
│  decision/engine.py    — buy/no_buy with full reasoning                │
│  decision/sizing.py    — conviction-scaled fixed-risk position sizing  │
│  decision/risk_gates.py — 4 gates: position size / concurrent /        │
│                            sector concentration / circuit breaker      │
│  Mode: shadow (default) | paper | live (gated by env var)              │
└─────────┬──────────────────────────────────────────┬───────────────────┘
          │                                          │
          ▼                                          ▼
┌──────────────────────────┐    ┌────────────────────────────────────────┐
│  EXECUTION (shadow)      │    │              DIGEST                    │
│  execute/shadow.py       │    │  digest/render.py — markdown matching  │
│  Virtual fills →         │    │    Fred's Perplexity prompt format     │
│  trades table            │    │  digest/notify.py — Pushover + Telegram│
│                          │    │    + always-on file output             │
│  Phase 4: ibkr.py        │    └────────────┬───────────────────────────┘
│  (paper / live)          │                 │
└──────────────────────────┘                 ▼
                                  ┌─────────────────────────┐
                                  │  Pushover (push iOS)    │
                                  │  Telegram bot           │
                                  │  logs/digests/*.md      │
                                  └─────────────────────────┘

       ┌─────────────────────────────────────────────────────────┐
       │                    SCHEDULER                            │
       │  ops/scheduler.py — APScheduler                         │
       │  5 daily scans in Asia/Dubai timezone:                  │
       │    15:00, 18:00, 22:00 (silent), 02:00 (silent), 08:00  │
       │  + outcomes update job at 09:00                         │
       │  Each job = full pipeline cycle                         │
       └─────────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────────┐
       │                  FASTAPI HTTP LAYER                     │
       │  src/fesi/api/{main,routes,schemas}.py                  │
       │  31 routes — exposes the DB to the Next.js frontend     │
       │  Bearer-token auth via API_TOKEN env var                │
       │  CORS env-var driven                                    │
       └─────────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────────┐
       │                  NEXT.JS FRONTEND                       │
       │  web/ — Next.js 16 + Server Components                  │
       │  12 pages: signals, portfolio, tickers, sources, digests│
       │    framework, admin, research, signal/[id],             │
       │    ticker/[symbol], digest/[id], login                  │
       │  Site password gate via web/src/proxy.ts                │
       │  Hosted on Vercel                                       │
       └─────────────────────────────────────────────────────────┘
```

## Service responsibilities

### `src/fesi/` — the Python backend (one package, multiple roles)

| Module | Responsibility |
|---|---|
| `cli.py` | `fesi` click CLI: init-db, status, ingest, prices, run-pipeline, schedule, api, digest |
| `config.py` | Loads `config/*.yaml`, env vars via pydantic-settings, validation models |
| `db.py` | SQLAlchemy engine, `connect()` context manager, `init_db()` (idempotent schema bootstrap) |
| `logging.py` | structlog setup |
| `store/schema.py` | Single-source-of-truth Table definitions; cross-dialect (SQLite + Postgres) |
| `store/*.py` | Pure-function CRUD per table (`tickers`, `raw_items`, `signals`, `decisions`, `prices`, `outcomes`, `digests`, `positions`, `research_topics`, `user_actions`) |
| `ingest/base.py` | `IngestAdapter` ABC + `RawItem` dataclass |
| `ingest/http.py` | Shared httpx client with retries, rate limits, SEC-friendly UA |
| `ingest/{sec_edgar,fda_openfda,clinicaltrials,wires,perplexity}.py` | One adapter per source. Perplexity does sector queries + custom topics + per-ticker daily research. |
| `analysis/ta.py` | Technical analysis: SMA(20/50/200), RSI(14), trend detection. Pure Python. |
| `intelligence/llm.py` | Claude API (primary in prod) + deterministic fallback for `classify()` and `score()` |
| `intelligence/normalize.py` | Fuzzy-title dedup → `CandidateSignal` groups |
| `intelligence/classifier.py` | Public interface (thin wrapper around llm.py) |
| `intelligence/scorer.py` | Public interface |
| `intelligence/cross_ref.py` | Multi-source corroboration boost |
| `decision/engine.py` | `make_decision()` — buy/no_buy with full reasoning |
| `decision/sizing.py` | Conviction-scaled fixed-risk position sizing |
| `decision/risk_gates.py` | The 4 hard gates |
| `execute/shadow.py` | Virtual fills → `trades` table (Phase 4 will add `ibkr.py`) |
| `digest/render.py` | Markdown digest in Fred's Perplexity format |
| `digest/notify.py` | Pushover + Telegram + always-on file output |
| `ops/pipeline.py` | End-to-end orchestrator: ingest → normalize → score → decide → digest → notify |
| `ops/scheduler.py` | APScheduler with 5 daily jobs in Asia/Dubai |
| `ops/dashboard.py` | Streamlit dashboard (legacy local dev tool, superseded by Next.js for prod) |
| `api/main.py` | FastAPI app, CORS, bearer-token auth dependency |
| `api/routes.py` | All 31 routes |
| `api/schemas.py` | Pydantic response models (mirror `web/src/lib/types.ts`) |
| `ml/` | Phase 3 — feature extraction + model training (placeholder) |
| `migrations/` | Removed in Phase 2 — schema is now SQLAlchemy `metadata.create_all()` |

### `web/` — the Next.js 16 frontend

| Path | Purpose |
|---|---|
| `src/proxy.ts` | Site-wide password gate (Next.js 16: formerly `middleware.ts`) |
| `src/lib/api.ts` | Typed API client — Server Components call this to reach Railway |
| `src/lib/types.ts` | TypeScript types mirroring `src/fesi/api/schemas.py` |
| `src/lib/format.ts` | Shared display formatters (`formatTimestamp`, `formatUsd`, `formatPrice`, `formatCount`) |
| `src/components/Nav.tsx` | Top navigation |
| `src/components/StatRow.tsx` | Reusable `StatRow` (flex) and `StatTile` (grid) components |
| `src/app/layout.tsx` | Root layout (dark theme, antialiased) |
| `src/app/page.tsx` | `/` — recent signals with day/conviction filters |
| `src/app/signals/[id]/page.tsx` | Per-signal detail with ML feature vector + BUY/SKIP/WATCH recommendation banner |
| `src/app/portfolio/page.tsx` | Shadow portfolio: invested/unrealized/realized P&L, open positions with sell, closed trade journal |
| `src/app/tickers/page.tsx` | Watchlist grouped by sector with AddTickerForm + lifecycle status |
| `src/app/tickers/[symbol]/page.tsx` | Per-ticker drill-down + signal history + TA indicators (SMA/RSI) |
| `src/app/research/page.tsx` | Sector research, custom topics (TopicManager), per-ticker daily research |
| `src/app/sources/page.tsx` | Source health: active/inactive, items collected, last fetch |
| `src/app/digests/page.tsx` | Past digests list |
| `src/app/digests/[id]/page.tsx` | Single digest reader |
| `src/app/framework/page.tsx` | Decision framework documentation (mission, sectors, pipeline, risk gates) |
| `src/app/admin/page.tsx` | One-click admin: system status, stats, "Run pipeline" button, risk policy |
| `src/app/admin/RunPipelineButton.tsx` | Client component — POSTs to `/api/admin/run-pipeline` |
| `src/app/research/TopicManager.tsx` | Client component — CRUD for custom research topics (add/run/delete) |
| `src/components/SignalActionButtons.tsx` | Client component — invest/skip/watch buttons on signals |
| `src/components/SellButton.tsx` | Client component — sell (full/partial) with confirmation |
| `src/components/AddTickerForm.tsx` | Client component — add ticker to watchlist from UI |
| `src/app/api/auth/route.ts` | Server-side password validation, sets `shadow_auth` cookie |
| `src/app/api/admin/run-pipeline/route.ts` | Server-side proxy to Railway's `POST /api/pipeline/run` |
| `src/app/api/signals/[id]/action/route.ts` | Proxy for signal invest/skip/watch actions |
| `src/app/api/positions/[id]/sell/route.ts` | Proxy for position sell |
| `src/app/api/research/run/route.ts` | Proxy for manual research trigger |
| `src/app/api/research/topics/route.ts` | Proxy for custom topics CRUD |
| `src/app/api/research/topics/[id]/route.ts` | Proxy for topic update/delete |
| `src/app/api/research/topics/[id]/run/route.ts` | Proxy for manual topic run |
| `src/app/api/tickers/route.ts` | Proxy for add ticker |
| `src/app/login/page.tsx` | Password entry (Suspense-wrapped because of `useSearchParams`) |

### `scripts/` — one-shot operational scripts

| File | Purpose |
|---|---|
| `railway_deploy.py` | Provisions the Railway stack via GraphQL (bypasses the buggy CLI) |
| `wire_vercel.py` | Updates Vercel env vars to point at Railway, redeploys |
| `show_buys.py` | Local debug — prints all shadow buy decisions with full reasoning |

### `config/` — runtime configuration (YAML, validated by Pydantic)

| File | Contents |
|---|---|
| `sectors.yaml` | The 6 sectors: biotech_pharma, china_biotech_us_pipeline, ai_infrastructure, crypto_to_ai_pivot, commodities_critical_minerals, binary_event_other |
| `catalysts.yaml` | 28 catalyst types with sectors, typical impact, direction, patterns |
| `risk.yaml` | Hard risk policy: $2K/trade, $10K/month, 4 gates |
| `sources.yaml` | 16 data sources (6 active, 10 paid/social to enable later) |
| `watchlist.yaml` | 19+ tickers with thesis, alert thresholds, aliases |

## Data flow (one pipeline cycle)

```
1. ops/pipeline.py::run_pipeline(run_label=...) called by scheduler or `fesi run-pipeline`
2. For each adapter in [sec_edgar, fda_openfda, clinicaltrials, wires, perplexity]:
     adapter.fetch() → list[RawItem]
     store/raw_items.insert_raw_items(items)  # SAVEPOINT-wrapped, IntegrityError = dedup
   THEN: perplexity.fetch_custom_topics(topics_due_for_run)  # user-created research topics
   THEN: if run_label == "morning_catchup":
         perplexity.fetch_ticker_research(invested_and_considering_tickers)
3. store/raw_items.get_unprocessed_raw_items(since)
     → JOIN raw_items LEFT JOIN raw_items_signals — items not yet linked to a signal
4. intelligence/normalize.normalize(items, similarity_threshold=0.85)
     → list[CandidateSignal] (each merges 1+ raw_items by fuzzy title match)
5. For each candidate:
     classify(title, body, source) → ClassificationResult (Claude or fallback)
     score(title, body, classification, catalyst) → ScoringResult
     compute_conviction(impact, prob, source_count, source_diversity, source_keys)
     resolve ticker via watchlist symbol/name/alias match
     store/signals.insert_signal(...)  # writes feature vector + populates raw_items_signals junction
     store/outcomes.upsert_outcome_stub(signal_id)
6. For each new signal:
     decision/engine.make_decision(conn, signal)
       — check conviction threshold (12.0, dropped to 10.0 for watchlist hits)
       — check_all() runs the 4 risk gates
       — sizing.plan_position() computes shares + stop + target
       — store/decisions.insert_decision(action='buy' or 'no_buy', full reasoning)
       — if buy: execute/shadow.execute_shadow_buy() → virtual fill in trades table
       — if buy: store/positions.open_position() → open position with entry price
6b. store/positions.update_all_unrealized(conn) — refresh unrealized P&L for all open positions
7. digest/render.render_digest(conn, signals=window_signals, ...)
     → markdown matching the Top 10 / Emerging / Watchlist / Follow-up / Portfolio format
     store/digests.insert_digest(...)
8. digest/notify.deliver_digest(markdown)
     → file (always) → Pushover (if key) → Telegram (if key)
```

## Tech stack — what and why

### Backend
- **Python 3.12+** — required by SQLAlchemy 2.0 modern features and `from __future__ import annotations` patterns we use throughout.
- **SQLAlchemy 2.0 core** (not ORM) — cross-DB SQL via `text()` with named parameters. We use Table definitions in `schema.py` for `metadata.create_all()` only; queries are raw SQL because the codebase is small enough that ORM overhead isn't worth it.
- **psycopg v3** — Postgres driver. Strict about `postgresql://` not `postgres://` URLs.
- **FastAPI + uvicorn** — HTTP layer. Bearer-token auth via `python-jose`.
- **APScheduler** — in-process cron. Configured for `Asia/Dubai`.
- **httpx + tenacity** — HTTP client with exponential backoff. Used by all ingest adapters.
- **Anthropic SDK** — Claude API for the classifier/scorer. Optional; falls back to deterministic pattern matching.
- **yfinance** — Free OHLCV. We use `Ticker.history()` not `download()` (see LEARNINGS.md).
- **structlog** — JSON-friendly structured logging.
- **click** — CLI framework.
- **pydantic v2 + pydantic-settings** — config validation.
- **xgboost / lightgbm / scikit-learn** — Phase 3 ML training (not yet active).

### Frontend
- **Next.js 16.2.3 (App Router)** — Server Components by default. **Note:** middleware was renamed to `proxy.ts` in v16. See `web/AGENTS.md` for the warning about API differences from Next.js 15.
- **React 19.2** — comes with Next.js 16.
- **Tailwind CSS 4** — utility-first styling. Dark theme via `className="dark"` on `<html>`.
- **TypeScript** — strict mode, types mirror Pydantic schemas.

### Infrastructure
- **Railway** — backend hosting. Postgres + 2 services (api + scheduler) sharing one Docker image.
- **Vercel** — frontend hosting. Next.js production deploys.
- **Docker** — multi-arch Python 3.12 slim base for the Railway image.
- **GitHub** — source of truth, public repo (necessary for Railway to clone without OAuth app setup).
- **uv** — Python toolchain manager. Installs Python 3.12, manages venvs.

### Notification
- **Pushover** — iOS push for urgent alerts. ~$5 one-time license.
- **Telegram bot** — full digest delivery to a private chat.

### Broker (Phase 4)
- **Interactive Brokers** — DFSA Dubai branch. Verified for UAE residents. Free TWS / Web / REST APIs. 160+ markets.

## Mode lifecycle

```
shadow ──manual flag──> paper ──manual flag──> live
  (default)              (Phase 4 target)        (gated)
```

- **`shadow`** — every decision is journaled; no broker contacted. The default. Used to accumulate the forward backtest.
- **`paper`** — decisions sent to IBKR's paper account. Phase 4 target.
- **`live`** — decisions hit the live IBKR account. Gated behind manual env-var flip. First 10 live trades require manual approval.

The `MODE` env var is the source of truth. Default is `shadow`.

## Database schema overview

14 tables, defined in `src/fesi/store/schema.py`:

| Table | Purpose | Key columns |
|---|---|---|
| `raw_items` | Every fetched item, before normalization | `(source, source_id) UNIQUE`, `content_hash` |
| `tickers` | Master list of tradeable instruments | `(symbol, exchange) UNIQUE`, `is_watchlist`, `aliases` (in YAML, not column) |
| `signals` | Normalized + scored events | `catalyst_type`, `conviction_score`, 12 ML feature columns, `raw_item_ids` (JSON) |
| `raw_items_signals` | Junction table — replaces SQLite-specific `json_each` query | `(raw_item_id, signal_id)` |
| `decisions` | Every shadow/paper/live decision with full reasoning | `mode`, `action`, 4 `passed_*_check` bools |
| `trades` | Virtual fills (shadow) or real fills (paper/live) | `decision_id`, `mode`, `status` |
| `outcomes` | T+1, T+5, T+30, T+90 returns + max draw | joined by `signal_id` |
| `prices` | Daily OHLCV cache | `(ticker_id, date) UNIQUE` |
| `embeddings` | Text vectors for semantic dedup (Phase 2+) | `text_hash`, `vector` BLOB |
| `catalyst_priors` | Historical baselines per catalyst type (Phase 4) | `hit_rate`, `avg_return_*` |
| `digests` | Journal of every digest delivered | `markdown_body` |
| `user_actions` | Append-only audit trail of Fred's actions | `action_type`, `target_type`, `target_id`, `note` |
| `positions` | Open/closed positions with P&L | `entry_price`, `exit_price`, `shares_held`, `realized_pnl_usd`, `unrealized_pnl_usd` |
| `research_topics` | User-created research queries (max 8) | `name`, `query_template`, `schedule` (daily/every_run), `sector_hint` |

`metadata.create_all(engine)` is idempotent and dialect-aware. The same schema works in SQLite (dev) and Postgres (Railway prod).

## Key design principles

1. **Local code IS prod code.** Same Python everywhere. Phase 1 ran on Mac with SQLite + APScheduler before any cloud touch.
2. **ML-ready from day 1.** Schema captures feature vectors at signal creation time, point-in-time correct. Phase 3 training reads straight from the DB.
3. **Shadow Portfolio first.** No historical news backtest. Every decision is journaled; the journal IS the backtest after 30+ days.
4. **Risk policy enforced in code.** The 4 gates are not promises — they're functions that return `(passed, reason)` and gate every buy.
5. **LLM is optional.** Deterministic fallback means the pipeline runs end-to-end without an Anthropic key.
6. **Two services on Railway, one image.** Crash isolation + scale-to-zero economics. Same Docker image, different `startCommand` per service.
