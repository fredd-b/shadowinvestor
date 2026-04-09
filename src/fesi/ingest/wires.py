"""Press wires RSS ingestion (PR Newswire / GlobeNewswire / BusinessWire).

Pulls health/biotech/energy/AI press releases from RSS feeds. Free, no API key.
We use stdlib xml.etree (no feedparser dependency) for resilience.

The RSS endpoints occasionally change — keep them in this file as a constant
list and update if a feed dies. Each item is filtered against the keyword
patterns from `config/catalysts.yaml` to keep the noise level manageable.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from fesi.config import load_catalysts
from fesi.ingest.base import IngestAdapter, RawItem
from fesi.ingest.http import RateLimiter, fetch_text, get_client
from fesi.logging import get_logger

log = get_logger(__name__)


# RSS feeds — these are stable as of 2026-04. If one breaks, comment it out
# and add a replacement.
WIRE_FEEDS: list[tuple[str, str]] = [
    ("pr_newswire_health",
     "https://www.prnewswire.com/rss/health-latest-news/health-latest-news-list.rss"),
    ("pr_newswire_energy",
     "https://www.prnewswire.com/rss/energy-latest-news/energy-latest-news-list.rss"),
    ("pr_newswire_financial",
     "https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss"),
    ("globenewswire_all_english",
     "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20All%20News%20English"),
    ("businesswire_all",
     "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJfXFlbWQ=="),
]


class WiresAdapter(IngestAdapter):
    """Aggregate ingestion from multiple press wire RSS feeds."""

    source_key = "press_wires"

    def __init__(self, *, lookback_hours: int = 48):
        self.lookback_hours = lookback_hours
        self.rate_limiter = RateLimiter(per_minute=60)
        # PR Newswire blocks non-browser User-Agents — use a Firefox UA for RSS
        self.client = get_client(
            headers={
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) "
                    "Gecko/20100101 Firefox/121.0"
                ),
            }
        )
        # Build a single regex of all catalyst patterns to filter noise
        catalysts = load_catalysts()
        all_patterns = []
        for cat in catalysts.values():
            all_patterns.extend(cat.patterns)
        # Add some always-on financial keywords
        all_patterns.extend([
            "FDA", "phase 3", "phase 2", "trial", "approval", "approves",
            "designation", "uranium", "lithium", "GPU", "AI",
            "data center", "hosting", "supply agreement", "offtake",
            "partnership", "license", "Ph 3", "Ph 2", "BLA", "NDA",
            "milestone", "discovery", "drilling",
        ])
        if all_patterns:
            escaped = [re.escape(p) for p in all_patterns]
            self.keyword_re = re.compile(
                r"(?i)" + "|".join(escaped)
            )
        else:
            self.keyword_re = None

    def fetch(self) -> list[RawItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        items: list[RawItem] = []
        for feed_name, url in WIRE_FEEDS:
            try:
                self.rate_limiter.wait()
                xml = fetch_text(self.client, url)
                items.extend(self._parse_rss(feed_name, xml, cutoff))
            except Exception as e:
                log.warning("rss_fetch_failed", feed=feed_name, url=url, error=str(e))
        log.info("wires_fetch_done", items=len(items))
        return items

    def _parse_rss(
        self, feed_name: str, xml: str, cutoff: datetime
    ) -> list[RawItem]:
        out: list[RawItem] = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            log.warning("rss_parse_failed", feed=feed_name, error=str(e))
            return out

        # Find all <item> elements anywhere in the tree
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")
            guid_el = item.find("guid")

            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            description = (desc_el.text or "").strip() if desc_el is not None else ""
            guid = (guid_el.text or "").strip() if guid_el is not None else link

            if not title:
                continue

            # Keyword filter
            if self.keyword_re and not self.keyword_re.search(f"{title} {description}"):
                continue

            pub: datetime | None = None
            if pub_el is not None and pub_el.text:
                try:
                    pub = parsedate_to_datetime(pub_el.text)
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    pub = None

            if pub and pub < cutoff:
                continue

            payload = {
                "feed": feed_name,
                "title": title,
                "link": link,
                "description": description,
                "pub_date": pub_el.text if pub_el is not None else None,
                "guid": guid,
            }

            out.append(
                RawItem(
                    source=self.source_key,
                    source_id=guid or f"{feed_name}-{title[:80]}",
                    fetched_at=datetime.now(timezone.utc),
                    published_at=pub,
                    url=link,
                    title=title,
                    raw_payload=payload,
                    content_hash=RawItem.make_content_hash(title, link, pub),
                )
            )
        return out
