# Documentation

Read order if you're new to ShadowInvestor:

1. **[../README.md](../README.md)** — overview, mission, layout, setup
2. **[LEARNINGS.md](LEARNINGS.md)** ⭐ — institutional memory: do's, don'ts, gotchas, decisions, what broke. **Read this before changing anything load-bearing.**
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** — full system diagram, service responsibilities, data flow, schema
4. **[DECISION_FRAMEWORK.md](DECISION_FRAMEWORK.md)** — the trading framework: mission, sectors, 7-step pipeline, 4 risk gates, mode lifecycle
5. **[CLI.md](CLI.md)** — `fesi` command reference + common workflows
6. **[DEPLOYMENT.md](DEPLOYMENT.md)** — Railway + Vercel deploy guide, troubleshooting

## When to update which doc

| If you're ... | Update ... |
|---|---|
| Adding a new ingest adapter | `ARCHITECTURE.md` (service table), `LEARNINGS.md` if it has a quirk |
| Adding a new CLI command | `CLI.md` |
| Changing the risk policy | `DECISION_FRAMEWORK.md`, `config/risk.yaml` |
| Hitting a non-obvious bug and fixing it | `LEARNINGS.md` (under "What broke and how it was fixed") |
| Making a load-bearing decision | `LEARNINGS.md` (under "Decisions and why") + a memory file in `~/.claude/projects/...` |
| Changing the deploy steps | `DEPLOYMENT.md` |
| Shipping a phase | `CHANGELOG.md` + update phase status in `README.md` |
| Fixing a Railway / Vercel quirk | `LEARNINGS.md` + `DEPLOYMENT.md` troubleshooting section |

## Critical reads before deploying

- `LEARNINGS.md` → "DON'Ts" section
- `DEPLOYMENT.md` → "Troubleshooting" section
- `web/AGENTS.md` → the "this is NOT the Next.js you know" warning

## See also

- [`../CHANGELOG.md`](../CHANGELOG.md) — history of changes
- [`../PHASE_1_BUILD.md`](../PHASE_1_BUILD.md) — Phase 1 ticket plan (now shipped)
- [`~/.claude/projects/-Users-fred-FinanceEarlySignalsAndInvestor/memory/`](file:///Users/fred/.claude/projects/-Users-fred-FinanceEarlySignalsAndInvestor/memory/) — long-term context across Claude sessions
