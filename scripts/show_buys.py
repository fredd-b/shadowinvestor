"""One-off: print shadow BUY decisions in detail."""
from fesi.db import connect
from fesi.store.decisions import list_recent_decisions

with connect() as conn:
    buys = list_recent_decisions(conn, mode="shadow", action="buy")

print(f"BUY DECISIONS: {len(buys)}")
print("=" * 100)
for d in buys:
    ticker = d.get("ticker_symbol") or "?"
    usd = d.get("intended_position_usd") or 0
    cat = d.get("catalyst_type") or ""
    conv = d.get("conviction_score") or 0
    when = d["decided_at"][:16]
    print(f"{when} | {ticker:<10s} | conv {conv:5.1f} | ${usd:6.0f} | {cat}")
    print(f"    headline: {d['headline']}")
    print(f"    reasoning: {d['reasoning']}")
    print()
