from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import random
import time
from typing import Protocol

import requests

MGP_RETRY_BODY_MARKER = "mdb2 error: connect failed"


@dataclass(slots=True)
class FetchResult:
    text: str
    status_code: int
    url: str


class RetryableFetchError(RuntimeError):
    pass


class ResponseLike(Protocol):
    status_code: int

    @property
    def text(self) -> str: ...

    @property
    def url(self) -> str: ...

    def raise_for_status(self) -> None: ...


class SessionLike(Protocol):
    def get(
        self,
        url: str | bytes,
        *,
        timeout: float | tuple[float, float] | None = None,
    ) -> ResponseLike: ...


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _compute_backoff_seconds(
    attempt_number: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_fraction: float = 0.25,
) -> float:
    exponent = attempt_number - 1
    if exponent < 0:
        exponent = 0
    retry_multiplier = 1 << exponent
    unclamped_delay = base_delay_seconds * float(retry_multiplier)
    raw_delay = unclamped_delay if unclamped_delay < max_delay_seconds else max_delay_seconds
    jitter = raw_delay * jitter_fraction * random.random()
    return raw_delay + jitter


def fetch_with_retries(
    url: str,
    *,
    timeout_seconds: float = 20.0,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 30.0,
    session: SessionLike | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> FetchResult:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    requests_session: SessionLike = requests.Session() if session is None else session
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response: ResponseLike = requests_session.get(url, timeout=timeout_seconds)
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
