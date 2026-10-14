"""Low-level HTTP client for the NHL API with retries and logging.

The NHL does not publish an official, documented public API. The
endpoints used in this project were identified by inspecting real
responses directly (see scripts/explore_api.py) and cross-referencing
the community-maintained Zmalski NHL API reference. Because it's
unofficial, treat field names as *observed*, not guaranteed -- if the
NHL changes something, calls here should fail loudly (raise
NHLApiError) rather than silently returning wrong or empty data.
"""

import time
from typing import Any

import requests

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class NHLApiError(Exception):
    """Raised when an NHL API request fails after all retries, or
    returns a response that cannot be parsed as JSON."""


def get_json(
    url: str,
    *,
    timeout: int = 10,
    max_retries: int = 3,
    backoff_seconds: float = 1.5,
    rate_limit_retries: int = 6,
    rate_limit_wait_seconds: float = 10.0,
) -> dict[str, Any]:
    """Fetch JSON from a URL with retries and clear failure logging.

    Args:
        url: Full URL to request.
        timeout: Per-request timeout in seconds.
        max_retries: Number of attempts before giving up.
        backoff_seconds: Base delay between retries; grows linearly
            with attempt number to back off gracefully.
        rate_limit_retries: How many times to wait out a 429 (rate limited)
            response; these don't count against max_retries.
        rate_limit_wait_seconds: Base wait after a 429 when the response has
            no Retry-After header; grows with each 429.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        NHLApiError: If the request fails on all attempts, or the
            response body is not valid JSON.
    """
    last_error: Exception | None = None
    rate_limited = 0
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            response = requests.get(url, timeout=timeout)
            # 429 Too Many Requests: the API is throttling us, not failing.
            # Wait it out (Retry-After if given, else a growing pause) without
            # using up a normal retry -- observed 2026-10-13 after ~100 quick
            # api-web requests; before this, whole teams were silently skipped.
            if response.status_code == 429 and rate_limited < rate_limit_retries:
                rate_limited += 1
                retry_after = response.headers.get("Retry-After", "")
                wait = float(retry_after) if retry_after.isdigit() else rate_limit_wait_seconds * rate_limited
                logger.warning("Rate limited (429) on %s -- waiting %.0fs (%d/%d).",
                               url, wait, rate_limited, rate_limit_retries)
                time.sleep(wait)
                attempt -= 1
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "Request failed (attempt %d/%d) for %s: %s",
                attempt, max_retries, url, exc,
            )
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)
        except ValueError as exc:  # JSON decoding error
            raise NHLApiError(f"Invalid JSON from {url}: {exc}") from exc

    raise NHLApiError(
        f"Failed to fetch {url} after {max_retries} attempts: {last_error}"
    )
