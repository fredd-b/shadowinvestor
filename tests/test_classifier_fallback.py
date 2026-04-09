"""Tests for the deterministic classifier + scorer fallback (no Anthropic key needed)."""
from __future__ import annotations


def test_classify_fda_approval(monkeypatch):
    """A title containing 'FDA approves' should classify as fda_approval."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import importlib
    import fesi.config
    importlib.reload(fesi.config)

    from fesi.intelligence.llm import classify
    result = classify("FDA approves BeiGene's Brukinsa for new indication", "")
    assert result.method == "fallback"
    assert result.catalyst_type == "fda_approval"
    assert result.direction == "bullish"
    assert result.primary_ticker_symbol == "ONC"


def test_classify_complete_response_letter(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import importlib
    import fesi.config
    importlib.reload(fesi.config)

    from fesi.intelligence.llm import classify
    result = classify(
        "Hutchmed receives complete response letter from FDA on cancer drug",
        "",
    )
    assert result.method == "fallback"
    assert result.catalyst_type == "fda_complete_response_letter"
    assert result.direction == "bearish"
    assert result.primary_ticker_symbol == "HCM"


def test_classify_uranium_first_production(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import importlib
    import fesi.config
    importlib.reload(fesi.config)

    from fesi.intelligence.llm import classify
    result = classify(
        "NexGen Energy achieves first production at Rook I uranium mine",
        "",
    )
    assert result.catalyst_type == "mine_first_production"
    assert result.direction == "bullish"
    assert result.primary_ticker_symbol == "NXE"


def test_extract_economics_finds_dollar_amounts(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import importlib
    import fesi.config
    importlib.reload(fesi.config)

    from fesi.intelligence.llm import classify
    title = "BeiGene signs licensing deal worth $200 million upfront and $1.5 billion in milestones"
    result = classify(title, "")
    assert result.economics_summary is not None
    assert "$200 million" in result.economics_summary or "$200" in result.economics_summary


def test_score_fallback_uses_typical_impact(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import importlib
    import fesi.config
    importlib.reload(fesi.config)

    from fesi.config import load_catalysts
    from fesi.intelligence.llm import classify, score

    cls = classify("FDA approves new drug for BeiGene", "")
    cat = load_catalysts()[cls.catalyst_type]
    sc = score("FDA approves new drug for BeiGene", "", cls, cat)
    assert sc.method == "fallback"
    assert sc.impact_score == cat.typical_impact
    assert 1 <= sc.probability_score <= 5


def test_unknown_catalyst_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import importlib
    import fesi.config
    importlib.reload(fesi.config)

    from fesi.intelligence.llm import classify
    result = classify("Random unrelated headline about weather", "")
    assert result.method == "fallback"
    # Should still return a valid catalyst type even when no patterns match
    assert result.catalyst_type
    assert result.confidence < 0.5
