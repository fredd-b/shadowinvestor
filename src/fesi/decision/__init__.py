"""Decision engine — converts scored signals into shadow/paper/live decisions.

Sub-modules (Phase 1):
  engine.py     — main decision loop, applies rules from config/risk.yaml
  rules.py      — entry/exit rule definitions per catalyst type
  sizing.py     — position sizing (fixed-risk first; Kelly fractional later)
  risk.py       — risk gate checks (position, concurrent, sector, circuit breakers)
"""
