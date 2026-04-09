import Link from "next/link";

const NAV_ITEMS = [
  { href: "/", label: "Signals" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/tickers", label: "Tickers" },
  { href: "/sources", label: "Sources" },
  { href: "/digests", label: "Digests" },
];

export default function Nav() {
  return (
    <nav className="border-b border-zinc-800 bg-zinc-950">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-bold text-zinc-100">
          ShadowInvestor
        </Link>
        <div className="flex gap-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
