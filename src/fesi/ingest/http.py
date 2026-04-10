"""Shared httpx client + retry + rate-limit primitives for ingest adapters.

All adapters MUST go through this module so we have a consistent User-Agent
(required by SEC EDGAR), consistent retry behavior, and per-source rate limits.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from fesi.logging import get_logger

log = get_logger(__name__)

# SEC EDGAR requires a User-Agent with contact info. We use this everywhere
# for consistency.
USER_AGENT = "FESI/0.0.1 (personal-research; contact: fesi@example.com)"


class RateLimiter:
    """Simple per-instance rate limiter (max N calls per minute)."""

    def __init__(self, per_minute: int):
        self.interval = 60.0 / max(1, per_minute)
        self._last = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._last + self.interval - now
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


def get_client(
    *, headers: dict[str, str] | None = None, timeout: float = 30.0
) -> httpx.Client:
    """Return a configured httpx.Client. Caller is responsible for closing it."""
    base_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/xml, application/xml, */*",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        base_headers.update(headers)
    return httpx.Client(
        headers=base_headers,
        timeout=timeout,
        follow_redirects=True,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def fetch_json(
    client: httpx.Client, url: str, *, params: dict[str, Any] | None = None
) -> Any:
    log.debug("http_get_json", url=url, params=params)
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def fetch_text(
    client: httpx.Client, url: str, *, params: dict[str, Any] | None = None
) -> str:
    log.debug("http_get_text", url=url, params=params)
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.text


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def post_json(
    client: httpx.Client, url: str, *, json_body: dict[str, Any]
) -> Any:
    """POST JSON and return parsed response. Longer backoff for LLM APIs."""
    log.debug("http_post_json", url=url)
    response = client.post(url, json=json_body)
    response.raise_for_status()
    return response.json()
