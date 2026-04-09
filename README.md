# FESI — Finance Early Signals & Investor

> Personal catalyst-driven trading signal system. Industrializes a manual catalyst-scanning workflow into a 24/7 multi-source pipeline that runs in **Shadow Portfolio** mode (would-have-bought decisions journaled in real time) and eventually executes live via Interactive Brokers under strict risk rules.

**Status:** Phase 0 — foundation. See `PHASE_1_BUILD.md` for the next 16 tickets.

---

## Mission

Make money on personal trades by detecting high-conviction, niche-sector catalysts faster and more systematically than manual reading, with eventual semi-automated execution through Interactive Brokers (DFSA Dubai branch).

**Categories monitored** (see `config/sectors.yaml`):

1. **Biotech / Pharma** (global) — FDA decisions, pivotal trial readouts, licensing deals
2. **China Biotech → FDA Pipeline** (dedicated edge area) — Chinese-domiciled biotechs tracking toward US FDA submission/approval
3. **AI Infrastructure** — GPU cloud, data center REITs, networking/optics/semis
4. **Crypto Miners Pivoting to AI/HPC** — long-term hosting contracts, GPU procurements
5. **Commodities — Uranium / Gold / Critical Minerals** — mine milestones, offtakes, reserve upgrades
6. **Other Binary-Catalyst Sectors** — defense awards, large buybacks, guidance changes

---

## Core principles

1. **Shadow Portfolio first.** No historical news backtest. Every signal generates a virtual decision in real time, journaled with full feature vector. After 30+ days of accumulation, the journal IS our backtest AND our ML training set.
2. **ML-ready from day 1.** The `signals` schema captures complete feature vectors at signal creation time (point-in-time correct). Phase 3 trains gradient-boosted models on accumulated decisions vs realized outcomes.
3. **Live trading is gated.** All trades start in `MODE=shadow`. Flipping to `live` is a manual env flag, not a code change. First 10 live trades require manual approval.
4. **Risk policy is enforced in code, not in promises.** Max $2K per trade, max $10K monthly deployment, max 6 concurrent positions, daily/weekly loss circuit breakers. See `config/risk.yaml`.
5. **Local code IS prod code.** Same Python everywhere. Phase 1 runs on Mac with SQLite + APScheduler; Phase 2+ migrates to Docker on Railway with Postgres + Vercel for the dashboard, RunPod for GPU training.

---

## Stack

| Layer | Phase 0/1 (local) | Phase 2+ (prod) |
|---|---|---|
| Backend | Python 3.12 + click CLI | Same code → Docker → Railway |
| DB | SQLite (`./data/fesi.db`) | Postgres (Railway managed) |
| Scheduler | APScheduler in-process | Same, in container |
| LLM | Anthropic Claude (classify + score) + Perplexity (live web grounding) | Same |
| Embeddings | Voyage 3 | Same |
| Market data | yfinance (free) → Polygon ($29/mo) | Same |
| Notifications | Pushover (iOS push) + Telegram bot | Same |
| Dashboard | Streamlit @ `localhost:8501` | Next.js → Vercel |
| Broker | IBKR paper account (Web API) | IBKR live, gated by env flag |
| ML training | scikit-learn / XGBoost / LightGBM on Mac CPU | RunPod GPU pod |

---

## Repository layout

```
.
├── config/                       # YAML config — sectors, catalysts, risk, sources, watchlist
│   ├── sectors.yaml
│   ├── catalysts.yaml
│   ├── risk.yaml
│   ├── sources.yaml
│   └── watchlist.yaml
├── data/                         # SQLite db + caches (gitignored)
├── models/                       # Trained ML model artifacts (gitignored)
├── logs/                         # Runtime logs (gitignored)
├── src/fesi/
│   ├── __init__.py               # version
│   ├── cli.py                    # `fesi` CLI entrypoint
│   ├── config.py                 # YAML loading + Pydantic validation + env settings
│   ├── db.py                     # SQLite connection + migration runner
│   ├── migrations/               # raw SQL files, applied in order
│   │   └── 001_initial_schema.sql
│   ├── ingest/                   # one module per data source
│   │   └── base.py               # IngestAdapter ABC + RawItem dataclass
│   ├── intelligence/             # normalize, classify, score, cross-reference
│   ├── store/                    # tickers, prices, signals, decisions, outcomes
│   ├── digest/                   # markdown render + Pushover/Telegram delivery
│   ├── decision/                 # decision engine + risk rules + sizing
│   ├── execute/                  # broker adapters (shadow/paper/live)
│   ├── ml/                       # feature extraction + model training (Phase 3)
│   └── ops/                      # scheduler, dashboard, journal CLI
├── tests/
│   └── test_smoke.py
├── pyproject.toml
├── Makefile
├── .env.example
├── PHASE_1_BUILD.md              # next 16 tickets
└── README.md
```

---

## Setup (local)

```bash
# 1. Install uv (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create venv and install
make install
source .venv/bin/activate

# 3. Copy env template, fill in API keys
cp .env.example .env
# edit .env

# 4. Initialize DB + validate configs
make init
make check

# 5. Run tests
make test
```

---

## CLI commands (Phase 0)

| Command | Purpose |
|---|---|
| `fesi --version` | Print version |
| `fesi status` | Print runtime settings (mode, env, DB, timezone) |
| `fesi init-db` | Apply migrations, create SQLite DB |
| `fesi config-check` | Load and validate all YAML configs |

Phase 1 will add: `fesi ingest <source>`, `fesi prices fetch <symbol>`, `fesi schedule run`, `fesi tickers list`.

---

## Risk policy summary (`config/risk.yaml`)

| Setting | Value |
|---|---|
| Max per trade | $2,000 |
| Max concurrent positions | 6 |
| Max per sector | 40% of deployed capital |
| Max per ticker (lifetime) | $4,000 |
| Monthly deployment cap | $10,000 |
| Cash reserve | 20% |
| Daily loss halt | -10% |
| Weekly loss halt | -15% |
| Consecutive loss review | 4 in a row |
| Account | Cash only — no margin, no options, no shorts |
| Default mode | `shadow` |
| First N live trades | Require manual approval (N=10) |

---

## Decision-making documentation

Architecture decisions, mission, constraints, and the reasoning behind each are stored in long-term memory at `~/.claude/projects/-Users-fred-FinanceEarlySignalsAndInvestor/memory/`. Read those files to understand WHY anything is the way it is.

---

## Roadmap

| Phase | Status | Goal |
|---|---|---|
| **0 — Foundation** | done | Schema, configs, scaffold, broker decision |
| **1 — Signal pipeline + Shadow Portfolio** | next | 16 tickets — see `PHASE_1_BUILD.md` |
| **2 — Watchlist intelligence + cross-ref** | planned | Per-ticker monitoring, supply-chain links, China biotech full wiring |
| **3 — ML calibration loop** | planned | GBM scorer trained on accumulated shadow data |
| **4 — Gated live execution via IBKR** | gated | Flip kill switch, hard guardrails, manual approval first 10 trades |
