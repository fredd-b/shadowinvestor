"""Cross-reference / corroboration boost.

When a signal is reported by multiple distinct sources — especially when a
regulatory source is among them — we boost the conviction. This is the only
place where multi-source effects are modeled.
"""
from __future__ import annotations

from fesi.config import load_sources


def compute_conviction(
    impact_score: int,
    probability_score: int,
    source_count: int,
    source_diversity: int,
    source_keys: list[str],
) -> float:
    """Conviction = base × corroboration_multiplier.

    base = impact_score × probability_score   (range 1..25)
    multiplier:
        single source                           1.00
        2 distinct sources                      1.15
        3+ distinct sources OR
        any regulatory source in the mix        1.30
    """
    base = impact_score * probability_score

    sources_cfg = load_sources()
    has_regulatory = any(
        (s in sources_cfg and sources_cfg[s].type == "regulatory")
        for s in source_keys
    )

    if source_diversity >= 3 or has_regulatory:
        multiplier = 1.30
    elif source_diversity >= 2:
        multiplier = 1.15
    else:
        multiplier = 1.00

    return round(base * multiplier, 2)
