"""Execution layer — broker adapters.

Phase 1: shadow only (no real broker calls).
Phase 4: paper trading via IBKR Web API.
Phase 5+: live trading via IBKR Web API, gated behind MODE=live env flag and
          manual approval for the first N live trades.

Sub-modules:
  ibkr.py       — Interactive Brokers Web API adapter
  shadow.py     — in-memory virtual fills for shadow mode
"""
