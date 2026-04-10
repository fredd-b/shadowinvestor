# Decision Framework

The mission, the rules, and the review process for ShadowInvestor — in one place.

This is the same content rendered at `/framework` in the web app, kept here as the canonical source.

## Mission

Make money on personal trades by detecting high-conviction, niche-sector catalysts faster and more systematically than reading news manually, with eventual semi-automated execution through Interactive Brokers (DFSA Dubai branch).

- **Stretch target:** +50% blended annual
- **Realistic-but-good:** 20–30%
- **Kill threshold:** below +10% — if the system can't beat that after 6 months of shadow data, retire it.

## What we monitor (6 sectors)

1. **Biotech / Pharma (Global)** — FDA decisions, pivotal trial readouts, licensing deals
2. **China Biotech → FDA Pipeline** — DEDICATED edge area. Chinese-domiciled biotechs tracking toward US FDA submission/approval. Under-followed by US analysts.
3. **AI Infrastructure** — GPU cloud, data center REITs, optics/semis, design wins
4. **Crypto Miners → AI/HPC** — BTC miners pivoting to AI hosting contracts
5. **Commodities — Uranium / Gold / Critical Minerals** — mine milestones, offtakes, reserve upgrades
6. **Other Binary-Catalyst Sectors** — defense awards, large buybacks, guidance changes

See `config/sectors.yaml` for full definitions.

## How a signal becomes a buy (7 steps)

### 1. Multi-source ingest
SEC EDGAR (8-K/6-K), FDA OpenFDA, ClinicalTrials.gov v2, and 5 press wire RSS feeds (PR Newswire health/energy/financial, GlobeNewswire, BusinessWire) are fetched 5x daily in UAE timezone (15:00, 18:00, 22:00, 02:00, 08:00).

### 2. Normalize + cross-source dedup
Items with title similarity ≥ 0.85 are merged into one candidate signal. Source count and source diversity become ML features on the resulting signal row.

### 3. Classify + score
Each candidate is classified into one of 28 catalyst types from `config/catalysts.yaml` (FDA approval, Phase 3 readout, offtake signing, mine first production, AI compute contract win, etc.) and scored on impact (1–5) × probability (1–5).

- Uses Claude when `ANTHROPIC_API_KEY` is set
- Falls back to deterministic pattern matching when no key — the entire pipeline runs end-to-end without Claude

### 4. Cross-reference boost
Single source: `1.00×`. Two distinct sources: `1.15×`. Three+ sources OR any regulatory source: `1.30×`.

`conviction_score = impact × probability × multiplier`

### 5. Decision engine
Conviction must be ≥ **12.0** (10.0 if the ticker is on the watchlist — the watchlist gets a 2-point conviction boost). Then ALL FOUR risk gates must pass.

### 6. Position sizing
Conviction-scaled fixed-risk: 0.5× max at conviction 12, scaling linearly to 1.0× max at conviction 25. Max **$2,000** per trade. Stop loss 12% below entry (bullish), target 30% above. Holding period 60 days for `0-3m` timeframe, 180 for `3-12m`, 365 for `1-3y`.

### 7. Shadow Portfolio
Every decision (buy AND no_buy) is journaled with full reasoning + the complete feature vector. After 30+ days, this becomes both the backtest dataset AND the ML training set.

## The four risk gates

| Gate | Rule |
|---|---|
| **Position size** | Intended position ≤ $2,000 |
| **Concurrent positions** | ≤ 6 open buys at any time |
| **Sector concentration** | ≤ 40% of monthly cap in any one sector |
| **Circuit breaker** | Halt new entries when monthly deployed ≥ $10,000 |

ALL FOUR must pass for any signal to become a buy decision. Each gate's pass/fail is recorded in the `decisions` table for auditing.

Phase 4 will add daily/weekly P&L circuit breakers (currently no-op in shadow mode because there's no realized P&L to react to).

## Risk policy (cash-only, no margin)

```yaml
position:
  max_per_trade_usd: 2000
  max_concurrent_positions: 6
  max_per_sector_pct: 40            # of monthly cap
  max_per_ticker_lifetime_usd: 4000  # never average down past this

capital:
  monthly_deployment_cap_usd: 10000
  reserve_pct: 20

circuit_breakers:
  daily_loss_halt_pct: 10
  weekly_loss_halt_pct: 15
  consecutive_loss_count: 4

execution:
  default_mode: shadow
  shadow_first_n_trades: 999          # never auto-flip
  live_first_n_trades_require_approval: 10
  kill_switch_enabled: true

account:
  type: cash
  margin: false
  options: false
  shorts: false
  currency: USD
```

See `config/risk.yaml` for the live values.

## Mode lifecycle

```
shadow (default) ──manual flag──> paper ──manual flag──> live
```

| Mode | Behavior |
|---|---|
| `shadow` | Decisions journaled, no broker contacted. Used to accumulate the forward backtest. |
| `paper` | Decisions sent to IBKR's paper account. Phase 4 target. |
| `live` | Decisions hit the live IBKR account. Gated behind manual env-var flip + first 10 trades require manual approval. |

The `MODE` env var is the source of truth. Default is `shadow`. There is no in-app toggle. The flip is intentional friction.

## The review process

1. **Daily:** 5 scheduled scans run automatically (UAE timezone). The Railway scheduler service handles this — no human action required.
2. **Weekly:** Open the dashboard, review the Portfolio tab, look at the past week of buy decisions and their T+5/T+30 outcomes. Cull any signal patterns that consistently lose.
3. **Monthly:** Recalculate catalyst priors from the `outcomes` table (Phase 3 ML training). Update the conviction threshold if the data warrants it.
4. **Quarterly:** Add or remove sectors / catalysts based on what's actually generating P&L.

## From shadow to live (the kill switch)

Live trading is gated behind several barriers:

1. `MODE` env var must be explicitly set to `live`. Default is `shadow`.
2. IBKR account must be opened (DFSA Dubai branch) and funded.
3. First 10 live trades require manual approval (not yet wired in code; planned for Phase 4).
4. Daily/weekly loss circuit breakers halt new entries automatically.
5. Kill switch in the admin page (TODO) instantly flips back to shadow mode.

We don't flip to live until the Shadow Portfolio shows consistent edge. **Target gates** before flipping:
- ≥ 60% hit rate (signals where T+30 return > 0)
- OR ≥ +1.0 Sharpe-equivalent
- AND at least 30 mature signals (T+30 elapsed) in the journal
- AND a blended return signal that beats SPY over the same window

If the system can't clear those after 6 months, **kill it** and write a post-mortem.

## What "edge" actually means here

LLMs reading public news rarely beat the market on widely-covered stocks. By the time the headline crosses the wire, the price has moved. The edge — if there is one — comes from:

1. **Speed** to events the market is slow to digest
2. **Breadth** — covering 500 micro-cap miners no analyst follows
3. **Cross-referencing** that a human can't hold in their head simultaneously
4. **Discipline** — sizing/stops a human won't enforce alone
5. **Niche depth** — pre-built catalyst playbooks for specific sub-sectors (e.g. China-biotech-to-FDA)

The system's job is to maximize hit rate × payoff while minimizing ruin probability. The risk policy exists to prevent blowing up during a bad month, which is the only way to eventually capture the upside.
