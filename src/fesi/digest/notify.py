"""Notification delivery — Pushover (push) + Telegram (digest) + always-on file.

Each channel degrades independently:
  - File output: ALWAYS works, writes to logs/digests/YYYY-MM-DD-HHMM.md
  - Pushover: works only if PUSHOVER_USER_KEY + PUSHOVER_APP_TOKEN are set
  - Telegram: works only if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set

A failure in one channel never blocks the others.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx

from fesi.config import get_settings
from fesi.logging import get_logger

log = get_logger(__name__)

LOGS_DIR = Path("logs/digests")


def deliver_digest(
    markdown: str,
    *,
    silent: bool = False,
    title: str = "FESI Digest",
) -> dict:
    """Push the digest through every configured channel. Returns per-channel status."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    results: dict[str, str] = {}

    # ---- File (always) ----
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    fpath = LOGS_DIR / f"{ts}.md"
    fpath.write_text(markdown)
    results["file"] = str(fpath)
    log.info("digest_written_to_file", path=str(fpath))

    # ---- Pushover (if configured) ----
    if settings.pushover_user_key and settings.pushover_app_token:
        try:
            short = _truncate_for_push(markdown)
            r = httpx.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": settings.pushover_app_token,
                    "user": settings.pushover_user_key,
                    "title": title,
                    "message": short,
                    "html": 0,
                    "priority": -1 if silent else 0,
                    "sound": "none" if silent else "pushover",
                },
                timeout=15.0,
            )
            r.raise_for_status()
            results["pushover"] = "ok"
            log.info("digest_sent_pushover")
        except Exception as e:
            results["pushover"] = f"error: {e}"
            log.warning("pushover_failed", error=str(e))
    else:
        results["pushover"] = "skipped: no credentials"

    # ---- Telegram (if configured) ----
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            r = httpx.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": markdown[:4000],
                    "parse_mode": "Markdown",
                    "disable_notification": silent,
                },
                timeout=15.0,
            )
            r.raise_for_status()
            results["telegram"] = "ok"
            log.info("digest_sent_telegram")
        except Exception as e:
            results["telegram"] = f"error: {e}"
            log.warning("telegram_failed", error=str(e))
    else:
        results["telegram"] = "skipped: no credentials"

    return results


def push_urgent_alert(
    *, ticker: str, headline: str, conviction: float
) -> dict:
    """Send a single high-priority push for a high-conviction watchlist hit."""
    settings = get_settings()
    results: dict[str, str] = {}

    if settings.pushover_user_key and settings.pushover_app_token:
        try:
            r = httpx.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": settings.pushover_app_token,
                    "user": settings.pushover_user_key,
                    "title": f"FESI ALERT: {ticker} (conviction {conviction:.1f})",
                    "message": headline[:1024],
                    "priority": 1,
                    "sound": "siren",
                },
                timeout=15.0,
            )
            r.raise_for_status()
            results["pushover"] = "ok"
        except Exception as e:
            results["pushover"] = f"error: {e}"
            log.warning("urgent_pushover_failed", error=str(e))
    else:
        results["pushover"] = "skipped: no credentials"

    return results


def _truncate_for_push(markdown: str, max_chars: int = 1024) -> str:
    """Pushover messages are capped at ~1024 chars. Take the most useful slice."""
    if len(markdown) <= max_chars:
        return markdown
    head = markdown[:max_chars - 30]
    return head + "\n\n[... truncated]"
