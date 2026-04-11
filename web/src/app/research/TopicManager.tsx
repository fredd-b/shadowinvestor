"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { ResearchTopic } from "@/lib/types";
import { formatTimestamp } from "@/lib/format";

export default function TopicManager({ topics }: { topics: ResearchTopic[] }) {
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState<number | string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const router = useRouter();

  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading("create");
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      const res = await fetch("/api/research/topics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: (form.get("name") as string).trim(),
          query_template: (form.get("query_template") as string).trim(),
          sector_hint: (form.get("sector_hint") as string).trim() || null,
          schedule: form.get("schedule") as string,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || data.detail || `${res.status}`);
      }
      setShowForm(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleDelete(topicId: number) {
    setLoading(topicId);
    setError(null);
    try {
      const res = await fetch(`/api/research/topics/${topicId}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleRun(topicId: number) {
    setLoading(topicId);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/research/topics/${topicId}/run`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(`${data.items_fetched} found, ${data.items_inserted} new`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Custom Research Topics</h2>
          <p className="text-xs text-zinc-500">{topics.length} of 8 used</p>
        </div>
        {!showForm && topics.length < 8 && (
          <button
            onClick={() => setShowForm(true)}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
          >
            + Add Topic
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-400">{error}</div>
      )}
      {result && (
        <div className="mb-4 rounded border border-green-500/30 bg-green-500/10 p-2 text-xs text-green-400">{result}</div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 rounded-lg border border-zinc-700 bg-zinc-900 p-4 space-y-3">
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Topic Name</label>
            <input name="name" required placeholder="e.g., quantum computing defense"
              className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700 focus:border-blue-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Research Query</label>
            <textarea name="query_template" required rows={3}
              placeholder="e.g., Latest news about quantum computing companies in defense sector, government contracts, breakthroughs"
              className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700 focus:border-blue-500 focus:outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Schedule</label>
              <select name="schedule" className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700">
                <option value="daily">Daily (morning catchup)</option>
                <option value="every_run">Every run (5x/day)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Sector Hint (optional)</label>
              <input name="sector_hint" placeholder="e.g., ai_infrastructure"
                className="w-full rounded bg-zinc-800 px-3 py-2 text-sm text-white border border-zinc-700 focus:border-blue-500 focus:outline-none" />
            </div>
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={loading === "create"}
              className="rounded bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-500 disabled:opacity-50">
              {loading === "create" ? "Creating..." : "Create"}
            </button>
            <button type="button" onClick={() => setShowForm(false)}
              className="text-sm text-zinc-400 hover:text-white">Cancel</button>
          </div>
        </form>
      )}

      {topics.length === 0 ? (
        <p className="text-sm text-zinc-500">No custom topics yet. Add one to start researching your own themes.</p>
      ) : (
        <div className="space-y-2">
          {topics.map((t) => (
            <div key={t.id} className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">{t.name}</span>
                  <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-500">{t.schedule}</span>
                  {!t.is_active && <span className="rounded bg-red-600/20 px-2 py-0.5 text-xs text-red-400">paused</span>}
                </div>
                <p className="mt-1 text-xs text-zinc-500 truncate">{t.query_template}</p>
                <div className="mt-1 flex gap-4 text-xs text-zinc-600">
                  <span>Last: {t.last_run_at ? formatTimestamp(t.last_run_at) : "never"}</span>
                  <span>Total items: {t.total_items_found}</span>
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => handleRun(t.id)}
                  disabled={loading === t.id}
                  className="rounded bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
                >
                  {loading === t.id ? "..." : "Run"}
                </button>
                <button
                  onClick={() => handleDelete(t.id)}
                  disabled={loading === t.id}
                  className="rounded bg-zinc-700 px-3 py-1 text-xs text-zinc-400 hover:bg-zinc-600 hover:text-white disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
