import { getDigests } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import Nav from "@/components/Nav";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function DigestsPage() {
  const digests = await getDigests(50).catch(() => []);

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="mb-6 text-3xl font-bold">Digests</h1>
        {digests.length === 0 ? (
          <p className="text-zinc-500">No digests yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-900 text-left text-xs uppercase text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Sent at</th>
                  <th className="px-4 py-3">Window</th>
                  <th className="px-4 py-3 text-right">Signals</th>
                  <th className="px-4 py-3 text-right">Decisions</th>
                  <th className="px-4 py-3">Delivered via</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {digests.map((d) => (
                  <tr key={d.id} className="border-t border-zinc-800">
                    <td className="px-4 py-3 text-zinc-300">
                      {formatTimestamp(d.sent_at)}
                    </td>
                    <td className="px-4 py-3 text-zinc-500">
                      {formatTimestamp(d.scan_window_start)} →{" "}
                      {d.scan_window_end.slice(11, 16)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {d.signal_count}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {d.decision_count}
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">
                      {d.delivered_via}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/digests/${d.id}`}
                        className="text-zinc-300 hover:text-zinc-100"
                      >
                        view →
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
