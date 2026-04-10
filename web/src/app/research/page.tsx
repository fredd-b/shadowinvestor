import { getResearchStatus } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import Nav from "@/components/Nav";
import RunResearchButton from "./RunResearchButton";

export const dynamic = "force-dynamic";

const SECTOR_ICONS: Record<string, string> = {
  biotech_pharma: "DNA",
  china_biotech_us_pipeline: "CN",
  ai_infrastructure: "AI",
  crypto_to_ai_pivot: "GPU",
  commodities_critical_minerals: "Au",
  binary_event_other: "Ev",
};

export default async function ResearchPage() {
  const sectors = await getResearchStatus().catch(() => []);
  const schedule = sectors[0]?.schedule ?? [];

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Research</h1>
            <p className="text-sm text-zinc-400">
              Perplexity web search across 6 sectors. Run individually or all at once.
            </p>
          </div>
          <RunResearchButton label="Run All Sectors" />
        </div>

        {/* Schedule */}
        <div className="mb-8 rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <h2 className="mb-2 text-sm font-semibold text-zinc-400 uppercase tracking-wider">
            Automatic Schedule (Dubai time)
          </h2>
          <div className="flex flex-wrap gap-3">
            {schedule.map((s) => (
              <span
                key={s.label}
                className="rounded bg-zinc-800 px-3 py-1 text-sm font-mono"
              >
                {s.time} <span className="text-zinc-500">{s.label}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Sector cards */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sectors.map((s) => (
            <div
              key={s.sector_key}
              className="flex flex-col justify-between rounded-lg border border-zinc-800 bg-zinc-900 p-5"
            >
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded bg-zinc-800 text-xs font-bold text-blue-400">
                    {SECTOR_ICONS[s.sector_key] ?? "?"}
                  </span>
                  <h3 className="font-semibold">{s.display_name}</h3>
                </div>
                <p className="mb-3 text-xs text-zinc-400 leading-relaxed">
                  {s.description}
                </p>
                <div className="mb-4 space-y-1 text-xs">
                  <div className="flex justify-between text-zinc-500">
                    <span>Last run</span>
                    <span className={s.last_run_at ? "text-zinc-300" : "text-zinc-600"}>
                      {s.last_run_at ? formatTimestamp(s.last_run_at) : "never"}
                    </span>
                  </div>
                  <div className="flex justify-between text-zinc-500">
                    <span>Items found</span>
                    <span className="text-zinc-300 font-mono">
                      {s.items_found_last_run}
                    </span>
                  </div>
                  <div className="flex justify-between text-zinc-500">
                    <span>Status</span>
                    <span className={s.enabled ? "text-green-400" : "text-red-400"}>
                      {s.enabled ? "active" : "no API key"}
                    </span>
                  </div>
                </div>
              </div>
              <RunResearchButton
                sector={s.sector_key}
                label={`Search ${s.display_name.split("—")[0].trim()}`}
              />
            </div>
          ))}
        </div>

        {/* How it works */}
        <div className="mt-8 rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 text-sm text-zinc-400">
          <h2 className="mb-2 font-semibold text-zinc-300">How it works</h2>
          <ul className="space-y-1 list-disc list-inside">
            <li>Each sector sends a targeted web search query to Perplexity (sonar model)</li>
            <li>The query includes your watchlist tickers + relevant catalyst types for that sector</li>
            <li>Perplexity searches the web and returns structured events with source URLs</li>
            <li>Events are deduped against existing items, then flow through classify → score → decide</li>
            <li>Cost: ~$0.005 per query (~$0.03/day for all 6 sectors × 5 daily runs)</li>
          </ul>
        </div>
      </main>
    </>
  );
}
