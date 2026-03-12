from __future__ import annotations

import json
from pathlib import Path

import pytest

from genealogy_tree.lineage import load_checkpoint
from genealogy_tree.models import GraphResult


def _minimal_graph_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "generator_version": "1.0.0",
        "start_id": "1",
        "nodes": {
            "1": {
                "id": "1",
                "name": "Root",
                "url": "https://example.test/1",
                "degrees": [
                    {
                        "degree_type": "Ph.D.",
                        "institutions": [
                            {
                                "name_raw": "Demo U",
                                "countries_raw": ["DemoLand"],
                                "country_raw_primary": "DemoLand",
                            }
                        ],
                        "year": {"kind": "years", "values": [2001]},
                        "year_text": "2001",
                        "dissertation": "Demo",
                        "advisors": [
                            {"name": "Advisor", "id": "2", "href_raw": "id.php?id=2"}
                        ],
                    }
                ],
                "source_snapshot": "data/snapshots/1.html",
                "parse_warnings": [],
            },
            "2": {
                "id": "2",
                "name": "Advisor",
                "url": "https://example.test/2",
                "degrees": [],
                "source_snapshot": "data/snapshots/2.html",
                "parse_warnings": [],
            },
        },
        "edges": [
            {
                "relation_kind": "advisor",
                "from_person_id": "1",
                "to_person_id": "2",
                "relation_slot": 1,
                "relation_name_raw": "Advisor",
                "from_degree_index": 0,
                "href_raw": "id.php?id=2",
                "institution_raw": "",
                "year": {"kind": "unknown"},
                "year_text": "",
            }
        ],
        "visit_order": ["1", "2"],
        "stats": {"visited_nodes": 2, "edge_count": 1},
        "warnings": [],
        "config": {},
    }


def _checkpoint_payload_from_graph(
    graph_payload: dict[str, object],
) -> dict[str, object]:
    return {
        **graph_payload,
        "open_stack": [],
        "visited_ids": ["1", "2"],
        "complete": True,
        "updated_at_utc": "2026-03-11T00:00:00+00:00",
    }


def test_graph_from_dict_rejects_legacy_edge_keys():
    payload = _minimal_graph_payload()
    edge = payload["edges"][0]
    assert isinstance(edge, dict)
    edge["to_advisor_id"] = "2"

    with pytest.raises(ValueError, match="legacy keys"):
        _ = GraphResult.from_dict(payload)


def test_graph_from_dict_rejects_legacy_year_kind():
    payload = _minimal_graph_payload()
    node = payload["nodes"]["1"]
    assert isinstance(node, dict)
    degree = node["degrees"][0]
    assert isinstance(degree, dict)
    degree["year"] = {"kind": "year", "value": 2001}

    with pytest.raises(ValueError, match="\\.kind must be one of"):
        _ = GraphResult.from_dict(payload)


def test_graph_from_dict_rejects_non_integer_year_values():
    payload = _minimal_graph_payload()
    node = payload["nodes"]["1"]
    assert isinstance(node, dict)
    degree = node["degrees"][0]
    assert isinstance(degree, dict)
    degree["year"] = {"kind": "years", "values": [2001, "2003"]}

    with pytest.raises(ValueError, match="values\\[1\\] must be an integer"):
        _ = GraphResult.from_dict(payload)


def test_load_checkpoint_rejects_legacy_year_kind(tmp_path: Path):
    graph_payload = _minimal_graph_payload()
    node = graph_payload["nodes"]["1"]
    assert isinstance(node, dict)
    degree = node["degrees"][0]
    assert isinstance(degree, dict)
    degree["year"] = {"kind": "year", "value": 2001}
    checkpoint = _checkpoint_payload_from_graph(graph_payload)

    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

    with pytest.raises(ValueError, match="\\.kind must be one of"):
        _ = load_checkpoint(checkpoint_path)
