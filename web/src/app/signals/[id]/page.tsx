import { getSignal } from "@/lib/api";
import Nav from "@/components/Nav";
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

        {/* Scoring grid */}
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Catalyst" value={signal.catalyst_type} />
          <Stat label="Direction" value={signal.direction} />
          <Stat label="Timeframe" value={signal.timeframe_bucket} />
          <Stat label="Sector" value={signal.sector} />
          <Stat label="Impact" value={`${signal.impact_score}/5`} />
          <Stat label="Probability" value={`${signal.probability_score}/5`} />
          <Stat label="Conviction" value={signal.conviction_score.toFixed(1)} />
          <Stat
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
                      ? `$${signal.feature_market_cap_usd.toLocaleString()}`
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

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="text-xs uppercase text-zinc-500">{label}</div>
      <div className="mt-1 font-mono text-sm text-zinc-100">{value}</div>
    </div>
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
