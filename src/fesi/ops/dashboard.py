"""Streamlit dashboard — `streamlit run src/fesi/ops/dashboard.py`.

Tabs:
  1. Recent signals  — table, filterable by sector / catalyst / conviction
  2. Shadow portfolio — current positions, P&L, hit rate
  3. Source health   — last fetch time, item count per source
  4. Per-ticker      — search by symbol, see all signals + outcomes
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from fesi.config import load_sectors, load_sources
from fesi.db import connect
from fesi.store.decisions import (
    get_sector_exposure,
    list_recent_decisions,
    total_deployed_capital,
    total_deployed_this_month,
)
from fesi.store.digests import list_recent_digests
from fesi.store.raw_items import (
    count_raw_items_by_source,
    latest_fetch_per_source,
)
from fesi.store.signals import list_signals_for_ticker, list_signals_in_window
from fesi.store.tickers import get_ticker_by_symbol, list_all_tickers


st.set_page_config(page_title="FESI Dashboard", layout="wide", page_icon=None)
st.title("FESI — Finance Early Signals & Investor")
st.caption("Personal catalyst-driven trading signal system · shadow mode")

tab_signals, tab_portfolio, tab_sources, tab_ticker, tab_digests = st.tabs([
    "Recent signals", "Shadow portfolio", "Source health", "Per-ticker", "Digests"
])


# ============================================================================
# Tab 1: Recent signals
# ============================================================================
with tab_signals:
    st.subheader("Recent signals")
    col1, col2, col3 = st.columns(3)
    days = col1.slider("Lookback (days)", 1, 30, 7)
    min_conv = col2.slider("Min conviction", 0.0, 30.0, 0.0, step=0.5)
    sectors_cfg = load_sectors()
    sector_filter = col3.selectbox(
        "Sector", ["(all)"] + list(sectors_cfg.keys())
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    with connect() as conn:
        signals = list_signals_in_window(
            conn,
            since=since,
            min_conviction=min_conv if min_conv > 0 else None,
            sector=sector_filter if sector_filter != "(all)" else None,
        )

    if not signals:
        st.info("No signals in this window. Run `fesi run-pipeline` to fetch some.")
    else:
        df = pd.DataFrame([
            {
                "created_at": s["created_at"][:16],
                "ticker": s.get("ticker_symbol") or "",
                "sector": s["sector"],
                "catalyst": s["catalyst_type"],
                "conviction": float(s["conviction_score"] or 0),
                "impact": s["impact_score"],
                "prob": s["probability_score"],
                "direction": s["direction"],
                "headline": s["headline"][:100],
                "watchlist": "yes" if s.get("feature_is_watchlist") else "",
                "sources": s.get("feature_source_count") or 1,
            }
            for s in signals
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(signals)} signals")


# ============================================================================
# Tab 2: Shadow portfolio
# ============================================================================
with tab_portfolio:
    st.subheader("Shadow portfolio")

    with connect() as conn:
        deployed_total = total_deployed_capital(conn, "shadow")
        deployed_month = total_deployed_this_month(conn, "shadow")
        exposure = get_sector_exposure(conn, "shadow")
        recent_decs = list_recent_decisions(conn, mode="shadow", limit=50)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total deployed (lifetime, shadow)", f"${deployed_total:,.0f}")
    c2.metric("Deployed this month (shadow)", f"${deployed_month:,.0f}")
    c3.metric("Buy decisions logged", len([d for d in recent_decs if d["action"] == "buy"]))

    if exposure:
        st.subheader("Sector exposure")
        exp_df = pd.DataFrame([
            {"sector": k, "deployed_usd": v}
            for k, v in sorted(exposure.items(), key=lambda x: -x[1])
        ])
        st.bar_chart(exp_df.set_index("sector"))

    if recent_decs:
        st.subheader("Recent decisions")
        df = pd.DataFrame([
            {
                "decided_at": d["decided_at"][:16],
                "action": d["action"],
                "ticker": d.get("ticker_symbol") or "",
                "catalyst": d["catalyst_type"],
                "conviction": float(d["conviction_score"] or 0),
                "intended_usd": d.get("intended_position_usd") or 0,
                "rule": d["rule_triggered"] or "",
                "reasoning": (d["reasoning"] or "")[:120],
            }
            for d in recent_decs
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================================
# Tab 3: Source health
# ============================================================================
with tab_sources:
    st.subheader("Source health")
    sources = load_sources()
    with connect() as conn:
        counts = count_raw_items_by_source(conn)
        latest = latest_fetch_per_source(conn)

    rows = []
    for key, cfg in sources.items():
        rows.append({
            "source": key,
            "active": "yes" if cfg.active else "",
            "type": cfg.type,
            "trust": cfg.trust,
            "items_total": counts.get(key, 0),
            "last_fetch": (latest.get(key) or "")[:16],
            "cost_usd_mo": cfg.monthly_usd,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ============================================================================
# Tab 4: Per-ticker page
# ============================================================================
with tab_ticker:
    st.subheader("Per-ticker drill-down")
    with connect() as conn:
        all_tickers = list_all_tickers(conn)
    if not all_tickers:
        st.warning("No tickers loaded. Run `fesi init-db` to load watchlist.")
    else:
        symbols = sorted({t["symbol"] for t in all_tickers})
        symbol = st.selectbox("Symbol", symbols)
        with connect() as conn:
            ticker = get_ticker_by_symbol(conn, symbol)
            if ticker:
                st.markdown(f"**{ticker['symbol']} — {ticker['name']}** ({ticker['exchange']})")
                st.markdown(f"Sector: `{ticker['sector']}`")
                if ticker.get("watchlist_thesis"):
                    st.info(ticker["watchlist_thesis"])
                signals = list_signals_for_ticker(conn, ticker["id"], limit=50)
                if signals:
                    df = pd.DataFrame([
                        {
                            "created_at": s["created_at"][:16],
                            "catalyst": s["catalyst_type"],
                            "conviction": float(s["conviction_score"] or 0),
                            "headline": s["headline"][:100],
                        }
                        for s in signals
                    ])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No signals for this ticker yet.")


# ============================================================================
# Tab 5: Digests
# ============================================================================
with tab_digests:
    st.subheader("Recent digests")
    with connect() as conn:
        digests = list_recent_digests(conn, limit=20)
    if not digests:
        st.info("No digests yet.")
    else:
        df = pd.DataFrame([
            {
                "sent_at": d["sent_at"][:16],
                "window_start": d["scan_window_start"][:16],
                "window_end": d["scan_window_end"][:16],
                "signals": d["signal_count"],
                "decisions": d["decision_count"],
                "via": d["delivered_via"],
            }
            for d in digests
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

        digest_id = st.number_input(
            "Open digest by id", min_value=0, max_value=int(df["sent_at"].count() * 100), step=1
        )
        if digest_id > 0:
            with connect() as conn:
                from fesi.store.digests import get_digest_by_id
                d = get_digest_by_id(conn, digest_id)
            if d:
                st.markdown(d["markdown_body"])
