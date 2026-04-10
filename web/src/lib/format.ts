// Shared display formatters used by every page.

/** "2026-04-09T20:17:35..." → "04-09 20:17" */
export function formatTimestamp(iso: string): string {
  return iso.slice(5, 16).replace("T", " ");
}

/** Number → "$1,234" with no decimals */
export function formatUsd(n: number | null | undefined, fallback = "—"): string {
  if (n === null || n === undefined) return fallback;
  return `$${Math.round(n).toLocaleString()}`;
}

/** Number → "1,234" */
export function formatCount(n: number | null | undefined, fallback = "—"): string {
  if (n === null || n === undefined) return fallback;
  return n.toLocaleString();
}

/** Number → "$1,234.56" with 2 decimals */
export function formatPrice(n: number | null | undefined, fallback = "—"): string {
  if (n === null || n === undefined) return fallback;
  return `$${n.toFixed(2)}`;
}
