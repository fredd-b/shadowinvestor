"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type PipelineStats = {
  raw_items_fetched: number;
  raw_items_inserted: number;
  candidates: number;
  signals_created: number;
  decisions_buy: number;
  decisions_no_buy: number;
  errors: string[];
};

export default function RunPipelineButton() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PipelineStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function run() {
    setRunning(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch("/api/admin/run-pipeline", { method: "POST" });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`${res.status}: ${body}`);
      }
      const data = (await res.json()) as PipelineStats;
      setResult(data);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <button
        onClick={run}
        disabled={running}
        className="rounded bg-yellow-500 px-6 py-3 font-bold text-zinc-950 hover:bg-yellow-400 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {running ? "Running pipeline... (30-90s)" : "▶ Run pipeline now"}
      </button>

      {error && (
        <div className="mt-4 rounded border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-300">
          <strong>Failed:</strong> {error}
        </div>
      )}

      {result && (
        <div className="mt-4 rounded border border-green-500/30 bg-green-500/5 p-4 text-sm">
          <div className="mb-2 font-semibold text-green-400">
            ✓ Pipeline completed
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-zinc-300">
            <dt className="text-zinc-500">Raw items fetched</dt>
            <dd className="font-mono">{result.raw_items_fetched}</dd>
            <dt className="text-zinc-500">New items inserted</dt>
            <dd className="font-mono">{result.raw_items_inserted}</dd>
            <dt className="text-zinc-500">Candidates after dedupe</dt>
            <dd className="font-mono">{result.candidates}</dd>
            <dt className="text-zinc-500">Signals created</dt>
            <dd className="font-mono">{result.signals_created}</dd>
            <dt className="text-zinc-500 text-yellow-400">Buy decisions</dt>
            <dd className="font-mono text-yellow-300">{result.decisions_buy}</dd>
            <dt className="text-zinc-500">No-buy decisions</dt>
            <dd className="font-mono">{result.decisions_no_buy}</dd>
            {result.errors.length > 0 && (
              <>
                <dt className="text-zinc-500 text-red-400">Errors</dt>
                <dd className="font-mono text-red-300">
                  {result.errors.length}
                </dd>
              </>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}
