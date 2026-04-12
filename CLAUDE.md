# CLAUDE.md — ShadowInvestor

This file is loaded at the start of every Claude Code session. It contains the critical rules, patterns, and context needed to work on this project without re-deriving anything.

---

## What this is

A **personal catalyst-driven trading signal system** that industrializes a manual Perplexity-based research workflow into a 24/7 multi-source pipeline. Runs in **shadow mode** (journaling would-have-bought decisions) with eventual live execution via Interactive Brokers.

- **Owner:** Fred (solo personal investor, UAE-based)
- **Status:** Phase 3.1 deployed — production live
- **Frontend:** https://shadowinvestor.vercel.app
- **Backend:** https://shadowinvestor-api-production.up.railway.app
- **Repo:** https://github.com/fredd-b/shadowinvestor (public)

---

## Tech stack

- **Backend:** Python 3.12+, SQLAlchemy 2.0 core (no ORM), FastAPI, APScheduler, psycopg v3
- **Frontend:** Next.js 16 (App Router) + React 19 + Tailwind CSS 4
- **DB:** SQLite (local dev) / Postgres (Railway prod) — 14 tables in `store/schema.py`
- **LLM:** Claude (primary classifier in prod) + deterministic fallback (no key needed)
- **Discovery:** Perplexity API (sonar model) — sectors + custom topics + per-ticker daily
- **Infra:** Railway (API + scheduler + Postgres), Vercel (frontend), Docker

---

## Hard rules — DO NOT VIOLATE

### Database
- **SAVEPOINT pattern**: `except IntegrityError` must be OUTSIDE `with conn.begin_nested()`. Inside = Postgres RELEASE on aborted savepoint = entire connection poisoned. See `store/raw_items.py`.
- **Use `text()` with named params** for all SQL. Never raw f-strings.
- **Never mock the DB in tests.** Use real SQLite in `tmp_path` (see `tests/conftest.py::tmp_db`).

### Deployment
- **Always `railway up --service X`**, never `railway redeploy` (reuses cached image, ignores new code).
- **No `startCommand` in `railway.toml`** — it snapshots into every deploy and overrides API settings.
- **No `healthcheckPath` in `railway.toml`** — applies to all services including the non-HTTP scheduler.
- **Dockerfile CMD is exec-form** `["fesi", "api", "run"]` — env vars read in Python, not shell.

### Frontend (Next.js 16)
- **`middleware.ts` is now `proxy.ts`** and exports `proxy()` not `middleware()`.
- **`params` and `searchParams` are Promises** — must `await` in Server Components.
- **`useSearchParams()` requires `<Suspense>` wrapper** or the build fails.
- **Client mutations go through Next.js API proxy routes** — never call Railway directly from browser.

### Pipeline
- **Every signal generates a decision (buy or no_buy)** with full reasoning. Never "skip" without logging.
- **LLM fallback must always work.** Don't add code paths that require Claude to be set.
- **Use `yf.Ticker(symbol).history()`** not `yf.download()` — multi-level column bug.

### Risk policy (non-negotiable)
- Max $2,000 per trade, max $10,000 monthly deployment, max 6 concurrent positions
- Cash-only, no margin, no options, no shorts
- `MODE=shadow` is the default. Never auto-flip to live.
- All 4 risk gates must pass for every buy decision.

---

## Key patterns

### Store module pattern
One module per table. Pure functions taking `Connection` as first arg. Dedup inserts use:
```python
try:
    with conn.begin_nested():
        conn.execute(text("INSERT ..."), params)
except IntegrityError:
    pass  # exception OUTSIDE the with
```

### Ingest adapter pattern
Inherits `IngestAdapter`, exposes `source_key`, implements `fetch() -> list[RawItem]`. Self-disables if API key missing.

### Server Component data fetching
`async function Page({ params })` with `params: Promise<...>`. Use `Promise.all` for parallel fetches. `export const dynamic = "force-dynamic"` for live data.

### Client-side mutations (BFF proxy)
`"use client"` component → `fetch("/api/...")` → Next.js route handler → `lib/api.ts` → Railway FastAPI.

### run_label plumbing
Scheduler passes label (e.g. `"morning_catchup"`) → pipeline → adapter. Custom topics check it for scheduling. Per-ticker research only fires on `morning_catchup`.

---

## Codebase overview

```
src/fesi/           # Python backend (~7.2k LOC, 51 files)
  store/schema.py   # 14 tables — single source of truth
  store/*.py        # one module per table (12 modules)
  ingest/           # 5 adapters: SEC, FDA, CT.gov, wires, Perplexity
  intelligence/     # Claude + deterministic fallback classifier/scorer
  decision/         # engine + sizing + 4 risk gates
  analysis/ta.py    # SMA(20/50/200), RSI(14), trend — pure Python
  ops/pipeline.py   # end-to-end orchestrator
  ops/scheduler.py  # APScheduler, 5 daily scans, Asia/Dubai TZ
  api/routes.py     # 31 FastAPI endpoints
web/                # Next.js 16 frontend (12 pages, 9 proxy routes)
config/             # YAML configs (sectors, catalysts, risk, sources, watchlist)
tests/              # 48 tests
```

---

## Deploy commands

```bash
# Backend (Railway)
railway up --service shadowinvestor-api
railway up --service shadowinvestor-scheduler

# Frontend (Vercel)
cd web && vercel deploy --prod --yes

# Local dev
fesi api run --port 8765           # Terminal A
cd web && npm run dev              # Terminal B → http://localhost:3001
```

---

## Critical docs (read order)

1. `docs/LEARNINGS.md` — institutional memory, do's/don'ts, what broke
2. `docs/ARCHITECTURE.md` — diagram, service responsibilities, data flow
3. `docs/DECISION_FRAMEWORK.md` — trading mission, sectors, 7-step pipeline, risk gates
4. `docs/CLI.md` — `fesi` command reference
5. `docs/DEPLOYMENT.md` — Railway + Vercel deploy guide

---

## Fred's working preferences

- **Plans first, then code.** Enter plan mode for anything non-trivial.
- **Build UI for everything.** If it's not in the dashboard, it doesn't exist.
- **Test in production.** Local SQLite tests don't catch Postgres-specific bugs.
- **Deep dives when asked.** "GREAT PLANNING REQUIRED" means thorough comparison tables.
- **Every change must ladder to P&L.** Push back on features that don't help Fred make money.
