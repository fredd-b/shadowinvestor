"""Digest renderer — produces the markdown digest matching Fred's prompt format.

Sections:
  - Top 10 High-Conviction Catalysts (ranked by conviction_score)
  - Emerging / Rumor-Type Signals (lower conviction, tagged)
  - Watchlist Updates (ticker_is_watchlist == 1)
  - Follow-Up Watchlist (signals with future event dates / pending catalysts)
  - Shadow Portfolio Summary (P&L from accumulated decisions)

The output is markdown so it works equally well in Telegram, email, push
notification, or the local Streamlit dashboard.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fesi.config import load_catalysts, load_sectors
from fesi.store.decisions import (
    get_sector_exposure,
    list_recent_decisions,
    total_deployed_this_month,
)


def render_digest(
    conn: sqlite3.Connection,
    *,
    signals: list[dict],
    window_start: datetime,
    window_end: datetime,
) -> str:
    """Render a digest markdown body for the given window of signals."""
    catalysts = load_catalysts()
    sectors = load_sectors()

    parts: list[str] = []

    # Header
    parts.append(
        f"# FESI Digest — {window_start.strftime('%Y-%m-%d %H:%M')} → "
        f"{window_end.strftime('%H:%M')} UTC"
    )
    parts.append(
        f"_Window: {(window_end - window_start).total_seconds() / 3600:.0f}h · "
        f"signals: {len(signals)}_"
    )
    parts.append("")

    # Split signals into buckets
    high = sorted(
        [s for s in signals if (s["conviction_score"] or 0) >= 12.0],
        key=lambda s: -float(s["conviction_score"] or 0),
    )[:10]
    emerging = sorted(
        [s for s in signals if 6.0 <= (s["conviction_score"] or 0) < 12.0],
        key=lambda s: -float(s["conviction_score"] or 0),
    )[:10]
    watchlist_hits = [s for s in signals if (s["feature_is_watchlist"] or 0) == 1]
    follow_up = [
        s for s in signals
        if s.get("timeframe_bucket") in ("3-12m", "1-3y")
        and (s["conviction_score"] or 0) >= 6.0
    ][:10]

    # ---- Section 1: Top 10 ----
    parts.append("## Top 10 High-Conviction Catalysts")
    parts.append("")
    if not high:
        parts.append("_No signals at conviction ≥ 12.0 in this window._")
    else:
        parts.append(
            "| # | Ticker | Sector | Catalyst | Conviction | Direction | Timeframe |"
        )
        parts.append("|---|---|---|---|---:|---|---|")
        for i, s in enumerate(high, 1):
            ticker = s.get("ticker_symbol") or "?"
            sec = sectors.get(s["sector"]).display_name if s["sector"] in sectors else s["sector"]
            cat = catalysts.get(s["catalyst_type"]).display_name if s["catalyst_type"] in catalysts else s["catalyst_type"]
            parts.append(
                f"| {i} | **{ticker}** | {sec} | {cat} | "
                f"**{float(s['conviction_score'] or 0):.1f}** | "
                f"{s['direction']} | {s['timeframe_bucket']} |"
            )
        parts.append("")
        parts.append("### Detail")
        for i, s in enumerate(high, 1):
            ticker = s.get("ticker_symbol") or "?"
            parts.append(f"**{i}. {ticker} — {s['headline']}**")
            parts.append("")
            parts.append(f"_{s['summary']}_")
            if s.get("economics_summary"):
                parts.append("")
                parts.append(f"**Economics:** {s['economics_summary']}")
            parts.append("")
            parts.append(
                f"Impact {s['impact_score']}/5 · "
                f"Probability {s['probability_score']}/5 · "
                f"Sources {s['feature_source_count']} ({s['feature_source_diversity']} distinct)"
            )
            parts.append("")
            parts.append("---")
            parts.append("")

    # ---- Section 2: Emerging ----
    parts.append("## Emerging / Lower-Confidence Signals")
    parts.append("")
    if not emerging:
        parts.append("_None in this window._")
    else:
        for s in emerging:
            ticker = s.get("ticker_symbol") or "?"
            parts.append(
                f"- **[low-confidence]** {ticker} — {s['headline']} "
                f"(conviction {float(s['conviction_score'] or 0):.1f}, "
                f"{s['catalyst_type']})"
            )
    parts.append("")

    # ---- Section 3: Watchlist updates ----
    parts.append("## Watchlist Updates")
    parts.append("")
    if not watchlist_hits:
        parts.append("_No fresh news on watchlist names in this window._")
    else:
        for s in watchlist_hits:
            ticker = s.get("ticker_symbol") or "?"
            parts.append(
                f"- **{ticker}** ({s['catalyst_type']}, "
                f"conviction {float(s['conviction_score'] or 0):.1f}): {s['headline']}"
            )
    parts.append("")

    # ---- Section 4: Follow-up ----
    parts.append("## Follow-Up Watchlist (Future Catalysts)")
    parts.append("")
    if not follow_up:
        parts.append("_None._")
    else:
        for s in follow_up:
            ticker = s.get("ticker_symbol") or "?"
            parts.append(
                f"- **{ticker}** — {s['headline']} "
                f"(timeframe {s['timeframe_bucket']})"
            )
    parts.append("")

    # ---- Section 5: Shadow Portfolio Summary ----
    parts.append("## Shadow Portfolio Summary")
    parts.append("")
    deployed = total_deployed_this_month(conn, "shadow")
    exposure = get_sector_exposure(conn, "shadow")
    recent_decisions = list_recent_decisions(conn, mode="shadow", limit=5)

    parts.append(f"- Deployed (this month, shadow): **${deployed:,.0f}**")
    if exposure:
        parts.append("- Sector exposure (shadow):")
        for sec_name, amount in sorted(exposure.items(), key=lambda x: -x[1]):
            parts.append(f"  - {sec_name}: ${amount:,.0f}")
    if recent_decisions:
        parts.append("- Recent shadow decisions:")
        for d in recent_decisions:
            parts.append(
                f"  - {d['decided_at'][:16]} · {d['action']} · "
                f"{d.get('ticker_symbol') or '?'} · "
                f"conviction {float(d.get('conviction_score') or 0):.1f}"
            )

    parts.append("")
    parts.append("---")
    parts.append("_Generated by FESI in shadow mode. No real trades executed._")

    return "\n".join(parts)
