# Deployment

How to deploy ShadowInvestor from scratch — Railway (backend + Postgres + scheduler) + Vercel (frontend).

## Current production state

| | URL | Project |
|---|---|---|
| Frontend | https://shadowinvestor.vercel.app | `freddb-5400s-projects/shadowinvestor` |
| Backend API | https://shadowinvestor-api-production.up.railway.app | `shadowinvestor` (Railway project ID `e05eaef6-387d-43e3-ae1b-71dbbf1b09bf`) |
| GitHub | https://github.com/fredd-b/shadowinvestor | public |

## What you need before starting

- A Railway account with billing set up (free trial works for first deploy)
- A Vercel account (hobby tier is free)
- A GitHub account with the repo pushed
- A Mac/Linux machine with `git`, `gh`, `vercel`, `railway` CLIs installed and authenticated
- Optional but recommended: an Anthropic API key for the upgraded LLM scorer

## One-time setup

### 1. GitHub repo

```bash
gh repo create fredd-b/shadowinvestor --public --source=. --remote=origin --push
```

> **Why public?** Railway's GitHub integration can clone public repos without OAuth installation. To use a private repo, you'd need to install the Railway GitHub App at https://github.com/apps/railway and authorize the repo. We chose public for setup speed; no secrets are in the code.

### 2. Vercel project

```bash
cd web
vercel link --project shadowinvestor --yes --scope <your-vercel-team-slug>
```

The `--scope` is **required** if you have multiple Vercel teams — without it the CLI errors with a JSON error and "next" suggestions. Find your team slug with `vercel teams ls` (or check `https://vercel.com/<team-slug>`).

Set initial env vars (use placeholders for `API_BASE_URL` and `API_TOKEN` — we'll update them after Railway is up):

```bash
vercel env add SITE_PASSWORD production --value "<choose-a-strong-password>" --yes
vercel env add API_BASE_URL production --value "http://placeholder.example.com" --yes
vercel env add API_TOKEN production --sensitive --value "placeholder" --yes
```

Deploy the frontend:

```bash
vercel deploy --prod --yes
```

You should see something like:
```
Production: https://shadowinvestor-<hash>-<team>.vercel.app
Aliased:    https://shadowinvestor.vercel.app
```

The dashboard is live but every API call will fail until Railway is up. That's fine.

### 3. Railway project

The Railway CLI works when properly authenticated. If write-ops fail ("Unauthorized") while `railway whoami` works, re-run `railway login`. For initial provisioning, `scripts/railway_deploy.py` talks to the Railway GraphQL API directly.

**Deploying code updates:** Always use `railway up --service <name>` (NOT `railway redeploy` which reuses the cached image without pulling new code). Set env vars with `railway variable set KEY=value --service <name>`.

```bash
# Step 1: log in interactively (one time, required to populate ~/.railway/config.json)
railway login

# Step 2: create the project (this CLI command does work)
railway init --name shadowinvestor --workspace "<your-workspace-name>"

# Step 3: link the project to the current directory
railway link --project <project-id>
```

The project ID is shown after `railway init`. Save it.

Now run the GraphQL provisioning script. Before running, edit `scripts/railway_deploy.py` and update:
- `PROJECT_ID` — the project ID from step 2
- `GITHUB_REPO` — your repo (`fredd-b/shadowinvestor` for the canonical deploy)

```bash
python scripts/railway_deploy.py
```

The script will:
1. Look up the production environment ID via GraphQL
2. Create the `Postgres` service (using `ghcr.io/railwayapp-templates/postgres-ssl:latest`)
3. Create `shadowinvestor-api` from the GitHub repo
4. Create `shadowinvestor-scheduler` from the same repo (different start command)
5. Generate a random `POSTGRES_PASSWORD` and set it on Postgres
6. Set `POSTGRES_USER`, `POSTGRES_DB`, `PGDATA` on Postgres
7. Compute `DATABASE_URL = postgresql://postgres:<pw>@postgres.railway.internal:5432/railway`
8. Set `DATABASE_URL`, `API_TOKEN` (random 32 bytes), `MODE=shadow`, `TZ=Asia/Dubai`, `CORS_ORIGINS=https://shadowinvestor.vercel.app` on the api + scheduler services
9. Generate a public domain for the API service
10. Trigger initial deploys

The script prints the `API_TOKEN` and the API URL when done. Save both.

> **CRITICAL:** if Railway redeploys later, always pass `commitSha` explicitly to `serviceInstanceDeployV2` — the mutation without it deploys whatever Railway has cached as latest, which can lag behind your most recent push by minutes. The script handles this.

### 4. Wire Vercel → Railway

After Railway is provisioned:

```bash
python scripts/wire_vercel.py "<railway-api-url>" "<api-token>"
```

This:
1. Removes the placeholder `API_BASE_URL` and `API_TOKEN` from Vercel production
2. Sets the real values
3. Triggers `vercel deploy --prod --yes`

### 5. Verify end-to-end

```bash
curl https://shadowinvestor-api-production.up.railway.app/health
# → {"status":"ok","db":"ok"}

curl -H "Authorization: Bearer $API_TOKEN" \
     https://shadowinvestor-api-production.up.railway.app/api/status
# → {"version":"0.0.1","mode":"shadow",...}
```

Then visit https://shadowinvestor.vercel.app in a browser, enter your `SITE_PASSWORD`, and you should see the empty dashboard.

### 6. Trigger the first pipeline run

Click "▶ Run pipeline now" on `/admin`. After 30–90 seconds you should see real signals appear on the home page.

## Service-level configuration

### Railway service: `shadowinvestor-api`

| Setting | Value |
|---|---|
| Source | GitHub: `fredd-b/shadowinvestor` (main branch) |
| Builder | `DOCKERFILE` |
| Dockerfile path | `Dockerfile` |
| Start command | `fesi api run` (overrides Dockerfile CMD via Railway service config) |
| Health check path | `/health` |
| Health check timeout | 120 s |
| Restart policy | `ON_FAILURE`, max 5 retries |

Required env vars (set by `scripts/railway_deploy.py`):
- `DATABASE_URL` — Postgres connection string (literal, NOT a `${{}}` template ref)
- `API_TOKEN` — bearer token for the Vercel frontend, random 32 bytes
- `CORS_ORIGINS` — comma-separated list, must include `https://shadowinvestor.vercel.app`
- `MODE` — `shadow` (default; do NOT set to `live` until Phase 4)
- `TZ` — `Asia/Dubai`
- `ENVIRONMENT` — `prod`
- `PORT` — auto-injected by Railway, read by `Settings.api_port`

Optional env vars (enable upgrades):
- `ANTHROPIC_API_KEY` — upgrades classifier from deterministic fallback to Claude (**set in prod** as of 2026-04-10)
- `PERPLEXITY_API_KEY` — enables Perplexity web search as 5th ingest source (**set in prod** as of 2026-04-10)
- `PUSHOVER_USER_KEY` + `PUSHOVER_APP_TOKEN` — urgent push alerts
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — digest delivery
- `POLYGON_API_KEY` — paid news source (future add)

### Railway service: `shadowinvestor-scheduler`

Same source + same Dockerfile as the API. The only difference is the start command:

| Setting | Value |
|---|---|
| Source | GitHub: `fredd-b/shadowinvestor` (main branch) |
| Builder | `DOCKERFILE` |
| Start command | `fesi schedule run` |
| Health check path | none (scheduler has no HTTP port) |
| Restart policy | `ON_FAILURE`, max 5 retries |

Same env vars as the API. The scheduler reads `DATABASE_URL` and runs the pipeline 5x daily.

### Railway service: `Postgres`

| Setting | Value |
|---|---|
| Source | image `ghcr.io/railwayapp-templates/postgres-ssl:latest` |
| Volume | mount path `/var/lib/postgresql/data` |

Env vars (set manually because we don't use Railway's managed Postgres template):
- `POSTGRES_PASSWORD` — generated by deploy script
- `POSTGRES_USER` — `postgres`
- `POSTGRES_DB` — `railway`
- `PGDATA` — `/var/lib/postgresql/data/pgdata`

### Vercel project: `shadowinvestor`

| Setting | Value |
|---|---|
| Framework | Next.js |
| Root directory | `web/` |
| Build command | `npm run build` (auto-detected) |
| Output directory | `.next` (auto-detected) |

Required env vars (production):
- `API_BASE_URL` — Railway API URL, e.g. `https://shadowinvestor-api-production.up.railway.app`
- `API_TOKEN` — same value as Railway's `API_TOKEN`, marked sensitive
- `SITE_PASSWORD` — the user-facing password for the dashboard (cookie value)

## Updating production

### Code change → backend

Push to `main` on GitHub. Railway auto-deploys both `shadowinvestor-api` and `shadowinvestor-scheduler` from the latest commit.

If the auto-deploy doesn't trigger (webhook lag), force it:
```bash
python scripts/railway_deploy.py  # idempotent — re-runs everything, deploys latest commit
```

Or manually via GraphQL:
```python
import json, httpx, subprocess
from pathlib import Path
token = json.loads(Path.home().joinpath('.railway/config.json').read_text())['user']['accessToken']
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
httpx.post('https://backboard.railway.com/graphql/v2',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'query': 'mutation($s:String!,$e:String!,$c:String!) { serviceInstanceDeployV2(serviceId:$s,environmentId:$e,commitSha:$c) }',
        'variables': {'s': '<service-id>', 'e': '<env-id>', 'c': sha},
    })
```

### Code change → frontend

Push to `main`. Vercel auto-deploys.

Or manually:
```bash
cd web && vercel deploy --prod --yes
```

### Env var change

Backend (Railway):
```python
# scripts/set_railway_var.py — pattern, not committed
import json, httpx
from pathlib import Path
token = json.loads(Path.home().joinpath('.railway/config.json').read_text())['user']['accessToken']
httpx.post('https://backboard.railway.com/graphql/v2',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'query': '''mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }''',
        'variables': {'input': {
            'projectId': 'e05eaef6-387d-43e3-ae1b-71dbbf1b09bf',
            'environmentId': '5859deb3-b4ef-49b0-bede-e21b9d3155a1',
            'serviceId': '<api-or-scheduler-service-id>',
            'name': 'ANTHROPIC_API_KEY',
            'value': '<your-key>',
        }},
    })
# Then trigger a redeploy with the new variable in scope
```

Frontend (Vercel):
```bash
vercel env rm SITE_PASSWORD production --yes
vercel env add SITE_PASSWORD production --value "<new-password>"
cd web && vercel deploy --prod --yes
```

## Local dev (no cloud needed)

You can run the entire stack locally without Railway or Vercel:

```bash
# 1. One-time setup
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[ml,dev]"

# 2. Initialize the local SQLite DB and load the watchlist
fesi init-db
fesi config-check

# 3. Fetch prices for the watchlist (one-time, ~30 seconds)
fesi prices fetch-watchlist --days 30

# 4. Run the pipeline once against real APIs
fesi run-pipeline
fesi digest last           # see what was generated

# 5. Start the API + frontend in two terminals
# Terminal A:
fesi api run --port 8765

# Terminal B:
cd web
cp .env.example .env.local  # then edit: API_BASE_URL=http://127.0.0.1:8765, SITE_PASSWORD=test
npm install
npm run dev                 # → http://localhost:3001 (or 3000)
```

Visit http://localhost:3001/login, enter "test", and you should see the dashboard with real data from your local pipeline run.

## Troubleshooting

### Railway deploy keeps failing on `${PORT:-8000}` literal error
You have a stale `startCommand` somewhere — either in `railway.toml` or in the Railway dashboard's service settings. **Both must be cleared.** The Dockerfile CMD is `["fesi", "api", "run"]` which reads `$PORT` in Python. See LEARNINGS.md for the full story.

### Railway deploy uses an old commit
The webhook lagged or the cache won. Force the latest commit explicitly:
```python
serviceInstanceDeployV2(serviceId, environmentId, commitSha=git_head_sha)
```

### Postgres `DATABASE_URL` is empty in the API service
The `${{Postgres.DATABASE_URL}}` template syntax doesn't resolve when set via the GraphQL API. Set the literal `postgresql://postgres:<pw>@postgres.railway.internal:5432/railway` string. `scripts/railway_deploy.py` does this automatically.

### Frontend shows empty dashboard / API errors
Check (in order):
1. `curl https://shadowinvestor-api-production.up.railway.app/health` — should return `{"status":"ok","db":"ok"}`
2. Check the Vercel project's `API_BASE_URL` env var — must match the Railway API URL exactly
3. Check the Vercel project's `API_TOKEN` env var — must match Railway's `API_TOKEN` exactly
4. Trigger a pipeline run via `/admin` — empty DBs show empty pages, that's expected before the first run

### Login page shows but "Wrong password"
Vercel's `SITE_PASSWORD` env var doesn't match what you typed. Check it:
```bash
vercel env ls
```
And update if needed (see "Env var change → Frontend" above).

### `railway add` returns Unauthorized but `railway whoami` works
Known issue. Use `scripts/railway_deploy.py` which goes around the CLI.

## Cost estimate

| Service | Tier | Monthly cost |
|---|---|---|
| Vercel | Hobby | $0 |
| Railway | Hobby ($5 trial credit) | $5–10 once trial expires |
| Anthropic Claude | pay-as-you-go | ~$5–15 (depends on signal volume) |
| Pushover | one-time license | $5 (one-time) |
| Telegram | free | $0 |
| Polygon.io (optional) | Starter | $29 |
| Endpoints News (optional) | Standard | $18 |

**Minimum viable**: ~$10–25/month before paid data subscriptions.
