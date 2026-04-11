import { getPositions } from "@/lib/api";
import { formatTimestamp, formatUsd, formatPrice } from "@/lib/format";
import Nav from "@/components/Nav";
import SellButton from "@/components/SellButton";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function PortfolioPage() {
  const [open, closed] = await Promise.all([
    getPositions("shadow", "open").catch(() => []),
    getPositions("shadow", "closed").catch(() => []),
  ]);
  const partial = await getPositions("shadow", "partial_closed").catch(() => []);
  const allOpen = [...open, ...partial];

  const totalInvested = allOpen.reduce((s, p) => s + p.cost_basis_usd, 0);
  const totalUnrealized = allOpen.reduce((s, p) => s + (p.unrealized_pnl_usd ?? 0), 0);
  const totalRealized = closed.reduce((s, p) => s + p.realized_pnl_usd, 0);
  const wins = closed.filter((p) => p.realized_pnl_usd > 0).length;
  const winRate = closed.length > 0 ? Math.round((wins / closed.length) * 100) : null;

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="mb-2 text-3xl font-bold">Shadow Portfolio</h1>
        <p className="mb-6 text-sm text-zinc-400">
          {allOpen.length} open · {closed.length} closed
        </p>

        {/* Summary cards */}
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard label="Invested" value={formatUsd(totalInvested)} />
          <StatCard
            label="Unrealized P&L"
            value={`${totalUnrealized >= 0 ? "+" : ""}${formatUsd(totalUnrealized)}`}
            tone={totalUnrealized >= 0 ? "good" : "bad"}
          />
          <StatCard
            label="Realized P&L"
            value={`${totalRealized >= 0 ? "+" : ""}${formatUsd(totalRealized)}`}
            tone={totalRealized >= 0 ? "good" : "bad"}
          />
          <StatCard
            label="Win Rate"
            value={winRate !== null ? `${winRate}%` : "—"}
            tone={winRate !== null && winRate >= 50 ? "good" : "default"}
          />
        </div>

        {/* Open positions */}
        <h2 className="mb-3 text-lg font-semibold">Open Positions</h2>
        {allOpen.length === 0 ? (
          <div className="mb-8 rounded-lg border border-zinc-800 p-8 text-center text-zinc-500">
            No open positions. Mark a signal as &quot;Invest&quot; to open one.
          </div>
        ) : (
          <div className="mb-8 overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Ticker</th>
                  <th className="px-4 py-3">Sector</th>
                  <th className="px-4 py-3 text-right">Entry</th>
                  <th className="px-4 py-3 text-right">Current</th>
                  <th className="px-4 py-3 text-right">P&L $</th>
                  <th className="px-4 py-3 text-right">P&L %</th>
                  <th className="px-4 py-3 text-right">Shares</th>
                  <th className="px-4 py-3">Opened</th>
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {allOpen.map((p) => {
                  const remaining = p.shares_held - p.shares_sold;
                  const pnl = p.unrealized_pnl_usd ?? 0;
                  const pnlPct = p.pnl_pct ?? 0;
                  return (
                    <tr key={p.id} className="border-t border-zinc-800 hover:bg-zinc-900/50">
                      <td className="px-4 py-3">
                        <Link
                          href={`/tickers/${encodeURIComponent(p.ticker_symbol ?? "")}`}
                          className="font-mono text-yellow-400"
                        >
                          {p.ticker_symbol}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{p.sector}</td>
                      <td className="px-4 py-3 text-right font-mono">{formatPrice(p.entry_price)}</td>
                      <td className="px-4 py-3 text-right font-mono">{p.current_price ? formatPrice(p.current_price) : "—"}</td>
                      <td className={`px-4 py-3 text-right font-mono ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {pnl >= 0 ? "+" : ""}{formatUsd(pnl)}
                      </td>
                      <td className={`px-4 py-3 text-right font-mono ${pnlPct >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{remaining}</td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{formatTimestamp(p.opened_at)}</td>
                      <td className="px-4 py-3">
                        <SellButton positionId={p.id} sharesRemaining={remaining} ticker={p.ticker_symbol ?? "?"} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Closed positions */}
        {closed.length > 0 && (
          <>
            <h2 className="mb-3 text-lg font-semibold">Trade Journal (Closed)</h2>
            <div className="overflow-hidden rounded-lg border border-zinc-800">
              <table className="w-full text-sm">
                <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
                  <tr>
                    <th className="px-4 py-3">Ticker</th>
                    <th className="px-4 py-3 text-right">Entry</th>
                    <th className="px-4 py-3 text-right">Exit</th>
                    <th className="px-4 py-3 text-right">P&L</th>
                    <th className="px-4 py-3">Catalyst</th>
                    <th className="px-4 py-3">Opened</th>
                    <th className="px-4 py-3">Closed</th>
                  </tr>
                </thead>
                <tbody>
                  {closed.map((p) => (
                    <tr key={p.id} className="border-t border-zinc-800">
                      <td className="px-4 py-3 font-mono text-zinc-300">{p.ticker_symbol}</td>
                      <td className="px-4 py-3 text-right font-mono">{formatPrice(p.entry_price)}</td>
                      <td className="px-4 py-3 text-right font-mono">{p.exit_price ? formatPrice(p.exit_price) : "—"}</td>
                      <td className={`px-4 py-3 text-right font-mono ${p.realized_pnl_usd >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {p.realized_pnl_usd >= 0 ? "+" : ""}{formatUsd(p.realized_pnl_usd)}
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{p.catalyst_type}</td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{formatTimestamp(p.opened_at)}</td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{p.closed_at ? formatTimestamp(p.closed_at) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </>
  );
}

function StatCard({ label, value, tone = "default" }: { label: string; value: string; tone?: string }) {
  const color = tone === "good" ? "text-green-400" : tone === "bad" ? "text-red-400" : "text-zinc-100";
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wider">{label}</div>
      <div className={`mt-1 text-2xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  );
}
