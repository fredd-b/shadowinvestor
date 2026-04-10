# Phase 1 Build Plan

> **Status: ✅ SHIPPED 2026-04-09.** Kept as historical reference. See [`CHANGELOG.md`](CHANGELOG.md) for what actually landed.

> **Goal:** Multi-source ingest + LLM-scored intraday digest delivered to Fred's phone, every signal generates a shadow decision in DB. Target window: weeks 2–4 after Phase 0 (days 8–28).

## Phase 1 outcome

Full pipeline runs end-to-end against real APIs:
- 49 Python files, ~5k LOC
- 32 passing tests
- 4 ingest adapters wired (SEC EDGAR, FDA OpenFDA, ClinicalTrials.gov v2, RSS wires)
- LLM classifier with deterministic fallback
- Decision engine with 4 risk gates
- 5x daily scheduler in Asia/Dubai timezone
- Pushover + Telegram + file notification
- First live run produced **5 shadow buys**, $4,952 deployed across 2 sectors, 0 errors

## Conventions

- Each ticket was independently shippable
- Each had explicit acceptance criteria
- Tests required for any ticket touching the DB or LLM
- Order was roughly the order to build them — lower numbers first
- "DoD" = Definition of Done

---

## F1-01 — Finish DB bootstrap & migration runner
**Status:** Phase 0 created the initial schema and migration runner. This ticket finishes wiring it.
**What:**
- `fesi init-db` creates `data/fesi.db` and applies migration 001
- Idempotent (re-run does nothing)
- DB path resolves correctly even when CWD is not project root
**DoD:**
- `make init` works from a fresh checkout
- `tests/test_smoke.py::test_initial_migration_applies_cleanly` passes

---

## F1-02 — Watchlist loader → tickers table
**What:** On `fesi init-db`, load `config/watchlist.yaml` and upsert into `tickers` table. Set `is_watchlist=1`.
**DoD:**
- After `fesi init-db`, `SELECT COUNT(*) FROM tickers WHERE is_watchlist=1` matches watchlist length
- Re-running upserts (no duplicates)
- New CLI: `fesi tickers list` prints all watchlist tickers with sector + thesis

---

## F1-03 — Pricing layer (yfinance)
**What:** `fesi.store.prices` module that fetches OHLCV from yfinance and caches in `prices` table.
**DoD:**
- `fesi prices fetch <symbol>` pulls last 90 days of daily bars
- `fesi prices fetch --watchlist` fetches all watchlist tickers
- Idempotent (skip already-cached dates)
- Handles HK / TSX symbols (e.g. `1801.HK`, `NXE.TO`)
- Test that fetching twice for the same window inserts zero new rows the second time

---

## F1-04 — Ingest adapter: SEC EDGAR 8-K filings
**What:** First real ingestion adapter. Pull 8-K filings for watchlist tickers from SEC EDGAR REST API.
**DoD:**
- `fesi ingest sec-edgar` pulls last 48h of 8-Ks for watchlist tickers
- Stores to `raw_items` with `content_hash` for dedupe
- Re-running same window adds zero new rows
- Respects EDGAR's 10 req/sec rate limit and User-Agent requirement
- Includes a test that mocks the EDGAR HTTP layer

---

## F1-05 — Ingest adapter: FDA OpenFDA
**What:** Pull FDA approvals, AdCom decisions, NDA/BLA filings from OpenFDA API.
**DoD:**
- `fesi ingest fda-openfda` pulls last 48h of approvals/decisions
- Stores to `raw_items`
- Tagged with relevant ticker(s) when company name matches a watchlist entry
- Test with mocked HTTP

---

## F1-06 — Ingest adapter: ClinicalTrials.gov
**What:** Pull trial status changes for watchlist sponsors AND all China-sponsored trials.
**DoD:**
- `fesi ingest clinicaltrials` pulls last 48h of trial updates
- Filters to sponsor in watchlist OR sponsor country = China
- Stores to `raw_items`

---

## F1-07 — Ingest adapter: Press release wires (PR Newswire / GlobeNewswire / BusinessWire RSS)
**What:** RSS-based pull of biotech, energy, and AI press releases.
**DoD:**
- `fesi ingest wires` fetches all three wires
- Filters to keywords from `config/catalysts.yaml` patterns
- Stores to `raw_items`

---

## F1-08 — Normalizer + content-hash dedupe + cross-source grouping
**What:** `fesi.intelligence.normalize` module. Takes new `raw_items` and produces candidate signals — one row per unique event, even if reported by N sources.
**DoD:**
- Same headline from PR Newswire and BusinessWire produces ONE candidate signal with `feature_source_count=2` and `feature_source_diversity=2`
- Fuzzy title match (>0.85 similarity) treated as same event
- Outputs to a queue table or in-memory list for the classifier

---

## F1-09 — LLM classifier + scorer (Claude)
**What:** `fesi.intelligence.classifier` and `fesi.intelligence.scorer`. Uses Claude API to classify catalyst type, extract economics, assign impact / probability.
**DoD:**
- Each candidate signal becomes one `signals` row
- `catalyst_type` is one of the keys from `config/catalysts.yaml`
- `impact_score` and `probability_score` are 1–5 ints
- `economics_summary` is filled when present in source ("$X upfront, $Y milestones", etc.)
- Full prompt + response stored in journal for audit
- Handles Claude API errors gracefully (retries via tenacity, fallback to "unscored" status)
- ML feature vector populated at row creation (frozen, point-in-time correct)

---

## F1-10 — Cross-reference / corroboration boost
**What:** When a signal has `feature_source_count >= 2`, boost `conviction_score`. When sources have a quality spread (regulatory + press wire), boost more.
**DoD:**
- Single-source signal: `conviction = base`
- Two distinct sources: `conviction × 1.15`
- Three+ distinct sources OR a regulatory source: `conviction × 1.30`
- Stored as `conviction_score` separately from `impact * probability`

---

## F1-11 — Decision engine (shadow mode)
**What:** `fesi.decision.engine`. Takes signals, applies rules from `config/risk.yaml`, generates `decisions` rows in shadow mode.
**DoD:**
- Every signal with `conviction_score >= 12` (3*4 or 4*3) AND watchlist match → `would_buy` decision
- Every `would_buy` decision passes all 4 risk gates explicitly (recorded as bools in the decisions row)
- Position size, stop, target computed and stored
- Reasoning string is human-readable
- `mode='shadow'` always (live mode is gated by env flag, not implemented in F1)

---

## F1-12 — Outcome tracker (daily job)
**What:** `fesi.store.outcomes`. Daily job that joins signals → prices and computes T+1, T+5, T+30, max_drawup, max_drawdown.
**DoD:**
- Runs once per day after US market close
- Updates `outcomes` rows for any signal whose T+30 has just matured
- Marks `is_mature=1` when T+30 has elapsed
- New signals get an `outcomes` row with NULLs immediately so we can query "all signals + their (maybe-null) outcome" with one join

---

## F1-13 — Digest synthesizer
**What:** `fesi.digest.render`. Produces the markdown digest matching Fred's Perplexity prompt format: Top 10 + Emerging + Watchlist + Follow-up.
**DoD:**
- Output is markdown
- Top 10 ranked by `conviction_score` desc, only includes signals from current scan window
- Emerging section includes lower-confidence signals tagged as `[low-confidence]`
- Watchlist section shows update on watchlist tickers with news in last 48h
- Follow-up section lists signals with future dates (e.g. PDUFA dates) — sorted by date
- Includes shadow portfolio P&L summary at bottom
- Stored to `digests` table

---

## F1-14 — Notification delivery (Pushover + Telegram)
**What:** `fesi.digest.notify`. Pushes the digest via Pushover (urgent alerts) and Telegram (full digest).
**DoD:**
- Pushover delivery for HIGH conviction (≥4) watchlist signals — instant, with sound during waking hours
- Telegram delivery for batched scheduled digest (markdown format)
- Both configured via env vars
- Failure in one channel doesn't block the other (logged via structlog, journaled)
- All deliveries journaled to `digests` table

---

## F1-15 — Scheduler (5x daily, UAE time)
**What:** APScheduler running 5 jobs daily. Each job: ingest → normalize → score → decide → digest → notify.
**Schedule (UAE / Asia/Dubai time):**
- **15:00** — pre-US-market open (catches overnight US PRs + EU close + HK close) — alert sound ON
- **18:00** — post-US-open (catches US morning news flow) — alert sound ON
- **22:00** — mid-US-session (catches afternoon FDA decisions, mid-day news) — alert sound OFF
- **02:00** (next day) — post-US-close + after-hours filings sweep (8-Ks) — silent push, no sound
- **08:00** — morning catch-up digest — alert sound ON

**DoD:**
- `fesi schedule run` starts the long-lived scheduler process
- Logs every job run with start/end and outcome counts
- Handles errors per-job without crashing the scheduler
- 22:00 and 02:00 jobs deliver SILENT push (no alert sound)
- HIGH-conviction signals on watchlist names interrupt the schedule (instant push regardless of next scheduled scan)

---

## F1-16 — Streamlit dashboard
**What:** `fesi.ops.dashboard`. Minimal Streamlit dashboard at `localhost:8501`.
**Tabs:**
1. **Recent signals** — table (last 7 days), filterable by sector / catalyst / conviction
2. **Shadow portfolio** — current "positions", P&L, hit rate, calibration plot of impact_score vs realized return
3. **Source health** — last fetch time, item count per source, error rate
4. **Per-ticker page** — search by symbol, see all historical signals + outcomes for that ticker
**DoD:**
- `make dashboard` opens the dashboard
- All tabs load without errors against an empty fresh DB

---

## Definition of Done — Phase 1

- [ ] All 16 tickets pass acceptance criteria
- [ ] `fesi schedule run` runs continuously for 7 days without manual intervention
- [ ] First Pushover alert reaches Fred's phone for a real catalyst on a watchlist name
- [ ] At least 50 shadow decisions accumulated in `decisions` table
- [ ] At least 10 outcome rows have matured (T+5)
- [ ] Streamlit dashboard usable for daily review
- [ ] IBKR DFSA Dubai paper account opened (Fred, in parallel) — needed for Phase 4

---

## Out of scope for Phase 1 (deferred)

- Real broker execution (Phase 4)
- ML model training (Phase 3 — needs accumulated data first)
- HKEX / NMPA scraping (Phase 2 — start with English sources)
- Insider buying / options flow correlation (Phase 2)
- Supply-chain / competitor relationship graph (Phase 2)
- Reddit / StockTwits / X social ingestion (Phase 2 — wait for signal quality data)
- FastAPI backend (Phase 2 — not needed locally; only when frontend on Vercel ships)
- Postgres migration (Phase 2 — when SQLite hits a real wall)
