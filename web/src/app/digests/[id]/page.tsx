import { getDigest } from "@/lib/api";
import Nav from "@/components/Nav";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function DigestPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const digestId = parseInt(id, 10);
  if (Number.isNaN(digestId)) notFound();

  let digest;
  try {
    digest = await getDigest(digestId);
  } catch {
    notFound();
  }

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <Link href="/digests" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Digests
        </Link>
        <div className="mt-2 mb-6">
          <h1 className="text-3xl font-bold">Digest #{digest.id}</h1>
          <p className="text-sm text-zinc-400">
            {digest.sent_at.slice(0, 16).replace("T", " ")} · {digest.signal_count}{" "}
            signals · {digest.decision_count} decisions
          </p>
        </div>
        <pre className="overflow-auto whitespace-pre-wrap rounded-lg border border-zinc-800 bg-zinc-900 p-6 font-mono text-sm leading-relaxed text-zinc-200">
          {digest.markdown_body}
        </pre>
      </main>
    </>
  );
}
