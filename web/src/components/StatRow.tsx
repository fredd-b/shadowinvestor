// Shared "label : value" row used in admin dashboards and signal detail pages.
// Two layouts:
//   <StatRow> — flex justify-between (used inside cards / dl lists)
//   <StatTile> — stacked tile with uppercase label above mono value

type Tone = "default" | "good" | "warn" | "bad";

const TONE_CLASS: Record<Tone, string> = {
  default: "text-zinc-100",
  good: "text-green-400",
  warn: "text-yellow-400",
  bad: "text-red-400",
};

export function StatRow({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  tone?: Tone;
}) {
  return (
    <div className="flex justify-between">
      <dt className="text-zinc-500">{label}</dt>
      <dd className={`font-mono ${TONE_CLASS[tone]}`}>{value}</dd>
    </div>
  );
}

export function StatTile({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="text-xs uppercase text-zinc-500">{label}</div>
      <div className="mt-1 font-mono text-sm text-zinc-100">{value}</div>
    </div>
  );
}
