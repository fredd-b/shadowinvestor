"""End-to-end pipeline test with synthetic raw_items (no network).

This is the most important test in Phase 1 — it proves the entire signal
pipeline runs cleanly from raw_items → signals → decisions → digest, using
the deterministic fallback classifier (no API key needed).
"""
from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text


def test_e2e_pipeline_with_synthetic_items(tmp_db, monkeypatch):
    """Insert raw_items, run the pipeline manually, assert signals + decisions exist."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import fesi.config
    importlib.reload(fesi.config)

    from fesi.db import connect
    from fesi.intelligence.classifier import classify
    from fesi.intelligence.cross_ref import compute_conviction
    from fesi.intelligence.normalize import normalize
    from fesi.intelligence.scorer import score
    from fesi.config import load_catalysts
    from fesi.store.raw_items import get_unprocessed_raw_items
    from fesi.store.signals import insert_signal, list_signals_in_window
    from fesi.store.tickers import get_ticker_by_symbol
    from fesi.store.outcomes import upsert_outcome_stub
    from fesi.decision.engine import make_decision
    from fesi.store.prices import insert_price_bar
    from fesi.digest.render import render_digest

    # ---- Seed: insert price + synthetic raw_items ----
    with connect() as conn:
        onc = get_ticker_by_symbol(conn, "ONC")
        insert_price_bar(
            conn,
            ticker_id=onc["id"],
            date="2026-04-08",
            open_=195.0, high=205.0, low=193.0, close=200.0,
            volume=1_000_000,
            source="test",
        )

        now = datetime.now(timezone.utc)
        for i, (title, source) in enumerate([
            ("FDA approves BeiGene's Brukinsa for new lymphoma indication", "pr_newswire"),
            ("FDA approves BeiGene's Brukinsa for new lymphoma indication.", "businesswire"),
            ("NexGen Energy achieves first production at Rook I uranium mine", "globenewswire"),
            ("Cipher Mining wins long-term AI/HPC hosting contract with named customer", "pr_newswire"),
        ]):
            conn.execute(
                text("""
                    INSERT INTO raw_items (
                        source, source_id, fetched_at, published_at,
                        url, title, raw_payload, content_hash
                    )
                    VALUES (
                        :source, :sid, :fetched, :pub, :url, :title, :payload, :hash
                    )
                """),
                {
                    "source": source,
                    "sid": f"e2e-{i}",
                    "fetched": now.isoformat(),
                    "pub": now.isoformat(),
                    "url": f"https://example.com/{i}",
                    "title": title,
                    "payload": json.dumps({"description": title, "title": title}),
                    "hash": f"e2e-hash-{i}",
                },
            )

    # ---- Run normalize + classify + score + insert signals ----
    catalysts = load_catalysts()
    with connect() as conn:
        unprocessed = get_unprocessed_raw_items(
            conn, since=datetime.now(timezone.utc) - timedelta(hours=72)
        )
        assert len(unprocessed) == 4

        candidates = normalize(unprocessed)
        # Two BeiGene items should merge → 3 candidates
        assert len(candidates) == 3

        for cand in candidates:
            cls = classify(cand.primary_title, cand.primary_body, cand.sources[0])
            cat = catalysts.get(cls.catalyst_type)
            assert cat is not None
            sc = score(cand.primary_title, cand.primary_body, cls, cat)
            conviction = compute_conviction(
                sc.impact_score, sc.probability_score,
                cand.source_count, cand.source_diversity, cand.sources,
            )
            ticker = None
            if cls.primary_ticker_symbol:
                ticker = get_ticker_by_symbol(conn, cls.primary_ticker_symbol)

            sid = insert_signal(
                conn,
                event_at=cand.earliest_published or datetime.now(timezone.utc),
                primary_ticker_id=ticker["id"] if ticker else None,
                catalyst_type=cls.catalyst_type,
                sector=cls.sector,
                headline=cls.headline,
                summary=cls.summary,
                economics_summary=cls.economics_summary,
                impact_score=sc.impact_score,
                probability_score=sc.probability_score,
                conviction_score=conviction,
                timeframe_bucket=cls.timeframe_bucket,
                direction=cls.direction,
                feature_source_count=cand.source_count,
                feature_source_diversity=cand.source_diversity,
                feature_is_watchlist=int(ticker.get("is_watchlist", 0)) if ticker else 0,
                raw_item_ids=cand.raw_item_ids,
                source_urls=cand.urls,
            )
            upsert_outcome_stub(conn, sid)

    # ---- Verify signals exist ----
    with connect() as conn:
        signals = list_signals_in_window(
            conn, since=datetime.now(timezone.utc) - timedelta(hours=72)
        )
    assert len(signals) == 3

    # The merged signal should have feature_source_count == 2
    onc_signal = next((s for s in signals if s["ticker_symbol"] == "ONC"), None)
    assert onc_signal is not None
    assert onc_signal["feature_source_count"] == 2
    assert onc_signal["feature_source_diversity"] == 2

    # ---- Run decisions ----
    with connect() as conn:
        for s in signals:
            make_decision(conn, s)

        decision_rows = conn.execute(
            text("SELECT signal_id, action FROM decisions")
        ).mappings().all()
        assert len(decision_rows) >= 3

    # ---- Render digest ----
    with connect() as conn:
        signals2 = list_signals_in_window(
            conn, since=datetime.now(timezone.utc) - timedelta(hours=72)
        )
        md = render_digest(
            conn,
            signals=signals2,
            window_start=datetime.now(timezone.utc) - timedelta(hours=72),
            window_end=datetime.now(timezone.utc),
        )

    assert "FESI Digest" in md
    assert "ONC" in md
    assert "Shadow Portfolio Summary" in md


def test_e2e_unprocessed_query_excludes_already_signaled(tmp_db, db_conn, insert_raw_item_dict):
    """After a raw_item is linked to a signal, it should not appear in the unprocessed list."""
    from fesi.store.raw_items import get_unprocessed_raw_items
    from fesi.store.signals import insert_signal
    from fesi.store.tickers import get_ticker_by_symbol

    rid = insert_raw_item_dict(title="FDA approves BeiGene drug", body="...")

    onc = get_ticker_by_symbol(db_conn, "ONC")
    insert_signal(
        db_conn,
        event_at=datetime.now(timezone.utc),
        primary_ticker_id=onc["id"],
        catalyst_type="fda_approval",
        sector="china_biotech_us_pipeline",
        headline="FDA approves BeiGene drug",
        summary="...",
        economics_summary=None,
        impact_score=5,
        probability_score=4,
        conviction_score=20.0,
        timeframe_bucket="0-3m",
        direction="bullish",
        raw_item_ids=[rid],
    )

    unprocessed = get_unprocessed_raw_items(
        db_conn, since=datetime.now(timezone.utc) - timedelta(hours=24)
    )
    assert all(r["id"] != rid for r in unprocessed)
