"""Perplexity API ingestion — LLM-grounded web search for catalyst discovery.

Automates Fred's manual Perplexity loop: one search query per sector per run,
asking for structured JSON output of recent catalyst events. Runs 5x/day via
the scheduler (30 queries/day, ~$0.03/day with the sonar model).

Key difference from other adapters: Perplexity can DISCOVER tickers not in the
watchlist. The ticker info goes into raw_payload for the classifier to resolve.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from fesi.config import get_settings, load_catalysts, load_sectors, load_watchlist
from fesi.ingest.base import IngestAdapter, RawItem
from fesi.ingest.http import RateLimiter, get_client, post_json
from fesi.logging import get_logger

log = get_logger(__name__)

API_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar"


class PerplexityAdapter(IngestAdapter):
    """Fetch catalyst events via Perplexity's grounded web search API."""

    source_key = "perplexity_api"

    def __init__(self) -> None:
        key = get_settings().perplexity_api_key
        self.enabled = bool(key)
        if not self.enabled:
            return
        self.client = get_client(
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        self.rate_limiter = RateLimiter(per_minute=60)
        self.sectors = load_sectors()
        self.catalysts = load_catalysts()
        self.watchlist = load_watchlist()

    def fetch(self) -> list[RawItem]:
        if not self.enabled:
            log.info("perplexity_skipped_no_api_key")
            return []

        queries = self._build_queries()
        items: list[RawItem] = []
        for sector_key, prompt in queries:
            try:
                self.rate_limiter.wait()
                response = self._call_api(prompt)
                parsed = self._parse_response(sector_key, response)
                items.extend(parsed)
            except Exception as e:
                log.warning(
                    "perplexity_query_failed", sector=sector_key, error=str(e)
                )
        log.info("perplexity_fetch_done", items=len(items), queries=len(queries))
        return items

    # ------------------------------------------------------------------
    # Query generation
    # ------------------------------------------------------------------

    def _build_queries(self) -> list[tuple[str, str]]:
        """Build one search prompt per sector."""
        queries: list[tuple[str, str]] = []
        for sector_key, sector in self.sectors.items():
            catalyst_names = self._catalyst_names_for_sector(sector_key)
            watchlist_lines = self._watchlist_lines_for_sector(sector_key)
            prompt = self._make_prompt(sector, catalyst_names, watchlist_lines)
            queries.append((sector_key, prompt))
        return queries

    def _catalyst_names_for_sector(self, sector_key: str) -> list[str]:
        """Return display names of catalysts relevant to this sector."""
        names: list[str] = []
        for cat in self.catalysts.values():
            if sector_key in cat.sectors:
                names.append(cat.display_name)
        return names

    def _watchlist_lines_for_sector(self, sector_key: str) -> list[str]:
        """Return 'SYMBOL (Name) — thesis' lines for tickers in this sector."""
        lines: list[str] = []
        for t in self.watchlist:
            if t.sector == sector_key:
                aliases = ""
                if hasattr(t, "aliases") and t.aliases:
                    aliases = f" (also: {', '.join(t.aliases)})"
                lines.append(f"- {t.symbol} ({t.name}{aliases}) — {t.thesis}")
        return lines

    def _make_prompt(
        self,
        sector: Any,
        catalyst_names: list[str],
        watchlist_lines: list[str],
    ) -> str:
        catalysts_str = ", ".join(catalyst_names) if catalyst_names else "any material catalyst"
        watchlist_str = "\n".join(watchlist_lines) if watchlist_lines else "(none)"

        return f"""You are a financial research assistant. Search for news from the last 6 hours about catalyst events in the {sector.display_name} sector.

Sector description: {sector.description}

Catalyst types to watch: {catalysts_str}

Companies on our watchlist (report any news about these):
{watchlist_str}

Also report events for any OTHER companies in this sector, even if not on the watchlist above.

Return ONLY a JSON array of event objects. Each event:
{{
  "title": "concise event headline (under 200 chars)",
  "ticker": "US ticker symbol if identifiable, else null",
  "exchange": "NASDAQ/NYSE/AMEX/HKEX or null",
  "company_name": "full company name",
  "catalyst_type": "brief label (e.g. 'FDA approval', 'Phase 3 positive', 'offtake signed')",
  "summary": "2-3 sentence summary with key economics if available",
  "date": "YYYY-MM-DD if known, else null",
  "url": "most authoritative source URL if known, else null"
}}

If no relevant events found in the last 6 hours, return an empty array: []
Do NOT invent events. Only report events with real sources."""

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    def _call_api(self, prompt: str) -> dict:
        """Call Perplexity chat completions API."""
        body = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        return post_json(self.client, API_URL, json_body=body)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self, sector_key: str, api_response: dict
    ) -> list[RawItem]:
        """Parse Perplexity response into RawItems."""
        content = (
            api_response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        citations = api_response.get("citations", [])

        events = self._extract_events(content)
        if events is None:
            # JSON parse failed — create a single fallback item from the prose
            return self._fallback_item(sector_key, content, citations)

        items: list[RawItem] = []
        now = datetime.now(timezone.utc)
        for event in events:
            title = (event.get("title") or "").strip()
            if not title:
                continue

            url = event.get("url") or (citations[0] if citations else None)
            published_at = self._parse_date(event.get("date"))

            source_id = f"pplx-{sector_key}-{hashlib.sha256(title.encode()).hexdigest()[:12]}"

            items.append(
                RawItem(
                    source=self.source_key,
                    source_id=source_id,
                    fetched_at=now,
                    published_at=published_at,
                    url=url,
                    title=title,
                    raw_payload={
                        "sector_query": sector_key,
                        "event": event,
                        "citations": citations,
                        "model": MODEL,
                    },
                    content_hash=RawItem.make_content_hash(
                        title, url, published_at
                    ),
                )
            )
        return items

    def _extract_events(self, content: str) -> list[dict] | None:
        """Try to parse JSON array of events from Perplexity's response.

        Perplexity sometimes appends prose explanation after the JSON array.
        We try: (1) full content, (2) extract first [...] block via bracket matching.
        """
        text = _strip_md_fences(content).strip()
        if not text:
            return []
        # Attempt 1: parse the whole thing
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        # Attempt 2: extract the first JSON array by finding matched brackets
        extracted = _extract_json_array(text)
        if extracted is not None:
            try:
                parsed = json.loads(extracted)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        log.warning("perplexity_json_parse_failed", content_preview=text[:200])
        return None

    def _fallback_item(
        self, sector_key: str, content: str, citations: list[str]
    ) -> list[RawItem]:
        """When JSON parsing fails, wrap the prose as a single RawItem."""
        if not content.strip():
            return []
        title = content[:200].replace("\n", " ").strip()
        url = citations[0] if citations else None
        now = datetime.now(timezone.utc)
        return [
            RawItem(
                source=self.source_key,
                source_id=f"pplx-{sector_key}-fallback-{hashlib.sha256(title.encode()).hexdigest()[:12]}",
                fetched_at=now,
                published_at=None,
                url=url,
                title=title,
                raw_payload={
                    "sector_query": sector_key,
                    "raw_content": content,
                    "citations": citations,
                    "model": MODEL,
                    "parse_mode": "fallback",
                },
                content_hash=RawItem.make_content_hash(title, url, None),
            )
        ]

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse YYYY-MM-DD date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            return None


def _strip_md_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from LLM output."""
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    return text


def _extract_json_array(text: str) -> str | None:
    """Extract the first top-level [...] from text that may have trailing prose."""
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
