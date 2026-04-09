"""Abstract base class and shared types for ingestion adapters.

Each external data source is implemented as a subclass of `IngestAdapter`.
The contract is:
  - `fetch()` returns a list of normalized `RawItem` instances
  - The base class persists them via `store_raw_items` (Phase 1 ticket F1-04)
  - Adapters do NOT do classification or scoring — that is the intelligence layer
  - Adapters MUST be idempotent: re-running over the same window adds zero rows
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RawItem:
    """Normalized payload from a single source. Becomes one row in `raw_items`."""

    source: str            # e.g. 'fda_openfda' — must match config/sources.yaml
    source_id: str         # the source's own unique id (for dedupe)
    fetched_at: datetime   # UTC, when WE fetched it
    published_at: datetime | None  # when source claims it was published
    url: str | None
    title: str
    raw_payload: dict[str, Any]
    content_hash: str      # sha256 of (title + url + published_at) for dedupe

    @staticmethod
    def make_content_hash(title: str, url: str | None, published_at: datetime | None) -> str:
        h = hashlib.sha256()
        h.update(title.encode("utf-8"))
        h.update(b"|")
        h.update((url or "").encode("utf-8"))
        h.update(b"|")
        h.update((published_at.isoformat() if published_at else "").encode("utf-8"))
        return h.hexdigest()


class IngestAdapter(ABC):
    """Base class for all ingestion adapters."""

    #: Unique source key, must match an entry in config/sources.yaml
    source_key: str = ""

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Fetch items from this source. MUST be idempotent."""
        raise NotImplementedError
