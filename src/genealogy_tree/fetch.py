from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import random
import time

import requests

MGP_RETRY_BODY_MARKER = "mdb2 error: connect failed"


@dataclass(slots=True)
class FetchResult:
    text: str
    status_code: int
    url: str


class RetryableFetchError(RuntimeError):
    pass


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _compute_backoff_seconds(
    attempt_number: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_fraction: float = 0.25,
) -> float:
    raw = min(max_delay_seconds, base_delay_seconds * (2 ** max(0, attempt_number - 1)))
    return raw + (raw * jitter_fraction * random.random())


def fetch_with_retries(
    url: str,
    *,
    timeout_seconds: float = 20.0,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 30.0,
    session: requests.Session | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> FetchResult:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    requests_session = session or requests.Session()
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests_session.get(url, timeout=timeout_seconds)
            text = response.text
            if _is_retryable_status(response.status_code):
                raise RetryableFetchError(f"Retryable status code {response.status_code} for {url}")
            if MGP_RETRY_BODY_MARKER in text.casefold():
                raise RetryableFetchError("MGP returned MDB2 transient connection error body marker")
            response.raise_for_status()
            return FetchResult(text=text, status_code=response.status_code, url=response.url)
        except (requests.RequestException, RetryableFetchError) as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            sleep_fn(
                _compute_backoff_seconds(
                    attempt,
                    base_delay_seconds=base_delay_seconds,
                    max_delay_seconds=max_delay_seconds,
                )
            )

    raise RuntimeError(f"Failed to fetch {url} after {max_attempts} attempts: {last_error}") from last_error
