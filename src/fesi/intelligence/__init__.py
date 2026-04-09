"""Intelligence layer — normalize, classify, score, cross-reference.

Inputs: rows from `raw_items`.
Outputs: rows in `signals` (with full feature vector).

Sub-modules (Phase 1):
  normalize.py   — dedupe + group raw_items into candidate signals
  classifier.py  — LLM-driven catalyst type classification
  scorer.py      — LLM-driven impact × probability scoring
  cross_ref.py   — multi-source corroboration boost
  synthesizer.py — produces the digest body from a set of scored signals
"""
