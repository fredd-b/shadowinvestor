import Nav from "@/components/Nav";

export default function FrameworkPage() {
  return (
    <>
      <Nav />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <h1 className="mb-2 text-3xl font-bold">Decision Framework</h1>
        <p className="mb-8 text-sm text-zinc-400">
          The mission, the rules, and the review process — in one place.
        </p>

        <Section title="Mission">
          <p>
            Make money on personal trades by detecting high-conviction,
            niche-sector catalysts faster and more systematically than reading
            news manually, with eventual semi-automated execution through
            Interactive Brokers (DFSA Dubai branch).
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            Stretch target: <strong>+50% blended annual</strong>. Realistic-but-good:{" "}
            <strong>20–30%</strong>. Kill threshold: <strong>below +10%</strong>.
          </p>
        </Section>

        <Section title="What we monitor">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Sector name="Biotech / Pharma (Global)" desc="FDA decisions, pivotal trial readouts, licensing deals" />
            <Sector name="China Biotech → FDA Pipeline" desc="Chinese biotechs tracking toward US FDA submission/approval — DEDICATED edge area" highlight />
            <Sector name="AI Infrastructure" desc="GPU cloud, data center REITs, optics/semis, design wins" />
            <Sector name="Crypto Miners → AI/HPC" desc="BTC miners pivoting to AI hosting contracts" />
            <Sector name="Commodities — Uranium / Gold / Critical Minerals" desc="Mine milestones, offtakes, reserve upgrades" />
            <Sector name="Other Binary-Catalyst Sectors" desc="Defense awards, large buybacks, guidance changes" />
          </div>
        </Section>

        <Section title="How a signal becomes a buy">
          <div className="space-y-3">
            <Step n="1" title="Multi-source ingest">
              SEC EDGAR (8-K/6-K), FDA OpenFDA, ClinicalTrials.gov v2, and
              press wires (PR Newswire, GlobeNewswire, BusinessWire) are
              fetched 5x daily in UAE timezone (15:00, 18:00, 22:00, 02:00, 08:00).
            </Step>
            <Step n="2" title="Normalize + cross-source dedup">
              Items with title similarity ≥ 0.85 are merged into one
              candidate signal. Source count and source diversity become
              ML features.
            </Step>
            <Step n="3" title="Classify + score">
              Each candidate is classified into one of 28 catalyst types (FDA
              approval, Phase 3 readout, offtake signing, etc.) and scored
              on impact (1–5) × probability (1–5). Uses Claude when{" "}
              <code className="text-yellow-400">ANTHROPIC_API_KEY</code> is set,
              deterministic pattern matching otherwise.
            </Step>
            <Step n="4" title="Cross-reference boost">
              Single source: <code>1.00×</code>. Two distinct sources:{" "}
              <code>1.15×</code>. Three+ sources OR any regulatory source:{" "}
              <code>1.30×</code>. Conviction =
              impact × probability × multiplier.
            </Step>
            <Step n="5" title="Decision engine">
              Conviction must be ≥ <strong>12.0</strong> (10.0 if the ticker
              is on the watchlist). Then ALL FOUR risk gates must pass.
            </Step>
            <Step n="6" title="Position sizing">
              Conviction-scaled fixed-risk: 0.5× max at conviction 12, scaling
              linearly to 1.0× max at conviction 25. Max <strong>$2,000</strong>{" "}
              per trade. Stop loss 12% below entry (bullish), target 30% above.
            </Step>
            <Step n="7" title="Shadow Portfolio">
              Every decision (buy AND no_buy) is journaled with full reasoning
              and the complete feature vector. After 30+ days, this becomes
              both the backtest dataset AND the ML training set.
            </Step>
          </div>
        </Section>

        <Section title="The four risk gates">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Gate title="Position size" desc="Intended position ≤ $2,000" />
            <Gate title="Concurrent positions" desc="≤ 6 open buys at any time" />
            <Gate title="Sector concentration" desc="≤ 40% of monthly cap in any one sector" />
            <Gate title="Circuit breaker" desc="Halt new entries when monthly deployed ≥ $10,000" />
          </div>
          <p className="mt-3 text-sm text-zinc-500">
            ALL FOUR must pass for any signal to become a buy decision. Each
            gate's pass/fail is recorded in the database for auditing.
          </p>
        </Section>

        <Section title="Risk policy (cash-only, no margin)">
          <ul className="space-y-1 text-sm">
            <li>
              <Code>max_per_trade_usd</Code>: <strong>$2,000</strong>
            </li>
            <li>
              <Code>max_concurrent_positions</Code>: <strong>6</strong>
            </li>
            <li>
              <Code>max_per_sector_pct</Code>: <strong>40%</strong> of monthly cap
            </li>
            <li>
              <Code>monthly_deployment_cap_usd</Code>: <strong>$10,000</strong>
            </li>
            <li>
              <Code>daily_loss_halt_pct</Code>: <strong>−10%</strong>
            </li>
            <li>
              <Code>weekly_loss_halt_pct</Code>: <strong>−15%</strong>
            </li>
            <li>
              <Code>account.type</Code>: <strong>cash</strong> (no margin, no
              options, no shorts, USD)
            </li>
          </ul>
        </Section>

        <Section title="Mode lifecycle">
          <div className="space-y-2 text-sm">
            <Mode name="shadow" current desc="Default. Decisions are journaled but no broker is contacted. Used to accumulate the forward backtest." />
            <Mode name="paper" desc="Decisions are sent to IBKR's paper account (Phase 4 target)." />
            <Mode name="live" desc="Decisions hit the live IBKR account. Gated behind manual env-var flip + first 10 trades require manual approval." />
          </div>
          <p className="mt-3 text-sm text-zinc-500">
            Mode is set via the <Code>MODE</Code> environment variable. Default
            is <Code>shadow</Code> so live trading never happens by accident.
          </p>
        </Section>

        <Section title="The review process">
          <ol className="ml-4 list-decimal space-y-2 text-sm">
            <li>
              <strong>Daily:</strong> 5 scheduled scans run automatically (UAE
              timezone). The scheduler service handles this — no human action.
            </li>
            <li>
              <strong>Weekly:</strong> Open the dashboard, look at the
              Portfolio tab, review the past week of buy decisions and their
              T+5/T+30 outcomes. Cull any signal patterns that consistently lose.
            </li>
            <li>
              <strong>Monthly:</strong> Recalculate catalyst priors from the
              outcomes table (Phase 3 ML training). Update the conviction
              threshold if the data warrants it.
            </li>
            <li>
              <strong>Quarterly:</strong> Add or remove sectors / catalysts based
              on what's actually generating P&L.
            </li>
          </ol>
        </Section>

        <Section title="From shadow to live (the kill switch)">
          <p className="text-sm">
            Live trading is gated behind several barriers:
          </p>
          <ul className="mt-2 ml-4 list-disc space-y-1 text-sm text-zinc-300">
            <li>
              <Code>MODE</Code> env var must be explicitly set to{" "}
              <Code>live</Code>. Default is <Code>shadow</Code>.
            </li>
            <li>
              IBKR account must be opened (DFSA Dubai branch) and funded.
            </li>
            <li>
              First 10 live trades require manual approval (not yet wired).
            </li>
            <li>
              Daily/weekly loss circuit breakers halt new entries automatically.
            </li>
            <li>
              Kill switch in the admin page (TODO) instantly flips back to
              shadow mode.
            </li>
          </ul>
          <p className="mt-3 text-sm text-zinc-500">
            We don't flip to live until the Shadow Portfolio shows consistent
            edge (target: ≥ 60% hit rate or ≥ +1.0 Sharpe-equivalent on at
            least 30 mature signals).
          </p>
        </Section>
      </main>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="mb-3 text-xl font-semibold text-zinc-100">{title}</h2>
      <div className="text-zinc-300">{children}</div>
    </section>
  );
}

function Sector({ name, desc, highlight }: { name: string; desc: string; highlight?: boolean }) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        highlight
          ? "border-yellow-500/30 bg-yellow-500/5"
          : "border-zinc-800 bg-zinc-900"
      }`}
    >
      <div className="font-semibold text-zinc-100">{name}</div>
      <div className="mt-1 text-xs text-zinc-400">{desc}</div>
    </div>
  );
}

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="mb-1 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-yellow-500 text-xs font-bold text-zinc-950">
          {n}
        </span>
        <span className="font-semibold">{title}</span>
      </div>
      <div className="ml-8 text-sm text-zinc-400">{children}</div>
    </div>
  );
}

function Gate({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
      <div className="font-semibold text-zinc-100">{title}</div>
      <div className="mt-1 text-xs text-zinc-400">{desc}</div>
    </div>
  );
}

function Mode({ name, desc, current }: { name: string; desc: string; current?: boolean }) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="flex items-center gap-2">
        <code className="font-mono font-semibold text-zinc-100">{name}</code>
        {current && (
          <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs text-green-300">
            current
          </span>
        )}
      </div>
      <div className="mt-1 text-xs text-zinc-400">{desc}</div>
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-zinc-300">
      {children}
    </code>
  );
}
