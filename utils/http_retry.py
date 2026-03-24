"""
HTTP retry helper — exponential backoff for transient network failures.

All data-source modules should use `resilient_get()` instead of bare
`requests.get()` so that flaky feeds / APIs don't crash the pipeline
on the first timeout.

Strategy:
    • 3 attempts by default (1 initial + 2 retries)
    • Exponential backoff: 1s → 2s → 4s (base * 2^attempt)
    • Only retries on transient errors: Timeout, ConnectionError, 5xx
    • Non-retryable errors (404, 403, etc.) propagate immediately
"""

from __future__ import annotations

import logging
import time
import requests
from requests.exceptions import ConnectionError, Timeout

logger = logging.getLogger(__name__)

# Status codes worth retrying (server-side transient failures)
_RETRYABLE_STATUS = {500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526}


def resilient_get(
    url: str,
    *,
    timeout: int = 15,
    max_retries: int = 2,
    backoff_base: float = 1.0,
    headers: dict | None = None,
    label: str = "",
    **kwargs,
) -> requests.Response:
    """
    GET with exponential-backoff retry for transient failures.

    Args:
        url:          Target URL.
        timeout:      Per-request timeout in seconds.
        max_retries:  Number of *retries* (total attempts = max_retries + 1).
        backoff_base: Base delay in seconds (doubles each retry).
        headers:      Optional request headers.
        label:        Human-readable name for log messages (e.g. "CNBC Top News").
        **kwargs:     Extra keyword args passed to requests.get (e.g. params).

    Returns:
        requests.Response on success.

    Raises:
        requests.HTTPError    on non-retryable HTTP errors (4xx).
        requests.Timeout      after all retries are exhausted.
        requests.ConnectionError  after all retries are exhausted.
    """
    tag = label or url[:60]
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers, **kwargs)

            # Non-retryable client errors → raise immediately
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()

            # Retryable server errors
            if resp.status_code in _RETRYABLE_STATUS:
                raise requests.HTTPError(
                    f"{resp.status_code} Server Error", response=resp
                )

            return resp  # ← Success

        except (Timeout, ConnectionError, requests.HTTPError) as exc:
            # Non-retryable client errors (4xx) → propagate immediately
            if (
                isinstance(exc, requests.HTTPError)
                and exc.response is not None
                and 400 <= exc.response.status_code < 500
            ):
                raise

            last_exc = exc
            if attempt < max_retries:
                delay = backoff_base * (2 ** attempt)
                logger.warning(
                    "%s: attempt %d/%d failed (%s) — retrying in %.1fs",
                    tag, attempt + 1, max_retries + 1, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "%s: all %d attempts exhausted (%s)",
                    tag, max_retries + 1, exc,
                )

    # All retries exhausted — propagate the last exception
    raise last_exc  # type: ignore[misc]
