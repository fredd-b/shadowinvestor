"""Classifier — public interface for catalyst classification.

Thin wrapper around `fesi.intelligence.llm` so the rest of the pipeline imports
from a stable name and we can swap out the underlying LLM later.
"""
from __future__ import annotations

from fesi.intelligence.llm import ClassificationResult, classify

__all__ = ["ClassificationResult", "classify"]
