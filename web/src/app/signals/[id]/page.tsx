import { getSignal } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import Nav from "@/components/Nav";
import SignalActionButtons from "@/components/SignalActionButtons";
import { StatTile } from "@/components/StatRow";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function SignalPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const sid = parseInt(id, 10);
  if (Number.isNaN(sid)) notFound();

  let signal;
  try {
    signal = await getSignal(sid);
  } catch {
    notFound();
  }

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Signals
        </Link>

        <div className="mt-2 mb-6">
          <div className="flex items-baseline gap-3">
            {signal.ticker_symbol && (
              <Link
                href={`/tickers/${encodeURIComponent(signal.ticker_symbol)}`}
                className="font-mono text-3xl font-bold text-yellow-400"
              >
                {signal.ticker_symbol}
              </Link>
            )}
            {signal.ticker_name && (
              <span className="text-xl text-zinc-300">{signal.ticker_name}</span>
            )}
            <span className="ml-auto rounded bg-zinc-800 px-3 py-1 font-mono text-lg text-zinc-100">
              {signal.conviction_score.toFixed(1)}
            </span>
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-zinc-100">
            {signal.headline}
          </h1>
        </div>

        {/* Action buttons */}
        <div className="mb-6 flex items-center gap-4 rounded-lg border border-zinc-700 bg-zinc-900/50 p-4">
          <span className="text-sm text-zinc-500">Your call:</span>
          <SignalActionButtons signalId={signal.id} currentAction={signal.user_action} />
          {signal.user_action && (
            <span className="ml-auto text-xs text-zinc-500">
              Current: <span className="text-zinc-300 font-semibold">{signal.user_action}</span>
            </span>
          )}
        </div>

        {/* Summary */}
        <div className="mb-6 rounded-lg border border-zinc-800 bg-zinc-900 p-5">
          <p className="text-zinc-300">{signal.summary}</p>
          {signal.economics_summary && (
            <p className="mt-3 text-sm">
              <span className="text-zinc-500">Economics: </span>
              <span className="text-yellow-300">{signal.economics_summary}</span>
            </p>
          )}
        </div>

        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile label="Catalyst" value={signal.catalyst_type} />
          <StatTile label="Direction" value={signal.direction} />
          <StatTile label="Timeframe" value={signal.timeframe_bucket} />
          <StatTile label="Sector" value={signal.sector} />
          <StatTile label="Impact" value={`${signal.impact_score}/5`} />
          <StatTile label="Probability" value={`${signal.probability_score}/5`} />
          <StatTile label="Conviction" value={signal.conviction_score.toFixed(1)} />
          <StatTile
            label="Watchlist"
            value={signal.feature_is_watchlist === 1 ? "yes" : "no"}
          />
        </div>

        {/* ML feature vector */}
        <div className="mb-6">
          <h2 className="mb-3 text-lg font-semibold">ML feature vector</h2>
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <tbody>
                <FeatureRow
                  label="feature_source_count"
                  value={signal.feature_source_count}
                />
                <FeatureRow
                  label="feature_source_diversity"
                  value={signal.feature_source_diversity}
                />
                <FeatureRow
                  label="feature_source_quality_avg"
                  value={signal.feature_source_quality_avg}
                />
                <FeatureRow
                  label="feature_market_cap_bucket"
                  value={signal.feature_market_cap_bucket}
                />
                <FeatureRow
                  label="feature_market_cap_usd"
                  value={
                    signal.feature_market_cap_usd
                      ? formatUsd(signal.feature_market_cap_usd)
                      : null
                  }
                />
                <FeatureRow
                  label="feature_is_watchlist"
                  value={signal.feature_is_watchlist}
                />
              </tbody>
            </table>
          </div>
        </div>

        <div className="mb-6 rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-xs text-zinc-500">
          <div>
            <strong>Created:</strong> {signal.created_at}
          </div>
          <div>
            <strong>Event at:</strong> {signal.event_at}
          </div>
          <div>
            <strong>Status:</strong> {signal.status}
          </div>
          <div>
            <strong>ID:</strong> {signal.id}
          </div>
        </div>
      </main>
    </>
  );
}

function FeatureRow({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  return (
    <tr className="border-b border-zinc-800 last:border-b-0">
      <td className="px-4 py-2 font-mono text-xs text-zinc-500">{label}</td>
      <td className="px-4 py-2 font-mono text-zinc-200">
        {value === null || value === undefined ? "—" : value}
      </td>
    </tr>
  );
}
