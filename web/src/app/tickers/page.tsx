import { getTickers } from "@/lib/api";
import type { Ticker } from "@/lib/types";
import Nav from "@/components/Nav";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function TickersPage() {
  const tickers: Ticker[] = await getTickers(true).catch(() => []);

  // Group by sector
  const bySector: Record<string, Ticker[]> = {};
  for (const t of tickers) {
    const k = t.sector || "other";
    if (!bySector[k]) bySector[k] = [];
    bySector[k].push(t);
  }

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="mb-2 text-3xl font-bold">Watchlist</h1>
        <p className="mb-6 text-sm text-zinc-400">{tickers.length} tickers</p>

        <div className="space-y-6">
          {Object.entries(bySector).map(([sector, list]) => (
            <div key={sector}>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                {sector} · {list.length}
              </h2>
              <div className="overflow-hidden rounded-lg border border-zinc-800">
                <table className="w-full text-sm">
                  <tbody>
                    {list.map((t) => (
                      <tr
                        key={t.id}
                        className="border-b border-zinc-800 last:border-b-0 hover:bg-zinc-900/50"
                      >
                        <td className="px-4 py-3 w-32">
                          <Link
                            href={`/tickers/${encodeURIComponent(t.symbol)}`}
                            className="font-mono text-yellow-400"
                          >
                            {t.symbol}
                          </Link>
                          <span className="ml-2 text-xs text-zinc-500">{t.exchange}</span>
                        </td>
                        <td className="px-4 py-3 w-64 text-zinc-200">{t.name}</td>
                        <td className="px-4 py-3 text-zinc-400">
                          {t.watchlist_thesis}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </main>
    </>
  );
}
