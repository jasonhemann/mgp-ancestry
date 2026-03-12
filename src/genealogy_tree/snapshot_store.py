from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from collections.abc import Callable
from typing import cast

import requests

from .fetch import FetchResult, fetch_with_retries
from .models import PARSER_VERSION

BASE_MGP_ID_URL = "https://genealogy.math.ndsu.nodak.edu/id.php?id="


@dataclass(slots=True)
class SnapshotRecord:
    id: str
    url: str
    html: str
    html_path: Path
    meta_path: Path
    meta: dict[str, object]


class SnapshotStore:
    def __init__(
        self,
        snapshot_dir: str | Path,
        *,
        crawl_delay_seconds: float = 10.0,
        parser_version: str = PARSER_VERSION,
        timeout_seconds: float = 20.0,
        session: requests.Session | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.snapshot_dir: Path = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.crawl_delay_seconds: float = crawl_delay_seconds
        self.parser_version: str = parser_version
        self.timeout_seconds: float = timeout_seconds
        self.session: requests.Session = session or requests.Session()
        self.sleep_fn: Callable[[float], None] = sleep_fn
        self.monotonic_fn: Callable[[], float] = monotonic_fn
        self._last_fetch_monotonic: float | None = None

    def _paths_for_id(self, person_id: str) -> tuple[Path, Path]:
        html_path = self.snapshot_dir / f"{person_id}.html"
        meta_path = self.snapshot_dir / f"{person_id}.meta.json"
        return html_path, meta_path

    def has_snapshot(self, person_id: str) -> bool:
        html_path, meta_path = self._paths_for_id(person_id)
        return html_path.exists() and meta_path.exists()

    def load_snapshot(self, person_id: str) -> SnapshotRecord:
        html_path, meta_path = self._paths_for_id(person_id)
        html = html_path.read_text(encoding="utf-8")
        raw_meta_obj = cast(object, json.loads(meta_path.read_text(encoding="utf-8")))
        meta: dict[str, object] = {}
        if isinstance(raw_meta_obj, dict):
            for key, value in cast(dict[object, object], raw_meta_obj).items():
                meta[str(key)] = value
        url_value = meta.get("url")
        url = (
            str(url_value) if url_value is not None else f"{BASE_MGP_ID_URL}{person_id}"
        )
        return SnapshotRecord(
            id=str(person_id),
            url=url,
            html=html,
            html_path=html_path,
            meta_path=meta_path,
            meta=meta,
        )

    def get_snapshot(self, person_id: str, *, refresh: bool = False) -> SnapshotRecord:
        person_id = str(person_id)
        if self.has_snapshot(person_id) and not refresh:
            return self.load_snapshot(person_id)
        return self._fetch_and_store(person_id)

    def _enforce_crawl_delay(self) -> None:
        if self._last_fetch_monotonic is None:
            return
        elapsed = self.monotonic_fn() - self._last_fetch_monotonic
        if elapsed < self.crawl_delay_seconds:
            self.sleep_fn(self.crawl_delay_seconds - elapsed)

    def _fetch_and_store(self, person_id: str) -> SnapshotRecord:
        self._enforce_crawl_delay()
        url = f"{BASE_MGP_ID_URL}{person_id}"
        fetch_result: FetchResult = fetch_with_retries(
            url,
            timeout_seconds=self.timeout_seconds,
            session=self.session,
            sleep_fn=self.sleep_fn,
        )
        self._last_fetch_monotonic = self.monotonic_fn()

        html_path, meta_path = self._paths_for_id(person_id)
        _ = html_path.write_text(fetch_result.text, encoding="utf-8")

        digest = sha256(fetch_result.text.encode("utf-8")).hexdigest()
        fetched_at_utc = datetime.now(timezone.utc).isoformat()
        meta: dict[str, object] = {
            "id": str(person_id),
            "url": fetch_result.url,
            "fetched_at_utc": fetched_at_utc,
            "sha256": digest,
            "http_status": fetch_result.status_code,
            "content_length": len(fetch_result.text),
            "parser_version": self.parser_version,
        }
        _ = meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return SnapshotRecord(
            id=str(person_id),
            url=fetch_result.url,
            html=fetch_result.text,
            html_path=html_path,
            meta_path=meta_path,
            meta=meta,
        )
