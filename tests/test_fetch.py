from __future__ import annotations

import pytest

from genealogy_tree.fetch import fetch_with_retries


class FakeResponse:
    def __init__(self, status_code: int, text: str, url: str = "https://example.test") -> None:
        self.status_code = status_code
        self.text = text
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP error: {self.status_code}")


class FakeSession:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.calls = 0

    def get(self, url: str, timeout: float):
        self.calls += 1
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_retry_on_http_500_then_success():
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


def test_retry_on_mdb2_marker_then_success():
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


def test_raises_after_retries_exhausted():
    session = FakeSession([FakeResponse(503, "down"), FakeResponse(503, "still down")])
    with pytest.raises(RuntimeError):
        fetch_with_retries(
            "https://example.test/id.php?id=1",
            max_attempts=2,
            session=session,
            sleep_fn=lambda _: None,
        )

