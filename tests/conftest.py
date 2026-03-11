from __future__ import annotations

from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "mgp"


@pytest.fixture
def load_fixture_html(fixture_dir: Path):
    def _load(person_id: str) -> str:
        return (fixture_dir / f"{person_id}.html").read_text(encoding="utf-8")

    return _load
