from __future__ import annotations

import csv
from pathlib import Path
from xml.etree import ElementTree as ET

from genealogy_tree.models import (
    AdvisorRef,
    DegreeRecord,
    EdgeRecord,
    GraphResult,
    InstitutionRecord,
    PersonRecord,
    year_many,
    year_unknown,
)
from genealogy_tree.writers import write_gephi_exports

GEXF_NS = {"g": "http://www.gexf.net/1.2draft"}


def _person(person_id: str, name: str, year: int) -> PersonRecord:
    return PersonRecord(
        id=person_id,
        name=name,
        url=f"https://example.test/{person_id}",
        degrees=[
            DegreeRecord(
                degree_type="Ph.D.",
                institutions=[InstitutionRecord(name_raw="Demo University", countries_raw=["DemoLand"])],
                year_value=year_many([year]),
                year_text=str(year),
                dissertation="Demo thesis",
                advisors=[AdvisorRef(name="Unknown", id=None, href_raw="")],
            )
        ],
    )


def test_write_gephi_exports_files(tmp_path: Path):
    graph = GraphResult(
        start_id="1",
        nodes={
            "1": _person("1", "Root", 2001),
            "2": _person("2", "Advisor", 1980),
        },
        edges=[
            EdgeRecord(
                relation_kind="advisor",
                from_person_id="1",
                to_person_id="2",
                relation_slot=1,
                relation_name_raw="Advisor",
                from_degree_index=0,
                year_value=year_unknown(),
            ),
            EdgeRecord(
                relation_kind="advisor",
                from_person_id="1",
                to_person_id=None,
                relation_slot=2,
                relation_name_raw="Unknown Advisor",
                from_degree_index=0,
                year_value=year_unknown(),
            ),
        ],
        visit_order=["1", "2"],
        stats={"visited_nodes": 2, "edge_count": 2, "advisor_edge_count": 2},
        warnings=[],
        config={},
    )

    result = write_gephi_exports(graph, tmp_path, prefix="demo")

    assert result.nodes_csv_path.exists()
    assert result.edges_csv_path.exists()
    assert result.gexf_path.exists()
    assert result.node_count == 2
    assert result.edge_count == 1
    assert result.unresolved_edge_count == 1

    with result.nodes_csv_path.open("r", encoding="utf-8", newline="") as handle:
        node_rows = list(csv.DictReader(handle))
    assert len(node_rows) == 2
    root_row = next(row for row in node_rows if row["id"] == "1")
    assert root_row["is_start"] == "1"
    assert root_row["depth"] == "0"
    assert root_row["earliest_degree_year"] == "2001"
    assert root_row["century"] == "21st"

    with result.edges_csv_path.open("r", encoding="utf-8", newline="") as handle:
        edge_rows = list(csv.DictReader(handle))
    assert len(edge_rows) == 1
    assert edge_rows[0]["source"] == "1"
    assert edge_rows[0]["target"] == "2"

    gexf_tree = ET.parse(result.gexf_path)
    node_elements = gexf_tree.findall(".//g:nodes/g:node", GEXF_NS)
    edge_elements = gexf_tree.findall(".//g:edges/g:edge", GEXF_NS)
    assert len(node_elements) == 2
    assert len(edge_elements) == 1
