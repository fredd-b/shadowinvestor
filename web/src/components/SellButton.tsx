"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SellButton({
  positionId,
  sharesRemaining,
  ticker,
}: {
  positionId: number;
  sharesRemaining: number;
  ticker: string;
}) {
  const [mode, setMode] = useState<"idle" | "confirm" | "partial">("idle");
  const [shares, setShares] = useState(sharesRemaining);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const router = useRouter();

  async function executeSell(qty: number | undefined) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/positions/${positionId}/sell`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shares: qty }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(`Sold ${data.shares_sold} shares at $${data.exit_price?.toFixed(2)} — P&L: $${data.realized_pnl?.toFixed(2)}`);
      setMode("idle");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return <span className="text-xs text-green-400">{result}</span>;
  }

  if (mode === "idle") {
    return (
      <div className="flex gap-2">
        <button
          onClick={() => setMode("confirm")}
          className="rounded bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-500"
        >
          Sell All
        </button>
        {sharesRemaining > 1 && (
          <button
            onClick={() => setMode("partial")}
            className="rounded bg-orange-600 px-3 py-1 text-xs font-semibold text-white hover:bg-orange-500"
          >
            Sell Partial
          </button>
        )}
      </div>
    );
  }

  if (mode === "confirm") {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-400">Sell all {sharesRemaining} shares of {ticker}?</span>
        <button
          onClick={() => executeSell(undefined)}
          disabled={loading}
          className="rounded bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-500 disabled:opacity-50"
        >
          {loading ? "Selling..." : "Confirm"}
        </button>
        <button onClick={() => setMode("idle")} className="text-xs text-zinc-500 hover:text-white">Cancel</button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    );
  }

  // partial mode
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        min={1}
        max={sharesRemaining}
        value={shares}
        onChange={(e) => setShares(parseInt(e.target.value, 10) || 1)}
        className="w-20 rounded bg-zinc-800 px-2 py-1 text-xs text-white border border-zinc-700"
      />
      <span className="text-xs text-zinc-500">of {sharesRemaining}</span>
      <button
        onClick={() => executeSell(shares)}
        disabled={loading}
        className="rounded bg-orange-600 px-3 py-1 text-xs font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
      >
        {loading ? "Selling..." : "Sell"}
      </button>
      <button onClick={() => setMode("idle")} className="text-xs text-zinc-500 hover:text-white">Cancel</button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}
