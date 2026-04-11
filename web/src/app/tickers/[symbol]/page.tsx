import { getTicker, getTickerSignals, getTickerIndicators } from "@/lib/api";
import { formatTimestamp, formatPrice } from "@/lib/format";
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

  const [signals, indicators] = await Promise.all([
    getTickerSignals(decoded, 100).catch(() => []),
    getTickerIndicators(decoded).catch(() => null),
  ]);

  const latest = indicators?.latest;

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Link href="/tickers" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Watchlist
        </Link>
        <div className="mt-2 mb-6">
          <div className="flex items-baseline gap-3">
            <h1 className="font-mono text-3xl font-bold text-yellow-400">
              {ticker.symbol}
            </h1>
            <span className="text-base text-zinc-500">{ticker.exchange}</span>
            <span className={`ml-auto rounded px-2 py-0.5 text-xs font-semibold ${
              ticker.lifecycle_status === "invested" ? "bg-green-600/20 text-green-400"
              : ticker.lifecycle_status === "considering" ? "bg-yellow-600/20 text-yellow-400"
              : "bg-zinc-700/50 text-zinc-400"
            }`}>
              {ticker.lifecycle_status}
            </span>
          </div>
          <p className="mt-1 text-xl text-zinc-200">{ticker.name}</p>
          <p className="mt-1 text-sm text-zinc-500">{ticker.sector}</p>
          {ticker.watchlist_thesis && (
            <div className="mt-4 rounded border-l-2 border-yellow-500/50 bg-yellow-500/5 p-3 text-sm text-zinc-300">
              {ticker.watchlist_thesis}
            </div>
          )}
        </div>

        {/* Technical Indicators */}
        {latest && (
          <div className="mb-6 rounded-lg border border-zinc-800 bg-zinc-900 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
              Technical Indicators
            </h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
              <TACell label="Price" value={formatPrice(latest.close)} />
              <TACell
                label="RSI (14)"
                value={latest.rsi_14?.toFixed(1) ?? "—"}
                tone={latest.rsi_14 != null ? (latest.rsi_14 > 70 ? "bad" : latest.rsi_14 < 30 ? "good" : "default") : "default"}
                note={latest.rsi_14 != null ? (latest.rsi_14 > 70 ? "OVERBOUGHT" : latest.rsi_14 < 30 ? "OVERSOLD" : "") : ""}
              />
              <SMACell label="SMA 20" value={latest.sma_20} close={latest.close} />
              <SMACell label="SMA 50" value={latest.sma_50} close={latest.close} />
              <SMACell label="SMA 200" value={latest.sma_200} close={latest.close} />
              {latest.trend && (
                <TACell
                  label="Trend"
                  value={latest.trend.toUpperCase()}
                  tone={latest.trend === "bullish" ? "good" : latest.trend === "bearish" ? "bad" : "default"}
                />
              )}
            </div>
            {indicators?.price_vs_entry_pct != null && (
              <div className="mt-3 text-sm">
                <span className="text-zinc-500">vs Entry: </span>
                <span className={`font-mono font-semibold ${
                  indicators.price_vs_entry_pct >= 0 ? "text-green-400" : "text-red-400"
                }`}>
                  {indicators.price_vs_entry_pct >= 0 ? "+" : ""}{indicators.price_vs_entry_pct.toFixed(1)}%
                </span>
                <span className="text-zinc-600 ml-2">
                  (entry {formatPrice(indicators.entry_price ?? 0)})
                </span>
              </div>
            )}
          </div>
        )}

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
                  <tr key={s.id} className="border-t border-zinc-800 hover:bg-zinc-900/50">
                    <td className="px-4 py-3 text-zinc-500">
                      {formatTimestamp(s.created_at)}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{s.catalyst_type}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      {s.conviction_score.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-zinc-300">
                      <Link href={`/signals/${s.id}`} className="hover:text-zinc-100 hover:underline">
                        {s.headline}
                      </Link>
                    </td>
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

function TACell({
  label, value, tone = "default", note = "",
}: {
  label: string; value: string; tone?: string; note?: string;
}) {
  const color = tone === "good" ? "text-green-400" : tone === "bad" ? "text-red-400" : "text-zinc-100";
  return (
    <div>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className={`font-mono text-sm font-semibold ${color}`}>{value}</div>
      {note && <div className={`text-xs ${color}`}>{note}</div>}
    </div>
  );
}

function SMACell({ label, value, close }: { label: string; value: number | null; close: number }) {
  if (value == null) return <TACell label={label} value="—" />;
  const above = close > value;
  return (
    <div>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className={`font-mono text-sm font-semibold ${above ? "text-green-400" : "text-red-400"}`}>
        {formatPrice(value)} {above ? "▲" : "▼"}
      </div>
    </div>
  );
}
