"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type RunResult = {
  sector: string;
  items_fetched: number;
  items_inserted: number;
  items_skipped: number;
};

export default function RunResearchButton({
  sector,
  label,
}: {
  sector?: string;
  label: string;
}) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function run() {
    setRunning(true);
    setResult(null);
    setError(null);
    try {
      const qs = sector ? `?sector=${encodeURIComponent(sector)}` : "";
      const res = await fetch(`/api/research/run${qs}`, { method: "POST" });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`${res.status}: ${body}`);
      }
      const data = (await res.json()) as RunResult;
      setResult(data);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        onClick={run}
        disabled={running}
        className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {running ? "Searching..." : label}
      </button>
      {error && (
        <span className="text-xs text-red-400">{error}</span>
      )}
      {result && (
        <span className="text-xs text-green-400">
          {result.items_fetched} found, {result.items_inserted} new
        </span>
      )}
    </div>
  );
}
