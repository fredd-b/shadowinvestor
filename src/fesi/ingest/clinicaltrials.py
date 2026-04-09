"""ClinicalTrials.gov v2 API ingestion adapter.

Pulls recently updated trials, filtered to (a) trials sponsored by watchlist
companies, and (b) trials sponsored by China-based organizations (for the
china_biotech_us_pipeline category).

API docs: https://clinicaltrials.gov/data-api/api
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fesi.config import load_watchlist
from fesi.ingest.base import IngestAdapter, RawItem
from fesi.ingest.http import RateLimiter, fetch_json, get_client
from fesi.logging import get_logger

log = get_logger(__name__)

CT_URL = "https://clinicaltrials.gov/api/v2/studies"
PAGE_SIZE = 100


class ClinicalTrialsAdapter(IngestAdapter):
    """Pull recently-updated trial records from ClinicalTrials.gov."""

    source_key = "clinicaltrials_gov"

    def __init__(self, *, lookback_hours: int = 48):
        self.lookback_hours = lookback_hours
        self.rate_limiter = RateLimiter(per_minute=60)
        self.client = get_client()

    def fetch(self) -> list[RawItem]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=self.lookback_hours)

        # CT.gov v2 uses Essie filter expressions for date ranges
        date_filter = (
            f"AREA[LastUpdatePostDate]RANGE"
            f"[{start.strftime('%Y-%m-%d')},{end.strftime('%Y-%m-%d')}]"
        )

        items: list[RawItem] = []

        # Query A: trials sponsored by watchlist companies
        watchlist = load_watchlist()
        biotech_names = [
            wt.name for wt in watchlist
            if wt.sector in ("biotech_pharma", "china_biotech_us_pipeline")
        ]
        for sponsor in biotech_names:
            try:
                self.rate_limiter.wait()
                data = fetch_json(
                    self.client,
                    CT_URL,
                    params={
                        "query.spons": sponsor,
                        "filter.advanced": date_filter,
                        "pageSize": PAGE_SIZE,
                        "format": "json",
                    },
                )
                items.extend(self._parse(data, lookup_sponsor=sponsor))
            except Exception as e:
                log.warning("ct_query_failed", sponsor=sponsor, error=str(e))

        # Query B: any trial in China (broader sweep for the China-biotech category)
        try:
            self.rate_limiter.wait()
            data = fetch_json(
                self.client,
                CT_URL,
                params={
                    "query.locn": "China",
                    "filter.advanced": date_filter,
                    "pageSize": PAGE_SIZE,
                    "format": "json",
                },
            )
            items.extend(self._parse(data, lookup_sponsor=None))
        except Exception as e:
            log.warning("ct_china_sweep_failed", error=str(e))

        log.info("clinicaltrials_fetch_done", items=len(items))
        return items

    def _parse(self, data: dict, lookup_sponsor: str | None) -> list[RawItem]:
        out: list[RawItem] = []
        studies = data.get("studies", []) or []
        for study in studies:
            try:
                out.append(self._build_item(study))
            except Exception as e:
                log.debug("ct_parse_failed", error=str(e))
        return out

    def _build_item(self, study: dict) -> RawItem:
        protocol = study.get("protocolSection", {}) or {}
        ident = protocol.get("identificationModule", {}) or {}
        status = protocol.get("statusModule", {}) or {}
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {}) or {}

        nct_id = ident.get("nctId", "")
        brief_title = ident.get("briefTitle", "")
        official_title = ident.get("officialTitle", "")
        sponsor = (
            (sponsor_module.get("leadSponsor") or {}).get("name", "")
        )
        overall_status = status.get("overallStatus", "")
        last_update = status.get("lastUpdatePostDateStruct", {}).get("date", "")
        phase = (protocol.get("designModule") or {}).get("phases", [])
        phase_str = ", ".join(phase) if phase else ""

        title = f"[{nct_id}] {sponsor} — {brief_title}"
        if phase_str:
            title += f" ({phase_str})"
        if overall_status:
            title += f" — {overall_status}"

        url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None

        try:
            pub = datetime.strptime(last_update, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pub = None

        payload = {
            "nct_id": nct_id,
            "brief_title": brief_title,
            "official_title": official_title,
            "sponsor": sponsor,
            "phase": phase,
            "overall_status": overall_status,
            "last_update": last_update,
            "summary": (
                (protocol.get("descriptionModule") or {}).get("briefSummary", "")
            ),
        }

        return RawItem(
            source=self.source_key,
            source_id=nct_id or f"ct-{title[:50]}",
            fetched_at=datetime.now(timezone.utc),
            published_at=pub,
            url=url,
            title=title,
            raw_payload=payload,
            content_hash=RawItem.make_content_hash(title, url, pub),
        )


def _ct_date_range(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%Y-%m-%d')},{end.strftime('%Y-%m-%d')}"
