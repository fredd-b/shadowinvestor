import { getTickers } from "@/lib/api";
import type { Ticker } from "@/lib/types";
import Nav from "@/components/Nav";
import AddTickerForm from "@/components/AddTickerForm";
import Link from "next/link";

export const dynamic = "force-dynamic";

const STATUS_COLORS: Record<string, string> = {
  monitoring: "bg-blue-600/20 text-blue-400",
  considering: "bg-yellow-600/20 text-yellow-400",
  invested: "bg-green-600/20 text-green-400",
  paused: "bg-zinc-700/50 text-zinc-500",
  archived: "bg-red-600/20 text-red-400",
};

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
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Watchlist</h1>
            <p className="text-sm text-zinc-400">{tickers.length} tickers</p>
          </div>
          <AddTickerForm />
        </div>

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
                        <td className="px-4 py-3 w-48 text-zinc-200">{t.name}</td>
                        <td className="px-4 py-3 w-24">
                          <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
                            STATUS_COLORS[t.lifecycle_status] || "bg-zinc-800 text-zinc-400"
                          }`}>
                            {t.lifecycle_status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-zinc-400 text-xs">
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
