"""Scorer — public interface for impact × probability scoring.

Thin wrapper around `fesi.intelligence.llm`.
"""
from __future__ import annotations

from fesi.intelligence.llm import ScoringResult, score

__all__ = ["ScoringResult", "score"]
