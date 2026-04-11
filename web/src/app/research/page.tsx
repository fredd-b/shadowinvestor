import { getResearchStatus, getResearchTopics, getTickers } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import Nav from "@/components/Nav";
import RunResearchButton from "./RunResearchButton";
import TopicManager from "./TopicManager";

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
  const [sectors, topics, tickers] = await Promise.all([
    getResearchStatus().catch(() => []),
    getResearchTopics().catch(() => []),
    getTickers(true).catch(() => []),
  ]);
  const schedule = sectors[0]?.schedule ?? [];
  const dailyResearchTickers = tickers.filter(
    (t) => t.lifecycle_status === "invested" || t.lifecycle_status === "considering"
  );

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Research</h1>
            <p className="text-sm text-zinc-400">
              Automated discovery across sectors, custom topics, and per-ticker monitoring.
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
        <h2 className="mb-3 text-lg font-semibold">Sector Research (6 sectors × 5 runs/day)</h2>
        <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
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
                </div>
              </div>
              <RunResearchButton
                sector={s.sector_key}
                label={`Search ${s.display_name.split("—")[0].trim()}`}
              />
            </div>
          ))}
        </div>

        {/* Custom Topics */}
        <div className="mb-8">
          <TopicManager topics={topics} />
        </div>

        {/* Per-Ticker Daily Research */}
        <div className="mb-8">
          <h2 className="mb-3 text-lg font-semibold">Per-Ticker Daily Research</h2>
          <p className="mb-3 text-xs text-zinc-500">
            Tickers marked &quot;invested&quot; or &quot;considering&quot; get a dedicated Perplexity query at 08:00 Dubai (morning catchup).
          </p>
          {dailyResearchTickers.length === 0 ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-sm text-zinc-500">
              No tickers with &quot;invested&quot; or &quot;considering&quot; status. Change a ticker&apos;s status from the Tickers page to enable daily research.
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-zinc-800">
              <table className="w-full text-sm">
                <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
                  <tr>
                    <th className="px-4 py-3">Ticker</th>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Sector</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyResearchTickers.map((t) => (
                    <tr key={t.id} className="border-t border-zinc-800">
                      <td className="px-4 py-3 font-mono text-yellow-400">{t.symbol}</td>
                      <td className="px-4 py-3 text-zinc-300">{t.name}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${
                          t.lifecycle_status === "invested"
                            ? "bg-green-600/20 text-green-400"
                            : "bg-yellow-600/20 text-yellow-400"
                        }`}>
                          {t.lifecycle_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{t.sector}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* How it works */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 text-sm text-zinc-400">
          <h2 className="mb-2 font-semibold text-zinc-300">How it works</h2>
          <ul className="space-y-1 list-disc list-inside">
            <li><strong>Sector research:</strong> 6 queries per run, searches for catalyst events per sector</li>
            <li><strong>Custom topics:</strong> Your own research queries, run daily or 5x/day</li>
            <li><strong>Per-ticker:</strong> Dedicated query for each invested/considering ticker at morning catchup</li>
            <li>All results flow through classify → score → decide pipeline</li>
            <li>Cost: ~$1-3.50/month total depending on custom topics</li>
          </ul>
        </div>
      </main>
    </>
  );
}
