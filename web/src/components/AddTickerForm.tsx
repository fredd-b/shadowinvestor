"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const SECTORS = [
  { key: "biotech_pharma", label: "Biotech & Pharma" },
  { key: "china_biotech_us_pipeline", label: "China Biotech" },
  { key: "ai_infrastructure", label: "AI Infrastructure" },
  { key: "crypto_to_ai_pivot", label: "Crypto / AI Pivot" },
  { key: "commodities_critical_minerals", label: "Commodities" },
  { key: "binary_event_other", label: "Other Binary" },
];

const EXCHANGES = ["NASDAQ", "NYSE", "AMEX", "HKEX", "TSX", "ASX", "LSE"];

export default function AddTickerForm() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    const form = new FormData(e.currentTarget);
    const body = {
      symbol: (form.get("symbol") as string).toUpperCase().trim(),
      exchange: form.get("exchange") as string,
      name: (form.get("name") as string).trim(),
      sector: form.get("sector") as string,
      thesis: (form.get("thesis") as string).trim(),
    };

    try {
      const res = await fetch("/api/tickers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || data.detail || `${res.status}`);
      }
      setSuccess(`Added ${body.symbol}`);
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <div className="flex items-center gap-3">
        <button
          onClick={() => setOpen(true)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
        >
          + Add Ticker
        </button>
        {success && <span className="text-xs text-green-400">{success}</span>}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Symbol</label>
          <input name="symbol" required placeholder="AAPL"
            className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700 focus:border-blue-500 focus:outline-none" />
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Exchange</label>
          <select name="exchange" required
            className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700">
            {EXCHANGES.map((ex) => <option key={ex} value={ex}>{ex}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Sector</label>
          <select name="sector" required
            className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700">
            {SECTORS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="block text-xs text-zinc-500 mb-1">Company Name</label>
        <input name="name" required placeholder="Apple Inc."
          className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700 focus:border-blue-500 focus:outline-none" />
      </div>
      <div>
        <label className="block text-xs text-zinc-500 mb-1">Investment Thesis</label>
        <textarea name="thesis" required rows={2} placeholder="Why are you watching this stock?"
          className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700 focus:border-blue-500 focus:outline-none" />
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={loading}
          className="rounded bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-500 disabled:opacity-50">
          {loading ? "Adding..." : "Add to Watchlist"}
        </button>
        <button type="button" onClick={() => setOpen(false)}
          className="rounded px-4 py-2 text-sm text-zinc-400 hover:text-white">
          Cancel
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </form>
  );
}
