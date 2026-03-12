from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "viz" / "graphviz" / "renderer" / "render_graphviz.py"


def _load_renderer_module():
    module_name = "viz_render_graphviz_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _lineage_fixture() -> dict:
    return {
        "start_id": "1",
        "nodes": {
            "1": {
                "id": "1",
                "name": "Root  Person",
                "url": "https://example.test/1",
                "degrees": [
                    {
                        "year": {"kind": "years", "values": [2000]},
                    }
                ],
            },
            "2": {
                "id": "2",
                "name": "Advisor A",
                "url": "https://example.test/2",
                "degrees": [
                    {
                        "year": {"kind": "years", "values": [1970]},
                    }
                ],
            },
            "3": {
                "id": "3",
                "name": "Advisor B",
                "url": "https://example.test/3",
                "degrees": [],
            },
        },
        "edges": [
            {
                "from_person_id": "1",
                "to_person_id": "2",
                "relation_name_raw": "Advisor A",
                "from_degree_index": 0,
            },
            {
                "from_person_id": "1",
                "to_person_id": "2",
                "relation_name_raw": "Advisor A",
                "from_degree_index": 1,
            },
            {
                "from_person_id": "1",
                "to_person_id": "3",
                "relation_name_raw": "Advisor B",
                "from_degree_index": 0,
            },
            {
                "from_person_id": "1",
                "to_person_id": None,
                "relation_name_raw": "Unknown",
                "from_degree_index": 2,
            },
        ],
    }


def test_collapse_edges_and_dot_contract():
    renderer = _load_renderer_module()
    payload = _lineage_fixture()

    resolved = renderer.normalize_resolved_edges(payload)
    collapsed = renderer.collapse_edges(resolved, collapse_parallel=True)
    depths = renderer.compute_depths(payload["start_id"], collapsed)
    dot_text = renderer.build_dot(payload, collapsed, depths, config={}, max_label_chars=40, include_year=True)

    assert len(resolved) == 3
    assert len(collapsed) == 2
    assert 'rankdir="BT"' in dot_text
    assert 'newrank="true"' in dot_text
    assert 'remincross="true"' in dot_text
    assert 'mclimit="10"' in dot_text
    assert dot_text.count('"1" -> "2"') == 1
    assert 'label="x2"' in dot_text
    assert 'label="Root Person (2000)"' in dot_text
    assert "\\\\n(2000)" not in dot_text
    assert "subgraph rank_depth_" not in dot_text


def test_renderer_script_smoke_svg(tmp_path: Path):
    if shutil.which("dot") is None:
        pytest.skip("Graphviz dot is not installed")

    input_path = tmp_path / "lineage_fixture.json"
    output_dir = tmp_path / "rendered"
    input_path.write_text(json.dumps(_lineage_fixture()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--format",
            "svg",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    dot_path = output_dir / "lineage_1.dot"
    svg_path = output_dir / "lineage_1.svg"
    assert dot_path.exists()
    assert svg_path.exists()
    assert 'rankdir="BT"' in dot_path.read_text(encoding="utf-8")
    assert "Summary:" in result.stdout
