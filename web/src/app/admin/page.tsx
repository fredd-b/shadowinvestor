import { getStatus, getPortfolio, getSourcesHealth } from "@/lib/api";
import Nav from "@/components/Nav";
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
          {/* System status card */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="mb-4 text-lg font-semibold">System</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-zinc-500">Mode</dt>
                <dd className="font-mono text-zinc-100">{status?.mode ?? "?"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Environment</dt>
                <dd className="font-mono text-zinc-100">
                  {status?.environment ?? "?"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Timezone</dt>
                <dd className="font-mono text-zinc-100">
                  {status?.timezone ?? "?"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Version</dt>
                <dd className="font-mono text-zinc-100">{status?.version ?? "?"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">LLM scorer</dt>
                <dd
                  className={`font-mono ${
                    status?.has_anthropic ? "text-green-400" : "text-yellow-400"
                  }`}
                >
                  {status?.has_anthropic ? "claude" : "fallback (no key)"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Pushover</dt>
                <dd
                  className={`font-mono ${
                    status?.has_pushover ? "text-green-400" : "text-zinc-500"
                  }`}
                >
                  {status?.has_pushover ? "configured" : "off"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Telegram</dt>
                <dd
                  className={`font-mono ${
                    status?.has_telegram ? "text-green-400" : "text-zinc-500"
                  }`}
                >
                  {status?.has_telegram ? "configured" : "off"}
                </dd>
              </div>
            </dl>
          </div>

          {/* Stats card */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="mb-4 text-lg font-semibold">Stats</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-zinc-500">Active sources</dt>
                <dd className="font-mono text-zinc-100">
                  {activeSources}/{sources.length}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Raw items collected</dt>
                <dd className="font-mono text-zinc-100">
                  {totalRawItems.toLocaleString()}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Open buys (shadow)</dt>
                <dd className="font-mono text-zinc-100">
                  {portfolio?.open_buy_count ?? 0}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Deployed this month</dt>
                <dd className="font-mono text-zinc-100">
                  ${portfolio?.deployed_this_month_usd?.toFixed(0) ?? "0"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Monthly cap</dt>
                <dd className="font-mono text-zinc-100">
                  ${portfolio?.monthly_cap_usd?.toFixed(0) ?? "0"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Cap used</dt>
                <dd className="font-mono text-zinc-100">
                  {portfolio?.cap_used_pct?.toFixed(0) ?? "0"}%
                </dd>
              </div>
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
