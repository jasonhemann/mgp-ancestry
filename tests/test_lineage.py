from __future__ import annotations

from pathlib import Path

from genealogy_tree.lineage import TraversalConfig, build_advisor_graph, load_checkpoint
from genealogy_tree.models import (
    AdvisorRef,
    DegreeRecord,
    InstitutionRecord,
    PersonRecord,
    year_many,
)


def _person(person_id: str, name: str, advisor_ids: list[str]) -> PersonRecord:
    advisors = [
        AdvisorRef(
            name=f"A{advisor_id}", id=advisor_id, href_raw=f"id.php?id={advisor_id}"
        )
        for advisor_id in advisor_ids
    ]
    degree = DegreeRecord(
        degree_type="Ph.D.",
        institutions=[
            InstitutionRecord(name_raw="Test University", countries_raw=["Testland"])
        ],
        year_value=year_many([2000]),
        year_text="2000",
        dissertation="Test",
        advisors=advisors,
    )
    return PersonRecord(
        id=person_id,
        name=name,
        url=f"https://example.test/{person_id}",
        degrees=[degree],
    )


def _build_people() -> dict[str, PersonRecord]:
    return {
        "1": _person("1", "Root", ["2", "3"]),
        "2": _person("2", "Left", ["4"]),
        "3": _person("3", "Right", ["4"]),
        "4": _person("4", "Shared", []),
    }


def test_dfs_dag_dedup():
    people = _build_people()

    def loader(person_id: str) -> PersonRecord:
        return people[person_id]

    graph = build_advisor_graph(
        "1", loader, config=TraversalConfig(max_depth=10, max_nodes=10)
    )
    payload = graph.to_dict()

    assert payload["visit_order"] == ["1", "2", "4", "3"]
    assert payload["stats"]["visited_nodes"] == 4
    assert payload["stats"]["edge_count"] == 4
    assert payload["stats"]["revisited_skips"] == 1


def test_depth_limit():
    people = _build_people()

    graph = build_advisor_graph(
        "1",
        lambda person_id: people[person_id],
        config=TraversalConfig(max_depth=1, max_nodes=20),
    )
    payload = graph.to_dict()
    assert set(payload["nodes"].keys()) == {"1", "2", "3"}


def test_stop_id():
    people = _build_people()
    graph = build_advisor_graph(
        "1",
        lambda person_id: people[person_id],
        config=TraversalConfig(max_depth=10, max_nodes=20, stop_ids={"2"}),
    )
    payload = graph.to_dict()
    # 2 is loaded but its advisors are not expanded.
    assert set(payload["nodes"].keys()) == {"1", "2", "3", "4"}
    assert payload["stats"]["stoplist_hits"] == 1


def test_max_nodes_cap():
    people = _build_people()
    graph = build_advisor_graph(
        "1",
        lambda person_id: people[person_id],
        config=TraversalConfig(max_depth=10, max_nodes=2),
    )
    payload = graph.to_dict()
    assert len(payload["nodes"]) == 2
    assert payload["stats"]["max_nodes_hits"] == 1


def test_checkpoint_resume_roundtrip(tmp_path: Path):
    people = {
        "1": _person("1", "P1", ["2"]),
        "2": _person("2", "P2", ["3"]),
        "3": _person("3", "P3", ["4"]),
        "4": _person("4", "P4", []),
    }
    checkpoint = tmp_path / "checkpoint.json"

    first = build_advisor_graph(
        "1",
        lambda person_id: people[person_id],
        config=TraversalConfig(max_depth=10, max_nodes=2),
        checkpoint_path=checkpoint,
    )
    assert first.stats["visited_nodes"] == 2
    saved = load_checkpoint(checkpoint)
    assert saved["complete"] is False
    assert saved["open_stack"]

    resumed = build_advisor_graph(
        "1",
        lambda person_id: people[person_id],
        config=TraversalConfig(max_depth=10, max_nodes=10),
        resume_state=saved,
        checkpoint_path=checkpoint,
    )
    payload = resumed.to_dict()
    assert payload["stats"]["visited_nodes"] == 4
    assert set(payload["nodes"].keys()) == {"1", "2", "3", "4"}
