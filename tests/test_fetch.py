from __future__ import annotations

from dataclasses import dataclass

import pytest

from genealogy_tree.fetch import fetch_with_retries


@dataclass(slots=True)
class FakeResponse:
    status_code: int
    text: str
    url: str = "https://example.test"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP error: {self.status_code}")


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self._responses: list[FakeResponse | Exception] = list(responses)
        self.calls: int = 0

    def get(
        self,
        url: str | bytes,
        *,
        timeout: float | tuple[float, float] | None = None,
    ) -> FakeResponse:
        _ = (url, timeout)
        self.calls += 1
        response: FakeResponse | Exception = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_retry_on_http_500_then_success() -> None:
    session = FakeSession(
        [
            FakeResponse(500, "server down"),
            FakeResponse(200, "ok"),
        ]
    )
    result = fetch_with_retries(
        "https://example.test/id.php?id=1",
        max_attempts=3,
        session=session,
        sleep_fn=lambda _: None,
    )
    assert result.status_code == 200
    assert session.calls == 2


def test_retry_on_mdb2_marker_then_success() -> None:
    session = FakeSession(
        [
            FakeResponse(200, "MDB2 Error: connect failed"),
            FakeResponse(200, "real payload"),
        ]
    )
    result = fetch_with_retries(
        "https://example.test/id.php?id=1",
        max_attempts=3,
        session=session,
        sleep_fn=lambda _: None,
    )
    assert result.text == "real payload"
    assert session.calls == 2


def test_raises_after_retries_exhausted() -> None:
    session = FakeSession([FakeResponse(503, "down"), FakeResponse(503, "still down")])
    with pytest.raises(RuntimeError):
        _ = fetch_with_retries(
            "https://example.test/id.php?id=1",
            max_attempts=2,
            session=session,
            sleep_fn=lambda _: None,
        )
