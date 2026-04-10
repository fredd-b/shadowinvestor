# ShadowInvestor

> Personal catalyst-driven trading signal system. Industrializes a manual catalyst-scanning workflow into a 24/7 multi-source pipeline that runs in **Shadow Portfolio** mode (would-have-bought decisions journaled in real time) and eventually executes live via Interactive Brokers under strict risk rules.

| | |
|---|---|
| **Status** | Phase 2 deployed — backend + frontend live in production |
| **Frontend** | https://shadowinvestor.vercel.app |
| **Backend API** | https://shadowinvestor-api-production.up.railway.app |
| **Repo** | https://github.com/fredd-b/shadowinvestor (public) |
| **Mode** | `shadow` (no live broker contact) |
| **Tests** | 32 passing |

---

## Mission

Make money on personal trades by detecting high-conviction, niche-sector catalysts faster and more systematically than reading news manually, with eventual semi-automated execution through Interactive Brokers (DFSA Dubai branch).

**Stretch target:** +50% blended annual · **Realistic-but-good:** 20–30% · **Kill threshold:** below +10%.

**Categories monitored** (see `config/sectors.yaml`):

1. **Biotech / Pharma** (global) — FDA decisions, pivotal trial readouts, licensing deals
2. **China Biotech → FDA Pipeline** (dedicated edge area) — Chinese-domiciled biotechs tracking toward US FDA submission/approval
3. **AI Infrastructure** — GPU cloud, data center REITs, networking/optics/semis
4. **Crypto Miners Pivoting to AI/HPC** — long-term hosting contracts, GPU procurements
5. **Commodities — Uranium / Gold / Critical Minerals** — mine milestones, offtakes, reserve upgrades
6. **Other Binary-Catalyst Sectors** — defense awards, large buybacks, guidance changes

See [`docs/DECISION_FRAMEWORK.md`](docs/DECISION_FRAMEWORK.md) for the full mission, sectors, pipeline steps, risk gates, and review process.

---

## Core principles

1. **Shadow Portfolio first.** No historical news backtest. Every signal generates a virtual decision in real time, journaled with full feature vector. After 30+ days of accumulation, the journal IS our backtest AND our ML training set.
2. **ML-ready from day 1.** The `signals` schema captures complete feature vectors at signal creation time (point-in-time correct). Phase 3 trains gradient-boosted models on accumulated decisions vs realized outcomes.
3. **Live trading is gated.** All trades start in `MODE=shadow`. Flipping to `live` is a manual env flag, not a code change. First 10 live trades require manual approval.
4. **Risk policy is enforced in code, not in promises.** Max $2K per trade, max $10K monthly deployment, max 6 concurrent positions, daily/weekly loss circuit breakers. See `config/risk.yaml`.
5. **Local code IS prod code.** Same Python everywhere. Local dev runs on SQLite + APScheduler; production runs on Postgres + Railway with Vercel for the frontend, RunPod for GPU training (Phase 3).
6. **LLM is optional.** Deterministic fallback classifier means the entire pipeline runs end-to-end without an Anthropic key.

---

## Tech stack

| Layer | Tool | Why |
|---|---|---|
| Backend language | Python 3.12+ | SQLAlchemy 2.0 + pydantic v2 features |
| HTTP | FastAPI + uvicorn | bearer-token-authenticated REST API for the frontend |
| DB | SQLite (local) / Postgres (Railway prod) | SQLAlchemy core abstracts both via `text()` |
| ORM | SQLAlchemy 2.0 core (no ORM) | cross-DB SQL via named params; schema in `store/schema.py` |
| Postgres driver | psycopg v3 | strict about `postgresql://` not `postgres://` |
| Scheduler | APScheduler | in-process cron, configured for `Asia/Dubai` |
| HTTP client | httpx + tenacity | retries with exponential backoff |
| LLM | Anthropic Claude (optional) | with deterministic fallback so no key needed |
| Market data | yfinance | use `Ticker.history()` not `download()` — see LEARNINGS |
| CLI | click | `fesi` command tree |
| Logging | structlog | JSON-friendly structured logs |
| Frontend | Next.js 16 (App Router) + React 19 | Server Components, no client data fetching |
| UI styling | Tailwind CSS 4 | utility-first, dark theme |
| Notifications | Pushover (push) + Telegram bot | with always-on file fallback |
| Backend host | Railway (api + scheduler + Postgres) | 2 services share one Docker image |
| Frontend host | Vercel | Next.js production deploys |
| Broker (Phase 4) | Interactive Brokers (DFSA Dubai branch) | UAE-resident-friendly, 160+ markets |
| ML training (Phase 3) | scikit-learn / XGBoost / LightGBM on RunPod | gradient-boosted scoring on accumulated shadow data |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full architecture and service responsibilities.

---

## Repository layout

```
.
├── config/                       # YAML config (validated by Pydantic)
│   ├── sectors.yaml              #   6 sectors
│   ├── catalysts.yaml            #   28 catalyst types
│   ├── risk.yaml                 #   $2K/trade, $10K/mo, 4 gates
│   ├── sources.yaml              #   16 data sources
│   └── watchlist.yaml            #   19 seed tickers w/ thesis + aliases
├── data/                         # SQLite db + caches (gitignored)
├── logs/digests/                 # Markdown digests written by every pipeline run
├── docs/                         # 📖 documentation
│   ├── ARCHITECTURE.md           #   full system architecture
│   ├── CLI.md                    #   `fesi` CLI reference
│   ├── DEPLOYMENT.md             #   Railway + Vercel deploy guide
│   ├── DECISION_FRAMEWORK.md     #   mission, sectors, pipeline, risk gates
│   └── LEARNINGS.md              #   ⭐ institutional memory — read first
├── scripts/
│   ├── railway_deploy.py         # Railway provisioning via GraphQL (bypasses buggy CLI)
│   ├── wire_vercel.py            # Vercel env vars → Railway after deploy
│   └── show_buys.py              # Local: print all shadow buys with reasoning
├── src/fesi/
│   ├── cli.py                    # `fesi` click CLI
│   ├── config.py                 # YAML loading + Pydantic validation + Settings (env)
│   ├── db.py                     # SQLAlchemy engine + connect() + init_db()
│   ├── logging.py                # structlog setup
│   ├── store/
│   │   ├── schema.py             # ⭐ single source of truth for all 11 tables
│   │   ├── tickers.py            #   watchlist loader, symbol/alias resolver
│   │   ├── raw_items.py          #   insert + dedup + unprocessed query
│   │   ├── signals.py            #   insert with full feature vector
│   │   ├── decisions.py          #   shadow/paper/live decisions + sector exposure
│   │   ├── digests.py            #   journal of every digest
│   │   ├── prices.py             #   yfinance Ticker.history() cache
│   │   └── outcomes.py           #   T+1 / T+5 / T+30 / T+90 returns + max draw
│   ├── ingest/
│   │   ├── base.py               # IngestAdapter ABC + RawItem + content_hash
│   │   ├── http.py               # shared httpx client w/ retry, rate-limit, SEC UA
│   │   ├── sec_edgar.py          # 8-K/6-K via EDGAR submissions JSON, CIK cache
│   │   ├── fda_openfda.py        # drug submissions
│   │   ├── clinicaltrials.py     # CT.gov v2 (sponsor + China geo filters)
│   │   └── wires.py              # 5 RSS feeds, browser UA, keyword filter
│   ├── intelligence/
│   │   ├── llm.py                # Claude classifier+scorer + deterministic fallback
│   │   ├── classifier.py         # public interface
│   │   ├── scorer.py             # public interface
│   │   ├── normalize.py          # fuzzy-title dedup + cross-source grouping
│   │   └── cross_ref.py          # corroboration boost
│   ├── decision/
│   │   ├── engine.py             # buy/no_buy with full reasoning (watchlist boost)
│   │   ├── sizing.py             # conviction-scaled fixed-risk + stop/target
│   │   └── risk_gates.py         # the 4 hard gates
│   ├── execute/
│   │   └── shadow.py             # virtual fills (Phase 4 will add ibkr.py)
│   ├── digest/
│   │   ├── render.py             # markdown w/ Top10/Emerging/Watchlist/Follow-up/Portfolio
│   │   └── notify.py             # Pushover + Telegram + always-on file logging
│   ├── ops/
│   │   ├── pipeline.py           # end-to-end orchestrator
│   │   ├── scheduler.py          # APScheduler 5x/day in Asia/Dubai
│   │   └── dashboard.py          # local Streamlit dashboard (legacy)
│   ├── api/
│   │   ├── main.py               # FastAPI app, CORS, bearer auth
│   │   ├── routes.py             # 17 routes
│   │   └── schemas.py            # Pydantic response models (mirror web/src/lib/types.ts)
│   └── ml/                       # Phase 3 placeholder
├── tests/
│   ├── conftest.py               # tmp_db fixture, db_conn, raw item factories
│   ├── test_smoke.py             # config + schema (4 tests)
│   ├── test_normalize.py         # dedupe + fuzzy match (5 tests)
│   ├── test_classifier_fallback.py  # deterministic classifier (6 tests)
│   ├── test_cross_ref.py         # corroboration boost (4 tests)
│   ├── test_decision_engine.py   # buy/no_buy + sizing + gates (7 tests)
│   ├── test_digest_render.py     # markdown rendering (4 tests)
│   └── test_pipeline_e2e.py      # synthetic raw_items → digest (2 tests)
├── web/                          # Next.js 16 frontend (deployed to Vercel)
│   ├── src/proxy.ts              # password gate (Next 16: was middleware.ts)
│   ├── src/lib/api.ts            # typed API client → Railway
│   ├── src/lib/types.ts          # TS types mirroring api/schemas.py
│   ├── src/lib/format.ts         # shared display formatters
│   ├── src/components/Nav.tsx
│   ├── src/components/StatRow.tsx     # StatRow + StatTile
│   └── src/app/                  # 10 pages (signals, portfolio, tickers, sources,
│                                 #           digests, framework, admin, signal/[id],
│                                 #           ticker/[symbol], login)
├── Dockerfile                    # multi-arch Python 3.12 slim, exec-form CMD
├── railway.toml                  # Railway build config (NO startCommand — see LEARNINGS)
├── pyproject.toml
├── Makefile
├── .env.example
├── CHANGELOG.md
└── README.md (this file)
```

---

## Setup (local)

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12

# 2. Create venv and install
make install
source .venv/bin/activate

# 3. Copy env template, fill in API keys (all optional)
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY for Claude (else fallback runs); set PUSHOVER/TELEGRAM for alerts

# 4. Initialize DB + load watchlist + validate configs
make init       # = fesi init-db
make check      # = fesi config-check

# 5. Run tests
make test       # = pytest

# 6. Fetch prices for the watchlist (~30 sec for 19 tickers)
fesi prices fetch-watchlist --days 30

# 7. Run the pipeline once against real APIs (~60–120 sec)
fesi run-pipeline
fesi digest last      # see what was generated
```

To run the full local stack (FastAPI + Next.js dev):

```bash
# Terminal A:
fesi api run --port 8765

# Terminal B:
cd web
echo "API_BASE_URL=http://127.0.0.1:8765
API_TOKEN=
SITE_PASSWORD=test" > .env.local
npm install && npm run dev
# → http://localhost:3001/login → enter "test"
```

See [`docs/CLI.md`](docs/CLI.md) for the full command reference and workflows.

---

## Production deployment

Deployed via:
- **Vercel** for the Next.js frontend (https://shadowinvestor.vercel.app)
- **Railway** for the FastAPI backend + scheduler + Postgres
- **GitHub** for source (https://github.com/fredd-b/shadowinvestor)

To deploy from scratch (or update an existing deploy), see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). The deploy uses two scripts that bypass the broken Railway CLI auth flow:

```bash
python scripts/railway_deploy.py             # provisions Railway via GraphQL
python scripts/wire_vercel.py <api-url> <api-token>   # points Vercel at Railway
```

---

## Risk policy summary (`config/risk.yaml`)

| Setting | Value |
|---|---|
| Max per trade | $2,000 |
| Max concurrent positions | 6 |
| Max per sector | 40% of monthly cap |
| Max per ticker (lifetime) | $4,000 |
| Monthly deployment cap | $10,000 |
| Cash reserve | 20% |
| Daily loss halt | -10% |
| Weekly loss halt | -15% |
| Consecutive loss review | 4 in a row |
| Account | Cash only — no margin, no options, no shorts |
| Default mode | `shadow` |
| First N live trades | Require manual approval (N=10) |

See [`docs/DECISION_FRAMEWORK.md`](docs/DECISION_FRAMEWORK.md) for the full framework.

---

## Documentation

| File | Purpose |
|---|---|
| [`README.md`](README.md) | This file — overview, setup, layout |
| [`CHANGELOG.md`](CHANGELOG.md) | Per-phase history of changes |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full architecture diagram, service responsibilities, data flow, schema |
| [`docs/CLI.md`](docs/CLI.md) | `fesi` CLI command reference + common workflows |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Railway + Vercel deploy guide, troubleshooting |
| [`docs/DECISION_FRAMEWORK.md`](docs/DECISION_FRAMEWORK.md) | Mission, sectors, 7-step pipeline, 4 risk gates, mode lifecycle |
| [`docs/LEARNINGS.md`](docs/LEARNINGS.md) | ⭐ **Institutional memory** — do's, don'ts, gotchas, decisions, what broke and how it was fixed. **Read this before changing anything load-bearing.** |
| [`PHASE_1_BUILD.md`](PHASE_1_BUILD.md) | Phase 1 ticket plan (now done) — kept for historical reference |

Long-term context (architecture decisions, project history) also lives in `~/.claude/projects/-Users-fred-FinanceEarlySignalsAndInvestor/memory/`.

---

## Roadmap

| Phase | Status | Goal |
|---|---|---|
| **0 — Foundation** | ✅ done | Schema, configs, scaffold, broker decision |
| **1 — Signal pipeline + Shadow Portfolio** | ✅ done | Multi-source ingest, classifier, decision engine, digest, scheduler. 32 tests, first live run produced 5 shadow buys. |
| **2 — Production deployment** | ✅ done | SQLAlchemy abstraction, FastAPI HTTP layer, Next.js 16 frontend, Docker, Railway + Vercel deployed. |
| **2.5 — Code review + polish** | ✅ done | Triple-agent review pass, shared formatters/components, typed unions, fixed deploy bugs. |
| **3 — ML calibration loop** | ⏳ planned | GBM scorer trained on accumulated shadow data; A/B against LLM-only scoring |
| **4 — Gated live execution via IBKR** | ⏳ gated | IBKR adapter, kill switch, manual approval for first 10 trades |

---

## Critical reads before contributing

1. **[`docs/LEARNINGS.md`](docs/LEARNINGS.md)** — every entry represents at least an hour someone burned figuring something out. Don't repeat the mistakes.
2. **`web/AGENTS.md`** — Next.js 16 has breaking changes from your training data. Specifically: `middleware.ts` → `proxy.ts`, `params`/`searchParams` are Promises.
3. **`config/risk.yaml`** — these are hard constraints, not suggestions.
