"""FDA OpenFDA ingestion adapter.

Pulls recent drug application submissions and approvals from the openFDA
drugsfda endpoint. Free, no API key required.

API docs: https://open.fda.gov/apis/drug/drugsfda/

We query the `submissions` endpoint with a date range filter on
`submissions.submission_status_date` for the last N days.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fesi.ingest.base import IngestAdapter, RawItem
from fesi.ingest.http import RateLimiter, fetch_json, get_client
from fesi.logging import get_logger

log = get_logger(__name__)

OPENFDA_URL = "https://api.fda.gov/drug/drugsfda.json"
PAGE_LIMIT = 100


class FdaOpenfdaAdapter(IngestAdapter):
    """FDA drug application submissions / approvals."""

    source_key = "fda_openfda"

    def __init__(self, *, lookback_hours: int = 48):
        self.lookback_hours = lookback_hours
        self.rate_limiter = RateLimiter(per_minute=240)
        self.client = get_client()

    def fetch(self) -> list[RawItem]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=self.lookback_hours)
        # OpenFDA uses YYYYMMDD format in date range queries
        date_range = f"[{start.strftime('%Y%m%d')}+TO+{end.strftime('%Y%m%d')}]"
        query = f"submissions.submission_status_date:{date_range}"

        items: list[RawItem] = []
        try:
            self.rate_limiter.wait()
            data = fetch_json(
                self.client,
                OPENFDA_URL,
                params={"search": query, "limit": PAGE_LIMIT},
            )
        except Exception as e:
            log.warning("openfda_fetch_failed", error=str(e))
            return items

        results = data.get("results", []) or []
        for entry in results:
            for submission in entry.get("submissions", []) or []:
                if not _date_in_range(
                    submission.get("submission_status_date"), start, end
                ):
                    continue
                item = self._build_item(entry, submission)
                if item:
                    items.append(item)

        log.info("fda_openfda_fetch_done", items=len(items))
        return items

    def _build_item(self, entry: dict, submission: dict) -> RawItem | None:
        application_number = entry.get("application_number")
        sponsor = entry.get("sponsor_name", "")
        products = entry.get("products", []) or []
        first_brand = ""
        first_active = ""
        if products:
            first_brand = products[0].get("brand_name", "") or ""
            active_ingredients = products[0].get("active_ingredients", []) or []
            if active_ingredients:
                first_active = active_ingredients[0].get("name", "") or ""

        sub_type = submission.get("submission_type", "")
        sub_status = submission.get("submission_status", "")
        sub_date = submission.get("submission_status_date", "")

        title_parts = [sponsor, first_brand or first_active, sub_type, sub_status]
        title = " — ".join(p for p in title_parts if p)
        if not title:
            return None

        url = (
            f"https://www.accessdata.fda.gov/scripts/cder/daf/"
            f"index.cfm?event=overview.process&ApplNo={application_number}"
            if application_number
            else None
        )

        try:
            pub = datetime.strptime(sub_date, "%Y%m%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pub = None

        payload = {
            "application_number": application_number,
            "sponsor": sponsor,
            "brand_name": first_brand,
            "active_ingredient": first_active,
            "submission_type": sub_type,
            "submission_status": sub_status,
            "submission_status_date": sub_date,
            "products": products,
            "submission": submission,
        }

        source_id = f"{application_number}-{sub_type}-{sub_date}"

        return RawItem(
            source=self.source_key,
            source_id=source_id,
            fetched_at=datetime.now(timezone.utc),
            published_at=pub,
            url=url,
            title=title,
            raw_payload=payload,
            content_hash=RawItem.make_content_hash(title, url, pub),
        )


def _date_in_range(
    yyyymmdd: str | None, start: datetime, end: datetime
) -> bool:
    if not yyyymmdd:
        return False
    try:
        d = datetime.strptime(yyyymmdd, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return start <= d <= end
