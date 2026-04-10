import { getSourcesHealth } from "@/lib/api";
import { formatTimestamp, formatCount } from "@/lib/format";
import Nav from "@/components/Nav";

export const dynamic = "force-dynamic";

export default async function SourcesPage() {
  const sources = await getSourcesHealth().catch(() => []);
  const active = sources.filter((s) => s.active);
  const inactive = sources.filter((s) => !s.active);

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="mb-2 text-3xl font-bold">Source Health</h1>
        <p className="mb-6 text-sm text-zinc-400">
          {active.length} active · {inactive.length} inactive · total items:{" "}
          {formatCount(sources.reduce((s, x) => s + x.items_total, 0))}
        </p>

        <h2 className="mb-3 text-xl font-semibold">Active</h2>
        <div className="mb-8 overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 text-right">Trust</th>
                <th className="px-4 py-3 text-right">Items</th>
                <th className="px-4 py-3">Last fetch</th>
                <th className="px-4 py-3 text-right">Cost/mo</th>
              </tr>
            </thead>
            <tbody>
              {active.map((s) => (
                <tr key={s.key} className="border-t border-zinc-800">
                  <td className="px-4 py-3">
                    <div className="font-medium text-zinc-100">{s.display_name}</div>
                    <div className="text-xs text-zinc-500">{s.key}</div>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{s.type}</td>
                  <td className="px-4 py-3 text-right font-mono">{s.trust}/5</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {formatCount(s.items_total)}
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    {s.last_fetch ? formatTimestamp(s.last_fetch) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {s.monthly_usd > 0 ? `$${s.monthly_usd}` : "free"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h2 className="mb-3 text-xl font-semibold text-zinc-500">Inactive</h2>
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 text-right">Trust</th>
                <th className="px-4 py-3 text-right">Cost/mo</th>
              </tr>
            </thead>
            <tbody>
              {inactive.map((s) => (
                <tr key={s.key} className="border-t border-zinc-800 text-zinc-500">
                  <td className="px-4 py-3">{s.display_name}</td>
                  <td className="px-4 py-3">{s.type}</td>
                  <td className="px-4 py-3 text-right font-mono">{s.trust}/5</td>
                  <td className="px-4 py-3 text-right">
                    {s.monthly_usd > 0 ? `$${s.monthly_usd}` : "free"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}
