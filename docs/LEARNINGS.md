# LEARNINGS

The institutional memory of ShadowInvestor. Read this before touching anything you haven't worked on recently. Every entry here represents an hour or more that someone (mostly Claude, working with Fred) burned figuring it out.

> **How to use this file:** when you hit a non-obvious gotcha and resolve it, add an entry. When you make a load-bearing decision, add a `### Why X (not Y)` note. When something breaks in production, root-cause it here.

---

## DON'Ts (hard rules)

### Don't trade out of `shadow` mode without a deliberate review
The `MODE` env var defaults to `shadow`. The decision engine writes every decision (buy AND no_buy) to the `decisions` table, but it never contacts a broker in shadow mode. **The only way `live` mode happens is an explicit env var change** — there's no in-app toggle, and there shouldn't be. The point of the gating is friction.

### Don't mock the database in tests
We use real SQLite (in `tmp_path`) for every test that touches the store layer. SQLAlchemy abstracts SQLite ↔ Postgres dialects but only at the SQL-text level — mocking the connection means you'd test against an interface that doesn't exist. See `tests/conftest.py::tmp_db`.

### Don't use `yf.download(symbol)` — use `yf.Ticker(symbol).history(period=...)`
`yf.download` returns multi-level columns even for one symbol and silently drops data. We hit this in Phase 1; the fix is in `src/fesi/store/prices.py::fetch_yfinance_history`. Use `Ticker.history()` always — clean single-level columns, stable across yfinance versions.

### Don't use shell-form `CMD` in the Dockerfile with `${VAR:-default}` syntax
Railway's runtime treats `CMD uvicorn ... --port ${PORT:-8000}` as exec form (literally splits on whitespace) and does NOT invoke `/bin/sh -c`. The `${PORT:-8000}` ends up as a literal string passed to uvicorn, which then dies with `Invalid value for '--port': '${PORT:-8000}' is not a valid integer.` We learned this the hard way over four failed deploys. **The fix:** read env vars in Python (`fesi api run` reads `Settings.api_port` which uses pydantic `AliasChoices("PORT", "API_PORT")`) and use pure exec-form CMD: `CMD ["fesi", "api", "run"]`. See `Dockerfile` line 38.

### Don't put `startCommand` in `railway.toml`
`railway.toml`'s `[deploy].startCommand` gets snapshotted into every deployment manifest and overrides anything you set later via `serviceInstanceUpdate` API. We had a stale `uvicorn ... --port ${PORT:-8000}` value in `railway.toml` that survived 6+ redeploys with the new Dockerfile because the toml took precedence. **The fix:** keep `railway.toml` minimal — `[build]` only, no `[deploy].startCommand`. Set per-service start commands via the Railway dashboard or `serviceInstanceUpdate` GraphQL mutation. See `railway.toml`.

### Don't `rm -rf data/` casually
The `data/` directory is gitignored and contains the SQLite DB (`fesi.db`) and the SEC ticker → CIK cache (`sec_cik_map.json`, ~5 MB, takes 5–10 sec to rebuild). Re-fetching prices for the watchlist after a wipe takes ~30 seconds. Re-running the pipeline against real APIs takes ~60–120 seconds. So a wipe is fine for testing, but you'll lose the shadow portfolio history.

### Don't add features that don't ladder to P&L
This is Fred's project rule, not a technical one. Every change should answer "does this help Fred make money on personal trades, with discipline?" If it doesn't, push back or defer. See `~/.claude/projects/.../memory/project_mission.md`.

### Don't bypass the four risk gates
Even in Phase 4 (live trading), every `buy` decision must pass: position size, concurrent positions, sector concentration, circuit breaker. The gates are the brakes. See `src/fesi/decision/risk_gates.py`.

### Don't put `healthcheckPath` in `railway.toml` when you have multiple services
`railway.toml`'s `[deploy]` section applies to ALL services built from the repo. The scheduler is not an HTTP server — it can't respond to `/health` and will fail the healthcheck every time. **Set `healthcheckPath` per-service via the Railway dashboard or GraphQL API**, not in `railway.toml`.

### Don't catch `IntegrityError` inside `with conn.begin_nested():`
See the DO's section for the full explanation. TL;DR: on Postgres, the savepoint is aborted after the failed INSERT. If you swallow the exception inside the `with`, the context manager tries to RELEASE (commit) the aborted savepoint → `InFailedSqlTransaction` poisons the entire connection. Put the `except` **outside** the `with`.

### Don't fetch sequentially when you can `Promise.all` (TS) / `asyncio.gather` (Py)
Page load latency matters. The home and admin pages already do this. New pages should follow the pattern.

---

## DO's (positive rules)

### DO preserve the LLM fallback path
Every classifier/scorer call checks `has_anthropic()` and falls back to deterministic pattern matching if no API key. This means the entire pipeline runs end-to-end with zero API keys — useful for local dev, CI, and the first prod deploy before keys are wired. **Don't add a code path that requires Claude to be set.** See `src/fesi/intelligence/llm.py`.

### DO add `aliases: [...]` to watchlist tickers when companies rename
BeiGene → BeOne Medicines (BGNE → ONC) broke ticker resolution because the classifier was looking for "BeiGene" in the news but the watchlist only had "BeOne Medicines". The `aliases` field on `WatchlistTicker` solves this. Pattern is in `config/watchlist.yaml`:
```yaml
- symbol: ONC
  name: "BeOne Medicines"
  aliases: ["BeiGene", "BGNE", "Brukinsa"]
```

### DO journal every decision (buy AND no_buy) with full reasoning
The Shadow Portfolio depends on this. A `no_buy` with `reason="conviction 9.0 < threshold 12.0"` is just as important as a `buy` because both are training data for Phase 3 ML. The decision engine never just "skips" — it always writes a row.

### DO use the deterministic classifier's `display_name` 2-grams
When adding new catalyst types to `config/catalysts.yaml`, you don't strictly need to fill in `patterns:`. The `_patterns_for_catalyst` helper in `src/fesi/intelligence/llm.py` derives 2-grams from `display_name` so `"First Production Achieved"` becomes patterns `["first production", "production achieved"]` automatically. But adding explicit `patterns:` improves precision.

### DO use the SAVEPOINT pattern for "insert with dedup" — exception OUTSIDE the `with`
`raw_items`, `prices`, and `outcomes` use SAVEPOINTs for dedup inserts. **Critical:** the `except IntegrityError` must be **outside** the `with conn.begin_nested()` block, not inside it. On Postgres, a failed INSERT aborts the savepoint; if you catch the error inside the `with`, the context manager tries to `RELEASE SAVEPOINT` (commit) on exit — but the savepoint is aborted, causing `InFailedSqlTransaction`. Correct pattern:
```python
try:
    with conn.begin_nested():
        conn.execute(text("INSERT ..."), params)
except IntegrityError:
    pass  # duplicate, fine
```
Wrong (breaks Postgres):
```python
with conn.begin_nested():
    try:
        conn.execute(text("INSERT ..."), params)
    except IntegrityError:
        pass  # swallows error but savepoint is still aborted → RELEASE fails
```
See `src/fesi/store/raw_items.py::insert_raw_items`.

### DO use the `raw_items_signals` junction table to find unprocessed items
The original code used SQLite's `json_each` on `signals.raw_item_ids`. That doesn't work in Postgres (different function name) and is slow. The junction table is portable and indexed. See `src/fesi/store/raw_items.py::get_unprocessed_raw_items`.

### DO use shared formatters and StatRow components in the frontend
`web/src/lib/format.ts` exports `formatTimestamp`, `formatUsd`, `formatPrice`, `formatCount`. `web/src/components/StatRow.tsx` exports `StatRow` (flex justify-between for cards) and `StatTile` (stacked grid tile). Don't inline date slicing or `$${n.toLocaleString()}` in new pages.

### DO wrap `useSearchParams()` in `<Suspense>`
Next.js 16's strict mode bails out the build if a client component uses `useSearchParams()` without a Suspense boundary. We hit this on `/login`. Pattern:
```tsx
function Inner() {
  const params = useSearchParams();
  // ...
}
export default function Page() {
  return <Suspense fallback={<div>loading...</div>}><Inner /></Suspense>;
}
```

### DO commit memory updates as you go
Long-term memory lives in `~/.claude/projects/-Users-fred-FinanceEarlySignalsAndInvestor/memory/`. When a new architectural decision is made, update or create a memory file. The `MEMORY.md` index gets loaded at every conversation start, so keep it current.

---

## Gotchas & pitfalls

### Next.js 16 renamed `middleware.ts` to `proxy.ts`
We're on Next.js 16.2.3 (current as of 2026-04). The file that used to be `middleware.ts` is now `proxy.ts` and the function exported as `middleware()` is now `proxy()`. The `config.matcher` API is unchanged. Read `web/AGENTS.md` — it has a hard "this is NOT the Next.js you know" warning. Always check `web/node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md` before assuming behavior.

### Next.js 16 `params` and `searchParams` are Promises
In Server Components: `params: Promise<{ slug: string }>` not `{ slug: string }`. Must `await`. This was a Next.js 15 change but it bites if you're copy-pasting from Next 13/14 docs. See any of our `[id]` or `[symbol]` pages for the pattern.

### Railway CLI write-ops auth expires before read-ops
`railway whoami` reports "Logged in" successfully, but `railway add`, `railway up`, `railway variables --set` all return "Unauthorized." Even after `railway link --project <id>`. The OAuth token's write scope expires hours before the read scope. **Workaround:** bypass the CLI entirely. Use `scripts/railway_deploy.py` which talks to `https://backboard.railway.com/graphql/v2` directly with the `accessToken` from `~/.railway/config.json`. The GraphQL API works fine even when the CLI says unauthorized.

### Railway's GraphQL `serviceInstanceDeployV2` accepts a `commitSha` arg
This is critical. Without it, the mutation redeploys whatever Railway has cached as the "latest deployment", which may not be your latest git commit (Railway's GitHub webhook can lag by minutes). **Always pass the explicit commit SHA** when forcing a deploy:
```python
gql('mutation($s:String!,$e:String!,$c:String!) { serviceInstanceDeployV2(serviceId:$s, environmentId:$e, commitSha:$c) }',
    {'s': sid, 'e': env_id, 'c': git_head_sha})
```

### Railway's managed Postgres template is NOT just `postgres:16`
Railway's `railway add --database postgres` provisions a service with `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `PGDATA`, an attached volume, and a generated `DATABASE_URL`. If you provision Postgres via the GraphQL `serviceCreate` mutation with just `image: postgres:16`, you get NONE of those — you have to set every variable manually and create the volume yourself. **`scripts/railway_deploy.py` does this for you** — the `POSTGRES_PASSWORD` is generated via `secrets.token_urlsafe(24)` and `DATABASE_URL` is constructed as `postgresql://postgres:<pw>@postgres.railway.internal:5432/railway`.

### Railway template variables (`${{Postgres.DATABASE_URL}}`) don't get resolved when set via API
If you call `variableUpsert` with `value="${{Postgres.DATABASE_URL}}"`, Railway stores it as a literal string and the variable resolves to `""` at deploy time. This only works if you set the variable in the dashboard UI. **Workaround:** read the Postgres service's literal vars via GraphQL, construct `DATABASE_URL` yourself, and set it as a plain string on the consuming service. See `scripts/railway_deploy.py`.

### Railway Postgres needs `postgresql://` not `postgres://`
`psycopg` rejects `postgres://...` URLs since v3. Always normalize. SQLAlchemy is more forgiving but psycopg v3 (which we use directly via SQLAlchemy) is strict. We hit this in Phase 2.

### PR Newswire RSS returns `Errno 54 Connection reset` for non-browser User-Agents
PR Newswire's CDN actively blocks anything that looks like a bot. GlobeNewswire and BusinessWire don't have this restriction. **The fix:** the wires adapter sends a Firefox UA:
```python
"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
```
See `src/fesi/ingest/wires.py`.

### SEC EDGAR requires `User-Agent` with contact info
Without it, EDGAR returns 403. Format: `"FESI/0.0.1 (contact: fesi@example.com)"`. See `src/fesi/ingest/http.py::USER_AGENT`.

### FDA OpenFDA `/drug/drugsfda.json` returns 500 intermittently
Don't rely on it as the only biotech source. We backstop with ClinicalTrials.gov v2 + the press wires.

### ClinicalTrials.gov v2 date-range filter syntax is non-obvious
- Wrong: `filter.lastUpdatePostDate=2026-04-08,2026-04-09` → 400
- Right: `filter.advanced=AREA[LastUpdatePostDate]RANGE[2026-04-08,2026-04-09]`

Sponsor filter is `query.spons` not `query.lead`. See `src/fesi/ingest/clinicaltrials.py`.

### BeiGene → BeOne Medicines (BGNE → ONC)
Renamed in 2024-2025. Current ticker is `ONC`. I-Mab (`IMAB`) and LianBio (`LIAN`) both restructured and are no longer on Yahoo Finance — we removed them from the watchlist seed.

### `vercel link` requires `--scope` if you have multiple Vercel teams
Otherwise you get a JSON error with "next" suggestions. Use `--scope freddb-5400s-projects` (or whichever team owns the project). See `scripts/wire_vercel.py`.

### Vercel project deploys go to `*-<hash>-<team>.vercel.app` first, then alias to `<project>.vercel.app`
The `vercel deploy --prod` output gives you both URLs. Use the alias (`shadowinvestor.vercel.app`) for everything user-facing.

---

## Decisions and why

### Shadow Portfolio instead of historical backtest
Historical news data is unreliable, expensive, and not point-in-time correct. The Shadow Portfolio approach runs the live pipeline in `MODE=shadow` and journals every decision with full reasoning + feature vector. After 30 days you have a dataset that's both a backtest AND an ML training set, generated under exactly the same conditions live trading would see. **Fred's call, 2026-04-09.** See `~/.claude/projects/.../memory/architecture_decisions.md`.

### ML-ready schema from day 1
Every signal row has 12 frozen feature columns (source count, source diversity, sentiment, market cap bucket, time-of-day, day-of-week, watchlist flag, catalyst priors, etc). Outcomes get computed daily and joined back. Phase 3 trains gradient-boosted trees on accumulated data. **Why not start with LLM scoring only?** Tabular GBMs typically beat LLM-only scoring on calibrated outcome prediction. We get both.

### China-biotech-to-FDA as a dedicated 6th sector
Most US analysts don't follow Chinese biotechs closely; the disclosure patterns (HKEX vs SEC, NMPA vs FDA) and out-licensing-to-Big-Pharma playbook are distinct enough to deserve their own scoring priors. **This is the project's edge area.** See `config/sectors.yaml` and the watchlist seed.

### Local-first architecture (SQLite → Postgres only when forced)
Phase 1 ran end-to-end on SQLite + APScheduler on Fred's Mac before we touched any cloud. Zero infra cost during the calibration window. The SQLAlchemy abstraction means moving to Postgres in Phase 2 was a one-line env var change, not a rewrite.

### Interactive Brokers (DFSA Dubai branch) as the broker
Verified for UAE residents (Fred's jurisdiction). DFSA-regulated, AED funding via FAB bank, free TWS/Web/REST APIs, 160+ markets including HKEX (Chinese biotechs) and TSX-V (uranium juniors). Backups: Saxo Bank, Tiger Brokers. See `~/.claude/projects/.../memory/financial_constraints.md`.

### Two Railway services (api + scheduler) sharing one image
Crash isolation: if the scheduler hits a bug mid-pipeline, the API stays up so the dashboard still works. Cost control: the API can scale to zero between requests. Same Docker image, different `startCommand` per service.

### Pure exec-form Dockerfile CMD
After the `${PORT:-8000}` shell-expansion saga, we settled on `CMD ["fesi", "api", "run"]` with all env-var resolution happening in Python (`Settings.api_port` reads `PORT` via `AliasChoices`). **Never go back** to shell-form CMD in this Dockerfile.

### Bearer token auth for the API, password gate for the frontend
Two layers: (1) the user enters a password into the Vercel frontend, which sets a cookie checked by `proxy.ts`; (2) the Vercel frontend's Server Components fetch from Railway with a `Authorization: Bearer <token>` header where the token is a server-only env var. Browser never sees the API token.

### Public GitHub repo (for now)
Originally private, but Railway can't clone private repos without the user installing the Railway GitHub App. We made the repo public to unblock deployment. **No secrets are in the repo** — all keys are env vars on Railway/Vercel. We can re-private it once Fred sets up the Railway GitHub App in the dashboard.

---

## What broke and how it was fixed

### API deploy failed 6+ times with `${PORT:-8000}` literal error (2026-04-09)
**Root cause:** A combination of three things — (1) `Dockerfile` used shell-form `CMD uvicorn ... --port ${PORT:-8000}`, (2) Railway's runtime treats shell-form CMD as exec without `/bin/sh -c`, (3) `railway.toml` had a `startCommand` that snapshotted into every deploy and overrode the per-service `startCommand` we set via API. **Fix:** removed `startCommand` from `railway.toml`, switched Dockerfile to `CMD ["fesi", "api", "run"]`, made `Settings.api_port` read `PORT` via `AliasChoices`. See commits `0831d5f` and `b14af08`.

### Railway deploys stuck on stale commit SHA `1daa9de`
**Root cause:** `serviceInstanceDeployV2(serviceId, environmentId)` (no commitSha arg) redeploys the latest Railway-known commit, not the latest git commit. Railway's GitHub webhook had lagged behind two pushes. **Fix:** always pass `commitSha` arg explicitly:
```python
serviceInstanceDeployV2(serviceId, environmentId, commitSha=git_rev_parse_HEAD())
```

### Postgres service had no `DATABASE_URL` after `serviceCreate`
**Root cause:** Provisioning Postgres via `serviceCreate(image: "ghcr.io/railwayapp-templates/postgres-ssl:latest")` doesn't set the standard postgres env vars — Railway's managed Postgres template does that. **Fix:** `scripts/railway_deploy.py` generates a random `POSTGRES_PASSWORD`, sets `POSTGRES_USER`/`POSTGRES_DB`/`PGDATA`, attaches a volume, and constructs `DATABASE_URL` manually as `postgresql://postgres:<pw>@postgres.railway.internal:5432/railway`. Then sets that on the api + scheduler services.

### Railway template variables `${{Postgres.DATABASE_URL}}` resolved to empty string
**Root cause:** Setting a variable's value to `${{Postgres.DATABASE_URL}}` via the GraphQL API stores it as a literal — the `${{...}}` interpolation only works when set via the dashboard UI. **Fix:** read the Postgres service's vars directly via `variables(...)` query and set the constructed `DATABASE_URL` string on the consumers.

### Dockerfile build cached too aggressively, deployed wrong commit
**Root cause:** Even with `skipBuildCache: true` in the deploy meta, Railway's "Build time: 8.77 seconds" was a strong signal it was reusing a cached image. **Fix:** ensured the new commit invalidated cache layers (Dockerfile change) AND passed `commitSha` to `serviceInstanceDeployV2` to force the right code.

### Next.js 16 build failed with "useSearchParams() should be wrapped in a suspense boundary"
**Root cause:** Next.js 16's static prerender bails out client components that use `useSearchParams()` without a Suspense boundary above them. Our `/login` page hit this. **Fix:** split into a `LoginForm` inner component wrapped in `<Suspense>` by the page-level component. See `web/src/app/login/page.tsx`.

### TypeScript inferred `acc[k] = []` as `never[]`
**Root cause:** `tickers.reduce((acc, t) => { acc[k] = []; ... }, {})` — the empty object literal's type is inferred as `{}` and the array push fails. **Fix:** declare the accumulator type explicitly: `Record<string, Ticker[]> = {}`. See `web/src/app/tickers/page.tsx`.

### `web/.env.example` not committable due to `.gitignore`
**Root cause:** `.gitignore` had `web/` excluded entirely (or `*.env*` overly broad). **Fix:** the file is not committed, but the values it would contain are documented in `docs/DEPLOYMENT.md`.

### Postgres `InFailedSqlTransaction` killed every pipeline run (2026-04-10)
**Root cause:** Two bugs compounding. (1) `insert_raw_items` caught `IntegrityError` *inside* `with conn.begin_nested()`, meaning Postgres's aborted savepoint was never rolled back — the context manager tried to RELEASE it and failed. (2) The pipeline had no SAVEPOINTs around candidate processing or decision making, so any single SQL error poisoned the entire transaction. **Fix:** moved all `except IntegrityError` outside the `with conn.begin_nested()` block in `raw_items.py`, `prices.py`, `outcomes.py`. Added `conn.begin_nested()` around each candidate and decision in `pipeline.py`. See commit `e72198a`.

### Postgres used psycopg2 (missing) instead of psycopg v3 (2026-04-10)
**Root cause:** `DATABASE_URL=postgresql://...` makes SQLAlchemy default to the `psycopg2` dialect, but we ship `psycopg[binary]>=3.2` (v3). The v2 package was never installed. **Fix:** `_normalize_url` in `db.py` now rewrites `postgresql://` to `postgresql+psycopg://` to force the v3 driver. See commit `888e227`.

### Scheduler failed healthcheck because `railway.toml` applied `/health` to all services (2026-04-10)
**Root cause:** `railway.toml` had `[deploy].healthcheckPath = "/health"` which Railway applied to every service — including the scheduler, which is a long-running APScheduler process (not an HTTP server). **Fix:** removed `healthcheckPath` from `railway.toml`, set it only on the API service via `serviceInstanceUpdate` GraphQL mutation. See commit `99cd3a6`.

### `railway redeploy` reuses cached image, doesn't pull new code
**Root cause:** `railway redeploy --service X` re-runs the most recent deployment image. If you've pushed new code to GitHub but the service was deployed via `railway up` (local code upload), redeploy just re-runs the old image. **Fix:** always use `railway up --service X` to push fresh local code.

### Initial fallback classifier returned `guidance_raise` for everything
**Root cause:** Catalyst types had no explicit `patterns:` in `catalysts.yaml` so the matcher always scored 0 and fell through to the catch-all. **Fix:** the `_patterns_for_catalyst` helper now derives 2-grams from `display_name` automatically, so `"First Production Achieved"` matches `"first production"` in news headlines. See `src/fesi/intelligence/llm.py::_patterns_for_catalyst`.

---

## Constraints (hard limits that shaped the architecture)

- **Cash account, no margin, no leverage, no shorts, no options.** All sizing logic assumes long-only equity. Don't add features that require any of these without an explicit decision review.
- **Max $2,000 per trade, max $10,000 deployed per month.** Position sizing scales conviction → size, capped at $2,000. Monthly cap is enforced by the circuit-breaker risk gate.
- **UAE timezone (Asia/Dubai).** Scheduler runs at 15:00, 18:00, 22:00, 02:00, 08:00 UAE time. All timestamps stored as UTC in the DB; UAE-localized only for display.
- **Personal use, single user.** No multi-tenancy, no user accounts, password gate is sufficient.
- **Free or near-free data sources during calibration.** SEC EDGAR, FDA OpenFDA, ClinicalTrials.gov, RSS wires — all free. Polygon ($29/mo) and Endpoints News ($18/mo) are budget-approved adds for Phase 2 if needed.
- **Vercel hobby tier + Railway base plan.** Total infra cost target: under $20/mo before any data subscriptions.
- **Python 3.12+ required.** SQLAlchemy 2.0, pydantic v2 features, and `from __future__ import annotations` patterns assume modern Python. macOS system Python (3.9) is too old — use `uv python install 3.12`.

---

## Patterns that work (use these)

### Ingest adapter pattern
Every adapter inherits from `IngestAdapter` (`src/fesi/ingest/base.py`), exposes a `source_key`, implements `fetch() -> list[RawItem]`. Use the shared `get_client()` helper from `ingest/http.py` for httpx + retries. Use `RawItem.make_content_hash()` for dedup. See `sec_edgar.py` as the canonical example.

### Store-module pattern
One module per table. Pure functions (no classes) that take a `Connection` as the first arg. Always use `text("... :name ...")` with named params (cross-DB compatible). Always wrap dedup-prone inserts with `try: with conn.begin_nested(): insert... except IntegrityError: pass` (**exception outside the `with`** — see DO's). See `store/raw_items.py`.

### Shadow → paper → live mode lifecycle
The `mode` env var has three legal values: `shadow`, `paper`, `live`. The decision engine writes the mode into every `decisions` row. Check the mode before contacting any broker. Default is `shadow`. The flip is manual.

### LLM with deterministic fallback
Public function (e.g. `classify(title, body, source)`) checks `has_anthropic()` and either calls `_claude_classify` or `_deterministic_classify`. On any Claude failure, log and fall back. Never raise from the public function. See `src/fesi/intelligence/llm.py`.

### Server Component data fetching
Pages are `async function Page({ params, searchParams })` with `params: Promise<...>` and `searchParams: Promise<...>`. Data fetching happens directly in the component via `await getX()` from `@/lib/api`. Use `Promise.all` for multiple parallel fetches. Use `.catch(() => [])` or `.catch(() => null)` for graceful error handling. Mark pages as `export const dynamic = "force-dynamic"` if they fetch live data.

### Frontend formatters
Always use `@/lib/format` for date / currency / count display. Never inline `s.created_at.slice(5, 16).replace("T", " ")` or `$${n.toLocaleString()}` in a new page.

### Frontend StatRow / StatTile
Use `<StatRow label value tone />` for flex-layout label/value rows inside cards (admin page). Use `<StatTile label value />` for stacked grid tiles (signal detail page). Both live in `@/components/StatRow`.

### Test pattern
`tmp_db` fixture creates a fresh SQLite DB per test, applies the schema via `init_db()`, loads the watchlist from `config/watchlist.yaml`. `db_conn` yields a SQLAlchemy connection. Use `monkeypatch.setenv("ANTHROPIC_API_KEY", "")` to force the deterministic classifier. See `tests/conftest.py`.

### Memory-driven context
Long-term context lives in `~/.claude/projects/-Users-fred-FinanceEarlySignalsAndInvestor/memory/`. The `MEMORY.md` index is loaded into every conversation. Add new memory files when you make decisions worth preserving across sessions.
