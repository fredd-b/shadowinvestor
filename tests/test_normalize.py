"""Tests for the normalize / cross-source dedup module."""
from __future__ import annotations

import json
from datetime import datetime, timezone


def _item(id_: int, title: str, source: str = "pr_newswire") -> dict:
    return {
        "id": id_,
        "title": title,
        "url": f"https://example.com/{id_}",
        "source": source,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "raw_payload": json.dumps({"description": title}),
    }


def test_normalize_groups_identical_titles():
    from fesi.intelligence.normalize import normalize

    items = [
        _item(1, "BeiGene receives FDA approval for Brukinsa", "pr_newswire"),
        _item(2, "BeiGene receives FDA approval for Brukinsa", "businesswire"),
    ]
    candidates = normalize(items)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.source_count == 2
    assert cand.source_diversity == 2
    assert sorted(cand.raw_item_ids) == [1, 2]


def test_normalize_groups_fuzzy_titles():
    from fesi.intelligence.normalize import normalize

    items = [
        _item(1, "FDA approves NexGen Energy uranium mine permit", "pr_newswire"),
        _item(2, "FDA approves NexGen Energy's uranium mine permit", "businesswire"),
    ]
    candidates = normalize(items, similarity_threshold=0.85)
    assert len(candidates) == 1
    assert candidates[0].source_count == 2


def test_normalize_keeps_distinct_events_separate():
    from fesi.intelligence.normalize import normalize

    items = [
        _item(1, "BeiGene receives FDA approval for Brukinsa"),
        _item(2, "Cameco wins long-term uranium supply contract"),
    ]
    candidates = normalize(items)
    assert len(candidates) == 2


def test_normalize_skips_empty_titles():
    from fesi.intelligence.normalize import normalize

    items = [
        _item(1, ""),
        _item(2, "Real headline"),
    ]
    candidates = normalize(items)
    assert len(candidates) == 1
    assert candidates[0].titles == ["Real headline"]


def test_candidate_primary_picks_longest_title():
    from fesi.intelligence.normalize import normalize

    items = [
        _item(1, "Short headline about NexGen"),
        _item(2, "Longer detailed headline about NexGen Energy uranium production milestone"),
    ]
    candidates = normalize(items, similarity_threshold=0.5)
    assert len(candidates) == 1
    assert "Longer detailed" in candidates[0].primary_title
