from __future__ import annotations

import json

from genealogy_tree.lineage import TraversalConfig, build_advisor_graph
from genealogy_tree.models import (
    AdvisorRef,
    DegreeRecord,
    EdgeRecord,
    GraphResult,
    InstitutionRecord,
    PersonRecord,
    year_raw,
    year_single,
)
from genealogy_tree.writers import render_markdown_lineage, write_graph_json, write_markdown_lineage


def _person(person_id: str, name: str, advisor_ids: list[str]) -> PersonRecord:
    advisors = [AdvisorRef(name=f"A{advisor_id}", id=advisor_id, href_raw=f"id.php?id={advisor_id}") for advisor_id in advisor_ids]
    degree = DegreeRecord(
        degree_type="Ph.D.",
        institutions=[InstitutionRecord(name_raw="Test University", countries_raw=["Testland"])],
        year_value=year_single(2000),
        year_text="2000",
        dissertation="Test",
        advisors=advisors,
    )
    return PersonRecord(id=person_id, name=name, url=f"https://example.test/{person_id}", degrees=[degree])


def test_json_writer_contract(tmp_path):
    people = {
        "1": _person("1", "Root", ["2"]),
        "2": _person("2", "Advisor", []),
    }
    graph = build_advisor_graph("1", lambda person_id: people[person_id], config=TraversalConfig(max_depth=5))
    out_path = tmp_path / "lineage_1.json"
    write_graph_json(graph, out_path)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    assert payload["generator_version"]
    assert payload["start_id"] == "1"
    assert "nodes" in payload
    assert "edges" in payload
    assert "stats" in payload


def test_markdown_render_revisit_reference():
    people = {
        "1": _person("1", "Root", ["2", "3"]),
        "2": _person("2", "Left", []),
        "3": _person("3", "Right", ["2"]),
    }
    graph = build_advisor_graph("1", lambda person_id: people[person_id], config=TraversalConfig(max_depth=10))
    text = render_markdown_lineage(graph)
    assert "# Advisor Lineage for Root (1)" in text
    assert "[see above](#node-2)" in text


def test_markdown_render_unknown_and_unresolvable_paths(tmp_path):
    root = PersonRecord(
        id="1",
        name="Root",
        url="https://example.test/1",
        source_snapshot="/tmp/root.html",
        parse_warnings=[],
        degrees=[
            DegreeRecord(
                degree_type="Ph.D.",
                institutions=[InstitutionRecord(name_raw="Alpha", countries_raw=["X"])],
                year_value=year_raw("unknown-year"),
                year_text="unknown-year",
                dissertation="N/A",
                advisors=[AdvisorRef(name="Unknown", id=None, href_raw="")],
            )
        ],
    )
    graph = GraphResult(
        start_id="1",
        nodes={"1": root},
        edges=[
            EdgeRecord(
                from_person_id="1",
                to_advisor_id=None,
                from_degree_index=0,
                advisor_slot=1,
                advisor_name_raw="Unknown",
            ),
            EdgeRecord(
                from_person_id="1",
                to_advisor_id="999",
                from_degree_index=0,
                advisor_slot=2,
                advisor_name_raw="Missing",
            ),
        ],
        visit_order=["1"],
        stats={"visited_nodes": 1, "edge_count": 2, "revisited_skips": 0},
        warnings=["demo warning"],
        config={},
    )
    text = render_markdown_lineage(graph)
    assert "## Warnings" in text
    assert "demo warning" in text
    assert "Unknown node (999)" in text
    assert "unresolvable" in text

    md_path = tmp_path / "lineage_1.md"
    write_markdown_lineage(graph, md_path)
    assert md_path.exists()
