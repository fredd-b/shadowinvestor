"""Ingestion adapters — one module per external data source.

Each adapter inherits from `IngestAdapter` (see base.py) and implements
`fetch()` returning a list of `RawItem`. Adapters do NOT classify or score —
that is the intelligence layer's responsibility.
"""
