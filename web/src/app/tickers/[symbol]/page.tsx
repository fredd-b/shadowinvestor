import { getTicker, getTickerSignals } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import Nav from "@/components/Nav";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function TickerPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;
  const decoded = decodeURIComponent(symbol);

  let ticker;
  try {
    ticker = await getTicker(decoded);
  } catch {
    notFound();
  }

  const signals = await getTickerSignals(decoded, 100).catch(() => []);

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Link href="/tickers" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Watchlist
        </Link>
        <div className="mt-2 mb-6">
          <h1 className="font-mono text-3xl font-bold text-yellow-400">
            {ticker.symbol}
            <span className="ml-3 text-base font-normal text-zinc-500">
              {ticker.exchange}
            </span>
          </h1>
          <p className="mt-1 text-xl text-zinc-200">{ticker.name}</p>
          <p className="mt-1 text-sm text-zinc-500">{ticker.sector}</p>
          {ticker.watchlist_thesis && (
            <div className="mt-4 rounded border-l-2 border-yellow-500/50 bg-yellow-500/5 p-3 text-sm text-zinc-300">
              {ticker.watchlist_thesis}
            </div>
          )}
        </div>

        <h2 className="mb-3 text-xl font-semibold">
          Signals · {signals.length}
        </h2>
        {signals.length === 0 ? (
          <p className="text-zinc-500">No signals for this ticker yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
                <tr>
                  <th className="px-4 py-3">When</th>
                  <th className="px-4 py-3">Catalyst</th>
                  <th className="px-4 py-3 text-right">Conviction</th>
                  <th className="px-4 py-3">Headline</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((s) => (
                  <tr key={s.id} className="border-t border-zinc-800">
                    <td className="px-4 py-3 text-zinc-500">
                      {formatTimestamp(s.created_at)}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{s.catalyst_type}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      {s.conviction_score.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-zinc-300">{s.headline}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </>
  );
}
