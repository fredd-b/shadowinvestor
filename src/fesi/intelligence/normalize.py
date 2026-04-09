"""Normalize raw_items into candidate signals via fuzzy title matching."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from fesi.logging import get_logger

log = get_logger(__name__)


@dataclass
class CandidateSignal:
    """Group of raw_items representing one underlying event."""
    raw_item_ids: list[int] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    bodies: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    earliest_published: datetime | None = None

    @property
    def primary_title(self) -> str:
        return max(self.titles, key=len) if self.titles else ""

    @property
    def primary_body(self) -> str:
        return max(self.bodies, key=len) if self.bodies else ""

    @property
    def source_count(self) -> int:
        return len(self.raw_item_ids)

    @property
    def source_diversity(self) -> int:
        return len(set(self.sources))


def normalize(
    raw_items: list[dict], similarity_threshold: float = 0.85
) -> list[CandidateSignal]:
    """Group raw_items into candidate signals via fuzzy title matching.

    Items with title similarity >= threshold are merged. The first match wins.
    """
    candidates: list[CandidateSignal] = []

    for item in raw_items:
        title = (item.get("title") or "").strip()
        if not title:
            continue

        merged = False
        for cand in candidates:
            if not cand.titles:
                continue
            best_sim = max(
                SequenceMatcher(None, title.lower(), t.lower()).ratio()
                for t in cand.titles
            )
            if best_sim >= similarity_threshold:
                cand.raw_item_ids.append(item["id"])
                cand.titles.append(title)
                cand.bodies.append(_extract_body(item))
                cand.urls.append(item.get("url") or "")
                cand.sources.append(item.get("source") or "")
                pub = _parse_pub(item.get("published_at"))
                if pub and (cand.earliest_published is None or pub < cand.earliest_published):
                    cand.earliest_published = pub
                merged = True
                break

        if not merged:
            candidates.append(
                CandidateSignal(
                    raw_item_ids=[item["id"]],
                    titles=[title],
                    bodies=[_extract_body(item)],
                    urls=[item.get("url") or ""],
                    sources=[item.get("source") or ""],
                    earliest_published=_parse_pub(item.get("published_at")),
                )
            )

    log.info("normalize_done", input=len(raw_items), candidates=len(candidates))
    return candidates


def _extract_body(item: dict) -> str:
    """Best-effort body extraction from raw_payload JSON."""
    payload = item.get("raw_payload")
    if not payload:
        return ""
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except (json.JSONDecodeError, TypeError):
        return str(payload)[:2000]
    if not isinstance(data, dict):
        return ""
    for key in ("description", "summary", "body", "abstract", "content", "text"):
        v = data.get(key)
        if isinstance(v, str) and v:
            return v[:5000]
    return ""


def _parse_pub(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
