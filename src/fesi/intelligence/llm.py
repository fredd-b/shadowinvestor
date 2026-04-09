"""LLM adapter — Claude API with deterministic fallback when no API key.

This module is the single point where the rest of the pipeline talks to an LLM.
When ANTHROPIC_API_KEY is set, real Claude calls happen. When not, deterministic
keyword + pattern matching from `config/catalysts.yaml` is used so the entire
pipeline still runs end-to-end. The fallback is intentionally crude — its job is
to keep the system functional and produce baseline scoring data, not to be smart.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from fesi.config import (
    CatalystConfig,
    get_settings,
    load_catalysts,
    load_watchlist,
)
from fesi.logging import get_logger

log = get_logger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"


@dataclass
class ClassificationResult:
    catalyst_type: str
    sector: str
    primary_ticker_symbol: str | None
    primary_ticker_exchange: str | None
    headline: str
    summary: str
    economics_summary: str | None
    direction: str            # bullish | bearish | neutral
    timeframe_bucket: str     # 0-3m | 3-12m | 1-3y
    confidence: float         # 0-1
    method: str               # 'claude' | 'fallback'


@dataclass
class ScoringResult:
    impact_score: int         # 1-5
    probability_score: int    # 1-5
    sentiment_score: float    # -1 to 1
    reasoning: str
    method: str               # 'claude' | 'fallback'


# ============================================================================
# Public API
# ============================================================================

def has_anthropic() -> bool:
    return bool(get_settings().anthropic_api_key)


def classify(
    title: str, body: str = "", source: str = ""
) -> ClassificationResult:
    """Classify a raw item into a catalyst. Uses Claude if key set, else fallback."""
    if has_anthropic():
        try:
            return _claude_classify(title, body, source)
        except Exception as e:
            log.warning("claude_classify_failed_using_fallback", error=str(e))
    return _deterministic_classify(title, body, source)


def score(
    title: str,
    body: str,
    classification: ClassificationResult,
    catalyst: CatalystConfig,
) -> ScoringResult:
    """Score impact and probability of a classified signal."""
    if has_anthropic():
        try:
            return _claude_score(title, body, classification, catalyst)
        except Exception as e:
            log.warning("claude_score_failed_using_fallback", error=str(e))
    return _deterministic_score(title, body, classification, catalyst)


# ============================================================================
# Deterministic fallback (no API key required — keeps pipeline working)
# ============================================================================

def _patterns_for_catalyst(cat: CatalystConfig) -> list[str]:
    """Patterns to search for. Augmented from display_name when patterns is sparse.

    The display_name often contains the diagnostic phrase ("First Production
    Achieved", "Out-Licensing / Co-Development Deal"). We strip parentheticals
    and dashes, split on '/', and emit both the full phrase AND all 2-grams so
    "first production" matches "achieves first production at Rook I".
    """
    patterns = [p.lower() for p in (cat.patterns or [])]

    name = cat.display_name.split("(")[0].strip()
    name = name.split("—")[0].strip()
    if not name:
        return patterns

    for piece in name.split("/"):
        phrase = piece.strip().lower()
        if len(phrase) >= 5:
            patterns.append(phrase)
        # Emit 2-grams so order-independent partial matches work
        words = [w for w in phrase.replace("-", " ").split() if w]
        for i in range(len(words) - 1):
            ngram = f"{words[i]} {words[i + 1]}"
            if len(ngram) >= 5 and ngram not in patterns:
                patterns.append(ngram)

    return patterns


def _deterministic_classify(
    title: str, body: str, source: str
) -> ClassificationResult:
    """Pattern-match catalyst type from `patterns` in catalysts.yaml + display_name.

    For each catalyst type, count how many patterns match the title+body.
    Pick the catalyst with the highest match count, tie-broken by typical_impact.
    """
    catalysts = load_catalysts()
    watchlist = load_watchlist()
    text = f"{title}\n{body}".lower()

    best_type: str | None = None
    best_score = 0
    best_catalyst: CatalystConfig | None = None

    for ctype, cat in catalysts.items():
        match_count = 0
        for pat in _patterns_for_catalyst(cat):
            if pat in text:
                match_count += 1
        if match_count > best_score:
            best_type = ctype
            best_score = match_count
            best_catalyst = cat
        elif (match_count == best_score and match_count > 0
              and best_catalyst is not None
              and cat.typical_impact > best_catalyst.typical_impact):
            best_type = ctype
            best_catalyst = cat

    if best_type is None or best_catalyst is None:
        # No pattern matched — generic catch-all
        best_type = "guidance_raise"
        best_catalyst = catalysts.get(best_type) or next(iter(catalysts.values()))

    # Match watchlist ticker by symbol, name, or any alias appearing in text
    matched = None
    for wt in watchlist:
        candidates = [wt.symbol.lower(), wt.name.lower(), *(a.lower() for a in wt.aliases)]
        for cand in candidates:
            if not cand:
                continue
            if (
                f" {cand} " in f" {text} "
                or f"({cand})" in text
                or (len(cand) >= 4 and cand in text)
            ):
                matched = wt
                break
        if matched:
            break

    sector = matched.sector if matched else (
        best_catalyst.sectors[0] if best_catalyst.sectors else "binary_event_other"
    )

    return ClassificationResult(
        catalyst_type=best_type,
        sector=sector,
        primary_ticker_symbol=matched.symbol if matched else None,
        primary_ticker_exchange=matched.exchange if matched else None,
        headline=title[:300],
        summary=title[:500],
        economics_summary=_extract_economics_fallback(text),
        direction=best_catalyst.direction,
        timeframe_bucket=best_catalyst.typical_timeframe,
        confidence=min(1.0, 0.4 + 0.2 * best_score) if best_score > 0 else 0.3,
        method="fallback",
    )


_ECONOMICS_RE = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?\s?(?:million|billion|m|b)\b)",
    re.IGNORECASE,
)


def _extract_economics_fallback(text: str) -> str | None:
    matches = _ECONOMICS_RE.findall(text)
    if not matches:
        return None
    return "; ".join(m.strip() for m in matches[:5])


def _deterministic_score(
    title: str,
    body: str,
    classification: ClassificationResult,
    catalyst: CatalystConfig,
) -> ScoringResult:
    """Default scores from catalyst priors when LLM unavailable."""
    impact = catalyst.typical_impact
    probability = 3  # neutral default
    if catalyst.direction == "bullish":
        sentiment = 0.5
    elif catalyst.direction == "bearish":
        sentiment = -0.5
    else:
        sentiment = 0.0
    return ScoringResult(
        impact_score=impact,
        probability_score=probability,
        sentiment_score=sentiment,
        reasoning=(
            f"Fallback scoring: catalyst type {classification.catalyst_type} "
            f"has typical impact {impact}/5. No LLM available."
        ),
        method="fallback",
    )


# ============================================================================
# Claude implementations (only used when ANTHROPIC_API_KEY is set)
# ============================================================================

def _strip_md_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _claude_classify(
    title: str, body: str, source: str
) -> ClassificationResult:
    import anthropic

    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    catalysts = load_catalysts()
    watchlist = load_watchlist()

    catalyst_list = "\n".join(
        f"- {k}: {v.display_name} ({v.direction}, {v.typical_timeframe})"
        for k, v in catalysts.items()
    )
    watchlist_list = "\n".join(
        f"- {wt.symbol} ({wt.exchange}): {wt.name} [{wt.sector}]"
        for wt in watchlist
    )

    prompt = f"""You are a financial signal classifier. Read the news item and classify it.

CATALYST TYPES (pick exactly one):
{catalyst_list}

WATCHLIST TICKERS (use ONLY these symbols for primary_ticker_symbol if matched, else null):
{watchlist_list}

NEWS ITEM:
Source: {source}
Title: {title}
Body: {body[:2000]}

Output ONLY a single JSON object (no prose, no markdown fence) with these keys:
{{
  "catalyst_type": "<one of the catalyst keys above>",
  "sector": "<one of: biotech_pharma, china_biotech_us_pipeline, ai_infrastructure, crypto_to_ai_pivot, commodities_critical_minerals, binary_event_other>",
  "primary_ticker_symbol": "<ticker symbol if matched in watchlist, or null>",
  "primary_ticker_exchange": "<exchange if matched, or null>",
  "summary": "<2-3 sentence summary including key economics if present>",
  "economics_summary": "<deal terms like '$X upfront, $Y milestones', or null>",
  "direction": "<bullish | bearish | neutral>",
  "timeframe_bucket": "<0-3m | 3-12m | 1-3y>",
  "confidence": <float 0 to 1>
}}
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = _strip_md_fence(response.content[0].text)
    data = json.loads(text)

    return ClassificationResult(
        catalyst_type=data["catalyst_type"],
        sector=data["sector"],
        primary_ticker_symbol=data.get("primary_ticker_symbol"),
        primary_ticker_exchange=data.get("primary_ticker_exchange"),
        headline=title[:300],
        summary=data["summary"],
        economics_summary=data.get("economics_summary"),
        direction=data["direction"],
        timeframe_bucket=data["timeframe_bucket"],
        confidence=float(data.get("confidence", 0.7)),
        method="claude",
    )


def _claude_score(
    title: str,
    body: str,
    classification: ClassificationResult,
    catalyst: CatalystConfig,
) -> ScoringResult:
    import anthropic

    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    prompt = f"""You are a financial impact scorer. Score this signal on impact and probability.

Catalyst type: {classification.catalyst_type} ({catalyst.display_name})
Direction: {catalyst.direction}
Typical impact for this catalyst type: {catalyst.typical_impact}/5

NEWS ITEM:
Title: {title}
Body: {body[:2000]}

Score on:
- impact_score (1-5): how much would this move the stock if confirmed?
  1=trivial, 3=meaningful, 5=potentially doubles or halves the stock
- probability_score (1-5): how confident are you the implied move actually happens?
  1=highly speculative rumor, 3=plausible, 5=confirmed regulatory action
- sentiment_score (-1 to 1): tonal sentiment of the news for the company

Output ONLY a single JSON object (no prose, no markdown fence):
{{
  "impact_score": <int 1-5>,
  "probability_score": <int 1-5>,
  "sentiment_score": <float -1 to 1>,
  "reasoning": "<2-3 sentence explanation of your scoring>"
}}
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = _strip_md_fence(response.content[0].text)
    data = json.loads(text)

    return ScoringResult(
        impact_score=int(data["impact_score"]),
        probability_score=int(data["probability_score"]),
        sentiment_score=float(data.get("sentiment_score", 0.0)),
        reasoning=data["reasoning"],
        method="claude",
    )
