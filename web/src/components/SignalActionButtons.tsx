"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const ACTIONS = [
  { key: "invest", label: "Invest", color: "bg-green-600 hover:bg-green-500", icon: "$" },
  { key: "skip", label: "Skip", color: "bg-zinc-700 hover:bg-zinc-600", icon: "x" },
  { key: "watch_pullback", label: "Watch", color: "bg-yellow-600 hover:bg-yellow-500", icon: "~" },
] as const;

export default function SignalActionButtons({
  signalId,
  currentAction,
}: {
  signalId: number;
  currentAction: string | null;
}) {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleAction(action: string) {
    setLoading(action);
    setError(null);
    try {
      const res = await fetch(`/api/signals/${signalId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!res.ok) throw new Error(await res.text());
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {ACTIONS.map((a) => {
        const isActive = currentAction === a.key;
        return (
          <button
            key={a.key}
            onClick={() => handleAction(a.key)}
            disabled={loading !== null}
            className={`rounded px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 ${
              isActive ? "ring-2 ring-white " + a.color : a.color
            }`}
          >
            {loading === a.key ? "..." : `${a.icon} ${a.label}`}
          </button>
        );
      })}
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}
