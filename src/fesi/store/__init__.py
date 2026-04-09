"""Storage layer — typed CRUD on top of the SQLite schema.

Sub-modules (Phase 1):
  tickers.py    — load watchlist into tickers table; symbol → id resolver
  prices.py     — yfinance OHLCV cache
  raw_items.py  — store + dedupe raw_items
  signals.py    — store + query signals
  decisions.py  — store + query decisions
  outcomes.py   — daily job to compute T+N returns from prices
"""
