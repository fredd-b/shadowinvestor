import { getSignals, getStatus } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import Nav from "@/components/Nav";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string; min?: string }>;
}) {
  const params = await searchParams;
  const days = parseInt(params.days || "7", 10);
  const minConviction = params.min ? parseFloat(params.min) : undefined;

  const [signals, status] = await Promise.all([
    getSignals({ days, minConviction }).catch(() => []),
    getStatus().catch(() => null),
  ]);

  const top = signals.slice(0, 50);

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6 flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-bold">Recent Signals</h1>
            <p className="text-sm text-zinc-400">
              Last {days} days · {signals.length} signals
              {minConviction != null && ` · conviction ≥ ${minConviction}`}
            </p>
          </div>
          {status && (
            <div className="text-right text-xs text-zinc-500">
              <div>
                mode: <span className="text-zinc-300">{status.mode}</span>
              </div>
              <div>
                LLM:{" "}
                <span className="text-zinc-300">
                  {status.has_anthropic ? "claude" : "fallback"}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="mb-4 flex flex-wrap gap-2 text-sm">
          {[1, 3, 7, 14, 30].map((d) => (
            <Link
              key={d}
              href={`/?days=${d}${minConviction ? `&min=${minConviction}` : ""}`}
              className={`rounded px-3 py-1 ${
                d === days
                  ? "bg-zinc-100 text-zinc-900"
                  : "border border-zinc-800 text-zinc-300 hover:bg-zinc-900"
              }`}
            >
              {d}d
            </Link>
          ))}
          <span className="ml-4 self-center text-zinc-500">conviction:</span>
          {[0, 6, 12, 18].map((c) => (
            <Link
              key={c}
              href={`/?days=${days}&min=${c}`}
              className={`rounded px-3 py-1 ${
                c === (minConviction ?? 0)
                  ? "bg-zinc-100 text-zinc-900"
                  : "border border-zinc-800 text-zinc-300 hover:bg-zinc-900"
              }`}
            >
              ≥ {c}
            </Link>
          ))}
        </div>

        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-4 py-3">When</th>
                <th className="px-4 py-3">Ticker</th>
                <th className="px-4 py-3">Catalyst</th>
                <th className="px-4 py-3">Sector</th>
                <th className="px-4 py-3 text-right">Conviction</th>
                <th className="px-4 py-3 text-right">I/P</th>
                <th className="px-4 py-3">Headline</th>
                <th className="px-4 py-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody>
              {top.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-zinc-500">
                    No signals in this window. Trigger a pipeline run from the API.
                  </td>
                </tr>
              ) : (
                top.map((s) => {
                  const isWatchlist = s.feature_is_watchlist === 1;
                  return (
                    <tr
                      key={s.id}
                      className="border-t border-zinc-800 hover:bg-zinc-900/50"
                    >
                      <td className="px-4 py-3 text-zinc-500">
                        {formatTimestamp(s.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        {s.ticker_symbol ? (
                          <Link
                            href={`/tickers/${encodeURIComponent(s.ticker_symbol)}`}
                            className={`font-mono ${
                              isWatchlist ? "text-yellow-400" : "text-zinc-300"
                            }`}
                          >
                            {s.ticker_symbol}
                          </Link>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{s.catalyst_type}</td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{s.sector}</td>
                      <td className="px-4 py-3 text-right font-mono text-zinc-200">
                        {s.conviction_score.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-zinc-500">
                        {s.impact_score}/{s.probability_score}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        <Link
                          href={`/signals/${s.id}`}
                          className="hover:text-zinc-100 hover:underline"
                        >
                          {s.headline}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {s.user_action ? (
                          <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
                            s.user_action === "invest"
                              ? "bg-green-600/20 text-green-400"
                              : s.user_action === "skip"
                              ? "bg-zinc-700/50 text-zinc-500"
                              : "bg-yellow-600/20 text-yellow-400"
                          }`}>
                            {s.user_action}
                          </span>
                        ) : (
                          <span className="text-zinc-700">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}
