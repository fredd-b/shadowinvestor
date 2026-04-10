import { getStatus, getPortfolio, getSourcesHealth } from "@/lib/api";
import { formatCount, formatUsd } from "@/lib/format";
import Nav from "@/components/Nav";
import { StatRow } from "@/components/StatRow";
import RunPipelineButton from "./RunPipelineButton";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const [status, portfolio, sources] = await Promise.all([
    getStatus().catch(() => null),
    getPortfolio("shadow").catch(() => null),
    getSourcesHealth().catch(() => []),
  ]);

  const totalRawItems = sources.reduce((s, x) => s + x.items_total, 0);
  const activeSources = sources.filter((s) => s.active).length;

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="mb-2 text-3xl font-bold">Admin · One-Click Operations</h1>
        <p className="mb-6 text-sm text-zinc-400">
          Trigger the pipeline manually or change runtime settings here.
        </p>

        <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="mb-4 text-lg font-semibold">System</h2>
            <dl className="space-y-2 text-sm">
              <StatRow label="Mode" value={status?.mode ?? "?"} />
              <StatRow label="Environment" value={status?.environment ?? "?"} />
              <StatRow label="Timezone" value={status?.timezone ?? "?"} />
              <StatRow label="Version" value={status?.version ?? "?"} />
              <StatRow
                label="LLM scorer"
                value={status?.has_anthropic ? "claude" : "fallback (no key)"}
                tone={status?.has_anthropic ? "good" : "warn"}
              />
              <StatRow
                label="Pushover"
                value={status?.has_pushover ? "configured" : "off"}
                tone={status?.has_pushover ? "good" : "default"}
              />
              <StatRow
                label="Telegram"
                value={status?.has_telegram ? "configured" : "off"}
                tone={status?.has_telegram ? "good" : "default"}
              />
            </dl>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="mb-4 text-lg font-semibold">Stats</h2>
            <dl className="space-y-2 text-sm">
              <StatRow
                label="Active sources"
                value={`${activeSources}/${sources.length}`}
              />
              <StatRow
                label="Raw items collected"
                value={formatCount(totalRawItems)}
              />
              <StatRow
                label="Open buys (shadow)"
                value={portfolio?.open_buy_count ?? 0}
              />
              <StatRow
                label="Deployed this month"
                value={formatUsd(portfolio?.deployed_this_month_usd ?? 0)}
              />
              <StatRow
                label="Monthly cap"
                value={formatUsd(portfolio?.monthly_cap_usd ?? 0)}
              />
              <StatRow
                label="Cap used"
                value={`${portfolio?.cap_used_pct?.toFixed(0) ?? "0"}%`}
              />
            </dl>
          </div>
        </div>

        {/* One-click controls */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <h2 className="mb-4 text-lg font-semibold">One-click operations</h2>
          <div className="space-y-3">
            <RunPipelineButton />
            <p className="text-xs text-zinc-500">
              <strong>Run pipeline:</strong> Fetches the last 48h of news from
              all active sources, classifies + scores each signal, and
              generates shadow buy/no_buy decisions. Same as the scheduled
              5x/day runs but on-demand.
            </p>
          </div>
        </div>

        {/* Risk policy reminder */}
        <div className="mt-8 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-6">
          <h2 className="mb-3 text-lg font-semibold text-yellow-300">
            Risk policy (shadow mode)
          </h2>
          <ul className="space-y-1 text-sm text-zinc-300">
            <li>• Max $2,000 per trade</li>
            <li>• Max 6 concurrent positions</li>
            <li>• Max 40% of monthly cap in any one sector</li>
            <li>• Monthly deployment cap: $10,000</li>
            <li>• Daily loss circuit breaker: -10%</li>
            <li>• Weekly loss circuit breaker: -15%</li>
            <li>• Cash account, no margin, no options, no shorts</li>
            <li>• All trades shadow-mode until explicit live flip</li>
          </ul>
        </div>
      </main>
    </>
  );
}
