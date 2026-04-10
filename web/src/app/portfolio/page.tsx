import { getPortfolio, getDecisions } from "@/lib/api";
import { formatTimestamp, formatUsd, formatPrice } from "@/lib/format";
import Nav from "@/components/Nav";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function PortfolioPage() {
  const [portfolio, decisions] = await Promise.all([
    getPortfolio("shadow").catch(() => null),
    getDecisions({ mode: "shadow", action: "buy", limit: 50 }).catch(() => []),
  ]);

  if (!portfolio) {
    return (
      <>
        <Nav />
        <main className="mx-auto max-w-7xl px-6 py-8">
          <p className="text-red-400">Failed to load portfolio.</p>
        </main>
      </>
    );
  }

  const sectorRows = Object.entries(portfolio.sector_exposure).sort(
    (a, b) => b[1] - a[1]
  );

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="mb-6 text-3xl font-bold">Shadow Portfolio</h1>

        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
            <div className="text-xs uppercase text-zinc-500">Deployed (lifetime)</div>
            <div className="mt-2 text-2xl font-bold">
              {formatUsd(portfolio.deployed_total_usd)}
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
            <div className="text-xs uppercase text-zinc-500">This month</div>
            <div className="mt-2 text-2xl font-bold">
              {formatUsd(portfolio.deployed_this_month_usd)}
            </div>
            <div className="mt-1 text-xs text-zinc-500">
              {portfolio.cap_used_pct.toFixed(0)}% of {formatUsd(portfolio.monthly_cap_usd)} cap
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full bg-yellow-500"
                style={{
                  width: `${Math.min(100, portfolio.cap_used_pct).toFixed(1)}%`,
                }}
              />
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
            <div className="text-xs uppercase text-zinc-500">Open buys</div>
            <div className="mt-2 text-2xl font-bold">{portfolio.open_buy_count}</div>
          </div>
        </div>

        {sectorRows.length > 0 && (
          <div className="mb-8">
            <h2 className="mb-3 text-xl font-semibold">Sector exposure</h2>
            <div className="overflow-hidden rounded-lg border border-zinc-800">
              <table className="w-full text-sm">
                <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
                  <tr>
                    <th className="px-4 py-3">Sector</th>
                    <th className="px-4 py-3 text-right">Deployed USD</th>
                    <th className="px-4 py-3 text-right">% of cap</th>
                  </tr>
                </thead>
                <tbody>
                  {sectorRows.map(([sec, amt]) => (
                    <tr key={sec} className="border-t border-zinc-800">
                      <td className="px-4 py-3 text-zinc-300">{sec}</td>
                      <td className="px-4 py-3 text-right font-mono">
                        {formatUsd(amt)}
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-500">
                        {((amt / portfolio.monthly_cap_usd) * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div>
          <h2 className="mb-3 text-xl font-semibold">Recent buy decisions</h2>
          {decisions.length === 0 ? (
            <p className="text-zinc-500">No buy decisions yet.</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-zinc-800">
              <table className="w-full text-sm">
                <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
                  <tr>
                    <th className="px-4 py-3">When</th>
                    <th className="px-4 py-3">Ticker</th>
                    <th className="px-4 py-3">Catalyst</th>
                    <th className="px-4 py-3 text-right">Conv.</th>
                    <th className="px-4 py-3 text-right">Size</th>
                    <th className="px-4 py-3 text-right">Entry</th>
                    <th className="px-4 py-3 text-right">Stop</th>
                    <th className="px-4 py-3 text-right">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((d) => (
                    <tr key={d.id} className="border-t border-zinc-800">
                      <td className="px-4 py-3 text-zinc-500">
                        {formatTimestamp(d.decided_at)}
                      </td>
                      <td className="px-4 py-3">
                        {d.ticker_symbol ? (
                          <Link
                            href={`/tickers/${encodeURIComponent(d.ticker_symbol)}`}
                            className="font-mono text-yellow-400"
                          >
                            {d.ticker_symbol}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{d.catalyst_type}</td>
                      <td className="px-4 py-3 text-right font-mono">
                        {d.conviction_score.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {formatUsd(d.intended_position_usd)}
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-400">
                        {formatPrice(d.intended_entry_price)}
                      </td>
                      <td className="px-4 py-3 text-right text-red-400">
                        {formatPrice(d.intended_stop_loss)}
                      </td>
                      <td className="px-4 py-3 text-right text-green-400">
                        {formatPrice(d.intended_target)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
