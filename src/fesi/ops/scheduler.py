"""APScheduler — runs the pipeline 5x/day in UAE timezone.

Schedule (Asia/Dubai):
  15:00 — pre-US-market open       (alert sound ON)
  18:00 — post-US-open              (alert sound ON)
  22:00 — mid-US-session            (silent)
  02:00 — post-US-close + filings   (silent)
  08:00 — morning catch-up          (alert sound ON)

Outcomes job runs daily at 09:00 UAE (after US close has settled).
"""
from __future__ import annotations

import signal
import sys
import time
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from fesi.config import get_settings
from fesi.db import connect
from fesi.logging import get_logger, setup_logging
from fesi.ops.pipeline import run_pipeline
from fesi.store.outcomes import update_all_outcomes

log = get_logger(__name__)

UAE_TZ = pytz.timezone("Asia/Dubai")


# (hour, minute, silent_alerts, label)
SCAN_SCHEDULE: list[tuple[int, int, bool, str]] = [
    (15, 0, False, "pre_market"),
    (18, 0, False, "post_open"),
    (22, 0, True, "mid_session"),
    (2, 0, True, "post_close"),
    (8, 0, False, "morning_catchup"),
]


def _scan_job(silent: bool, label: str):
    log.info("scheduled_scan_start", label=label, silent=silent)
    try:
        stats = run_pipeline(silent_alerts=silent, run_label=label)
        log.info(
            "scheduled_scan_done",
            label=label,
            signals=stats.signals_created,
            buys=stats.decisions_buy,
            errors=len(stats.errors),
        )
    except Exception:
        log.exception("scheduled_scan_failed", label=label)


def _outcomes_job():
    log.info("outcomes_job_start")
    try:
        with connect() as conn:
            result = update_all_outcomes(conn)
        log.info("outcomes_job_done", **result)
    except Exception:
        log.exception("outcomes_job_failed")


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=UAE_TZ)

    for hour, minute, silent, label in SCAN_SCHEDULE:
        scheduler.add_job(
            _scan_job,
            CronTrigger(hour=hour, minute=minute, timezone=UAE_TZ),
            kwargs={"silent": silent, "label": label},
            id=f"scan_{label}",
            misfire_grace_time=600,
            coalesce=True,
        )
        log.info("scan_job_registered", label=label, hour=hour, minute=minute)

    scheduler.add_job(
        _outcomes_job,
        CronTrigger(hour=9, minute=0, timezone=UAE_TZ),
        id="outcomes_daily",
        misfire_grace_time=3600,
        coalesce=True,
    )
    log.info("outcomes_job_registered")

    return scheduler


def run_forever() -> None:
    setup_logging("INFO")
    settings = get_settings()
    log.info(
        "scheduler_starting",
        mode=settings.mode,
        env=settings.environment,
        tz="Asia/Dubai",
    )

    scheduler = build_scheduler()
    scheduler.start()

    # Print next run times
    for job in scheduler.get_jobs():
        log.info("scheduled", job_id=job.id, next_run=str(job.next_run_time))

    # Block forever
    def _stop(signum, frame):
        log.info("scheduler_shutdown_requested", signal=signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while True:
        time.sleep(60)
