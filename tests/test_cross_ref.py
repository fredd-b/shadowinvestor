"""Tests for the cross-reference / corroboration boost."""
from __future__ import annotations


def test_single_source_no_boost():
    from fesi.intelligence.cross_ref import compute_conviction
    c = compute_conviction(
        impact_score=4, probability_score=4,
        source_count=1, source_diversity=1, source_keys=["pr_newswire"],
    )
    assert c == 16.0


def test_two_sources_15pct_boost():
    from fesi.intelligence.cross_ref import compute_conviction
    c = compute_conviction(
        impact_score=4, probability_score=4,
        source_count=2, source_diversity=2,
        source_keys=["pr_newswire", "businesswire"],
    )
    assert c == round(16 * 1.15, 2)


def test_three_sources_30pct_boost():
    from fesi.intelligence.cross_ref import compute_conviction
    c = compute_conviction(
        impact_score=4, probability_score=4,
        source_count=3, source_diversity=3,
        source_keys=["pr_newswire", "businesswire", "globenewswire"],
    )
    assert c == round(16 * 1.30, 2)


def test_regulatory_source_triggers_30pct_even_at_count_2():
    from fesi.intelligence.cross_ref import compute_conviction
    c = compute_conviction(
        impact_score=3, probability_score=3,
        source_count=2, source_diversity=2,
        source_keys=["pr_newswire", "sec_edgar"],
    )
    assert c == round(9 * 1.30, 2)
