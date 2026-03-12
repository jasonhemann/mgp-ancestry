from __future__ import annotations

from pathlib import Path

from genealogy_tree.fetch import FetchResult
from genealogy_tree.snapshot_store import SnapshotStore


def test_snapshot_store_caches_and_reuses(monkeypatch, tmp_path: Path):
    calls = {"count": 0}

    def fake_fetch(url: str, **kwargs):
        calls["count"] += 1
        return FetchResult(
            text=f"<html>{calls['count']}</html>", status_code=200, url=url
        )

    monkeypatch.setattr("genealogy_tree.snapshot_store.fetch_with_retries", fake_fetch)
    store = SnapshotStore(tmp_path / "snapshots", crawl_delay_seconds=0.0)

    first = store.get_snapshot("123", refresh=False)
    second = store.get_snapshot("123", refresh=False)
    third = store.get_snapshot("123", refresh=True)

    assert first.html == "<html>1</html>"
    assert second.html == "<html>1</html>"
    assert third.html == "<html>2</html>"
    assert calls["count"] == 2
    assert first.meta_path.exists()
    assert first.html_path.exists()
