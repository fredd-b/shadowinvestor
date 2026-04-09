"""Digest layer — render markdown digests and deliver via Pushover/Telegram.

Sub-modules (Phase 1):
  render.py     — markdown renderer matching Fred's Perplexity prompt format
                  (Top 10 + Emerging + Watchlist + Follow-up)
  notify.py     — Pushover (urgent push) + Telegram bot (full digest) delivery
"""
