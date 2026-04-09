"""SEC EDGAR ingestion adapter.

Pulls recent 8-K filings for watchlist tickers from EDGAR's submissions JSON
endpoint. Free, no API key required, but requires a User-Agent with contact info
(see ingest/http.py).

Endpoints:
  - Ticker → CIK map: https://www.sec.gov/files/company_tickers.json
  - Submissions:      https://data.sec.gov/submissions/CIK{cik:010d}.json
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import json

from fesi.config import load_watchlist
from fesi.db import connect
from fesi.ingest.base import IngestAdapter, RawItem
from fesi.ingest.http import RateLimiter, fetch_json, get_client
from fesi.logging import get_logger
from fesi.store.tickers import list_watchlist_tickers

log = get_logger(__name__)

CIK_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
CIK_CACHE_PATH = Path("data/sec_cik_map.json")


class SecEdgarAdapter(IngestAdapter):
    """8-K filings ingestion for US-listed watchlist tickers."""

    source_key = "sec_edgar"

    def __init__(self, *, lookback_hours: int = 48):
        self.lookback_hours = lookback_hours
        self.rate_limiter = RateLimiter(per_minute=600)  # SEC = 10 req/sec
        self.client = get_client(
            headers={"Accept": "application/json", "Host": "data.sec.gov"}
        )

    def fetch(self) -> list[RawItem]:
        try:
            cik_map = self._load_cik_map()
        except Exception as e:
            log.warning("sec_cik_map_fetch_failed", error=str(e))
            return []

        # Get watchlist symbols (US-listed only — HK/TSX won't have CIKs)
        watchlist = load_watchlist()
        us_symbols = [
            wt.symbol for wt in watchlist
            if wt.exchange in ("NASDAQ", "NYSE", "AMEX", "ARCA")
        ]

        items: list[RawItem] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        cutoff_date = cutoff.strftime("%Y-%m-%d")

        for symbol in us_symbols:
            cik = cik_map.get(symbol.upper())
            if not cik:
                continue
            try:
                self.rate_limiter.wait()
                data = fetch_json(
                    self.client,
                    SUBMISSIONS_URL.format(cik=int(cik)),
                )
                items.extend(self._parse_submissions(symbol, cik, data, cutoff_date))
            except Exception as e:
                log.warning("sec_submissions_failed", symbol=symbol, error=str(e))

        log.info("sec_edgar_fetch_done", items=len(items), checked=len(us_symbols))
        return items

    def _load_cik_map(self) -> dict[str, str]:
        """Load (and cache) the SEC's ticker → CIK mapping.

        The file is ~5MB and changes infrequently. We refresh weekly.
        """
        CIK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        if CIK_CACHE_PATH.exists():
            age = datetime.now(timezone.utc) - datetime.fromtimestamp(
                CIK_CACHE_PATH.stat().st_mtime, tz=timezone.utc
            )
            if age < timedelta(days=7):
                return json.loads(CIK_CACHE_PATH.read_text())

        log.info("sec_cik_map_refreshing")
        # Use a different host header for sec.gov vs data.sec.gov
        client = get_client(headers={"Host": "www.sec.gov"})
        try:
            data = fetch_json(client, CIK_MAP_URL)
        finally:
            client.close()

        # data is {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        cik_map = {entry["ticker"].upper(): str(entry["cik_str"]) for entry in data.values()}
        CIK_CACHE_PATH.write_text(json.dumps(cik_map))
        log.info("sec_cik_map_cached", path=str(CIK_CACHE_PATH), entries=len(cik_map))
        return cik_map

    def _parse_submissions(
        self, symbol: str, cik: str, data: dict, cutoff_date: str
    ) -> list[RawItem]:
        items: list[RawItem] = []
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        primary_descriptions = recent.get("primaryDocDescription", [])

        for i, form in enumerate(forms):
            if form not in ("8-K", "8-K/A", "6-K"):
                continue
            if i >= len(filing_dates) or filing_dates[i] < cutoff_date:
                continue
            accession = accession_numbers[i] if i < len(accession_numbers) else ""
            primary = primary_docs[i] if i < len(primary_docs) else ""
            description = (
                primary_descriptions[i]
                if i < len(primary_descriptions)
                else ""
            )

            cik_int = int(cik)
            accession_clean = accession.replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
                f"{accession_clean}/{primary}"
            )

            try:
                pub = datetime.strptime(filing_dates[i], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pub = None

            title = f"{symbol} {form}: {description or 'filing'}"
            payload = {
                "symbol": symbol,
                "cik": cik,
                "form": form,
                "filing_date": filing_dates[i],
                "accession": accession,
                "primary_document": primary,
                "description": description,
                "url": url,
            }

            items.append(
                RawItem(
                    source=self.source_key,
                    source_id=accession,
                    fetched_at=datetime.now(timezone.utc),
                    published_at=pub,
                    url=url,
                    title=title,
                    raw_payload=payload,
                    content_hash=RawItem.make_content_hash(title, url, pub),
                )
            )
        return items
