"""Tests for the Perplexity API ingest adapter.

All tests mock the HTTP layer — no real Perplexity API calls.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from fesi.ingest.base import RawItem
from fesi.ingest.perplexity import PerplexityAdapter
from fesi.intelligence.llm import strip_md_fence


# ---------- Fixtures ----------

SAMPLE_EVENTS = [
    {
        "title": "FDA Approves Brukinsa for Follicular Lymphoma",
        "ticker": "ONC",
        "exchange": "NASDAQ",
        "company_name": "BeOne Medicines",
        "catalyst_type": "FDA approval",
        "summary": "The FDA granted approval for Brukinsa in relapsed FL. This expands the label to a third indication.",
        "date": "2026-04-10",
        "url": "https://www.fda.gov/news-events/approvals/brukinsa-fl",
    },
    {
        "title": "NexGen Energy Receives Federal EA Approval for Rook I",
        "ticker": "NXE",
        "exchange": "NYSE",
        "company_name": "NexGen Energy",
        "catalyst_type": "mine commissioning milestone",
        "summary": "The Canadian Nuclear Safety Commission accepted NexGen's environmental assessment. Construction expected to begin Q3 2026.",
        "date": "2026-04-10",
        "url": "https://www.nexgenenergy.ca/news/ea-approval",
    },
    {
        "title": "Cipher Mining Signs 200MW AI Hosting Deal with CoreWeave",
        "ticker": "CIFR",
        "exchange": "NASDAQ",
        "company_name": "Cipher Mining",
        "catalyst_type": "HPC hosting contract",
        "summary": "Cipher Mining signed a 5-year, 200MW hosting agreement with CoreWeave for GPU compute colocation.",
        "date": None,
        "url": None,
    },
]

SAMPLE_API_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps(SAMPLE_EVENTS),
            }
        }
    ],
    "citations": [
        "https://www.fda.gov/news-events/approvals/brukinsa-fl",
        "https://www.nexgenenergy.ca/news/ea-approval",
    ],
}

EMPTY_API_RESPONSE = {
    "choices": [{"message": {"content": "[]"}}],
    "citations": [],
}

PROSE_API_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": "I found no significant catalyst events in the last 6 hours for this sector. Markets were quiet today with no major FDA decisions or trial readouts.",
            }
        }
    ],
    "citations": ["https://example.com/markets-quiet"],
}


# ---------- Tests ----------


def test_skips_when_no_key(monkeypatch):
    """Adapter returns [] and logs when PERPLEXITY_API_KEY is empty."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "")
    adapter = PerplexityAdapter()
    assert not adapter.enabled
    assert adapter.fetch() == []


def test_parses_structured_json(monkeypatch):
    """Adapter correctly parses a 3-event JSON response into 3 RawItems."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key-123")
    adapter = PerplexityAdapter()

    with patch.object(adapter, "_call_api", return_value=SAMPLE_API_RESPONSE):
        # Only run one sector query to keep test fast
        with patch.object(
            adapter,
            "_build_queries",
            return_value=[("biotech_pharma", "test prompt")],
        ):
            items = adapter.fetch()

    assert len(items) == 3
    assert all(isinstance(i, RawItem) for i in items)
    assert all(i.source == "perplexity_api" for i in items)

    # Check first item
    fda = items[0]
    assert "Brukinsa" in fda.title
    assert fda.url == "https://www.fda.gov/news-events/approvals/brukinsa-fl"
    assert fda.raw_payload["sector_query"] == "biotech_pharma"
    assert fda.raw_payload["event"]["ticker"] == "ONC"
    assert fda.published_at == datetime(2026, 4, 10, tzinfo=timezone.utc)

    # Third item has no URL — should fall back to first citation
    cifr = items[2]
    assert cifr.url == "https://www.fda.gov/news-events/approvals/brukinsa-fl"
    assert cifr.published_at is None  # date was null


def test_handles_empty_results(monkeypatch):
    """Empty JSON array from Perplexity returns empty list."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key-123")
    adapter = PerplexityAdapter()

    with patch.object(adapter, "_call_api", return_value=EMPTY_API_RESPONSE):
        with patch.object(
            adapter,
            "_build_queries",
            return_value=[("ai_infrastructure", "test prompt")],
        ):
            items = adapter.fetch()

    assert items == []


def test_handles_malformed_json(monkeypatch):
    """Prose response (not JSON) falls back to a single RawItem."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key-123")
    adapter = PerplexityAdapter()

    with patch.object(adapter, "_call_api", return_value=PROSE_API_RESPONSE):
        with patch.object(
            adapter,
            "_build_queries",
            return_value=[("commodities_critical_minerals", "test prompt")],
        ):
            items = adapter.fetch()

    assert len(items) == 1
    assert items[0].source == "perplexity_api"
    assert "fallback" in items[0].source_id
    assert items[0].raw_payload["parse_mode"] == "fallback"
    assert items[0].url == "https://example.com/markets-quiet"


def test_builds_one_query_per_sector(monkeypatch):
    """_build_queries returns exactly 6 tuples (one per sector)."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key-123")
    adapter = PerplexityAdapter()
    queries = adapter._build_queries()

    assert len(queries) == 6
    sector_keys = [q[0] for q in queries]
    assert "biotech_pharma" in sector_keys
    assert "china_biotech_us_pipeline" in sector_keys
    assert "ai_infrastructure" in sector_keys
    assert "crypto_to_ai_pivot" in sector_keys
    assert "commodities_critical_minerals" in sector_keys
    assert "binary_event_other" in sector_keys

    # Each query should be a non-empty prompt string
    for _, prompt in queries:
        assert isinstance(prompt, str)
        assert len(prompt) > 100


def test_dedup_via_content_hash(monkeypatch, db_conn):
    """Same response ingested twice → second batch all skipped."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key-123")
    adapter = PerplexityAdapter()

    from fesi.store.raw_items import insert_raw_items

    with patch.object(adapter, "_call_api", return_value=SAMPLE_API_RESPONSE):
        with patch.object(
            adapter,
            "_build_queries",
            return_value=[("biotech_pharma", "test prompt")],
        ):
            items1 = adapter.fetch()
            result1 = insert_raw_items(db_conn, items1)

            items2 = adapter.fetch()
            result2 = insert_raw_items(db_conn, items2)

    assert result1["inserted"] == 3
    assert result1["skipped"] == 0
    assert result2["inserted"] == 0
    assert result2["skipped"] == 3


def test_cross_source_normalize(monkeypatch, make_raw_item):
    """Perplexity + press wire items with similar titles merge in normalize."""
    from fesi.intelligence.normalize import normalize
    from fesi.store.raw_items import insert_raw_items

    # Simulate a wire item and a perplexity item about the same event
    wire_item = make_raw_item(
        title="Legend Biotech Announces Positive Phase 3 Results for Carvykti in Multiple Myeloma",
        source="press_wires",
    )
    pplx_item = RawItem(
        source="perplexity_api",
        source_id="pplx-biotech-abc123",
        fetched_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc),
        url="https://example.com/carvykti",
        title="Legend Biotech Announces Positive Phase 3 Results for Carvykti in Myeloma",
        raw_payload={"sector_query": "biotech_pharma", "event": {}},
        content_hash=RawItem.make_content_hash(
            "Legend Biotech Reports Positive Phase 3 Results for Carvykti in Myeloma",
            "https://example.com/carvykti",
            None,
        ),
    )

    # Convert to dicts like get_unprocessed_raw_items returns
    items = [
        {"id": 1, "source": wire_item.source, "title": wire_item.title,
         "url": wire_item.url, "published_at": wire_item.published_at.isoformat(),
         "raw_payload": json.dumps(wire_item.raw_payload)},
        {"id": 2, "source": pplx_item.source, "title": pplx_item.title,
         "url": pplx_item.url, "published_at": pplx_item.published_at.isoformat(),
         "raw_payload": json.dumps(pplx_item.raw_payload)},
    ]
    candidates = normalize(items)

    # Should merge into 1 candidate with source_diversity >= 2
    assert len(candidates) == 1
    assert candidates[0].source_diversity >= 2
    assert "press_wires" in candidates[0].sources
    assert "perplexity_api" in candidates[0].sources


def teststrip_md_fence():
    """Markdown fence stripping works for various formats."""
    assert strip_md_fence('```json\n[{"a":1}]\n```') == '[{"a":1}]'
    assert strip_md_fence('```\n[{"a":1}]\n```') == '[{"a":1}]'
    assert strip_md_fence('[{"a":1}]') == '[{"a":1}]'
