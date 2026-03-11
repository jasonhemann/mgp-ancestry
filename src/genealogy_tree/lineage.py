from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from .models import (
    EdgeRecord,
    GENERATOR_VERSION,
    GraphResult,
    PersonRecord,
    SCHEMA_VERSION,
    normalize_person_name,
)


@dataclass(slots=True)
class TraversalConfig:
    max_depth: int | None = 20
    max_nodes: int | None = 500
    max_nodes_hard: int = 10000
    stop_ids: set[str] | None = None
    stop_names: set[str] | None = None
    exhaustive: bool = False
    direction: str = "advisor"

    def normalized_stop_ids(self) -> set[str]:
        return set(self.stop_ids or set())

    def normalized_stop_names(self) -> set[str]:
        return {normalize_person_name(name) for name in (self.stop_names or set())}

    def to_dict(self) -> dict:
        return {
            "max_depth": self.max_depth,
            "max_nodes": self.max_nodes,
            "max_nodes_hard": self.max_nodes_hard,
            "stop_ids": sorted(self.normalized_stop_ids()),
            "stop_names": sorted(self.normalized_stop_names()),
            "exhaustive": self.exhaustive,
            "direction": self.direction,
        }


def load_checkpoint(checkpoint_path: str | Path) -> dict:
    path = Path(checkpoint_path)
    return json.loads(path.read_text(encoding="utf-8"))


def _serialize_open_stack(stack: list[tuple[str, int]]) -> list[dict]:
    return [{"id": person_id, "depth": depth} for person_id, depth in stack]


def _deserialize_open_stack(payload: list[dict]) -> list[tuple[str, int]]:
    return [(str(item["id"]), int(item["depth"])) for item in payload]


def _write_checkpoint(
    checkpoint_path: Path,
    *,
    start_id: str,
    config: TraversalConfig,
    stack: list[tuple[str, int]],
    visited: set[str],
    nodes: dict[str, PersonRecord],
    edges: list[EdgeRecord],
    visit_order: list[str],
    stats: dict,
    warnings: list[str],
    complete: bool,
) -> None:
    checkpoint_payload = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "start_id": start_id,
        "config": config.to_dict(),
        "open_stack": _serialize_open_stack(stack),
        "visited_ids": sorted(visited),
        "nodes": {node_id: person.to_dict() for node_id, person in nodes.items()},
        "edges": [edge.to_dict() for edge in edges],
        "visit_order": list(visit_order),
        "stats": dict(stats),
        "warnings": list(warnings),
        "complete": complete,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(checkpoint_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _initialize_state(
    *,
    start_id_str: str,
    resume_state: dict | None,
    default_stats: dict,
) -> tuple[
    list[tuple[str, int]],
    set[str],
    dict[str, PersonRecord],
    list[EdgeRecord],
    list[str],
    list[str],
    dict,
]:
    if resume_state:
        stack = _deserialize_open_stack(resume_state.get("open_stack", []))
        if not stack:
            stack = [(start_id_str, 0)]
        visited = set(str(v) for v in resume_state.get("visited_ids", []))
        nodes = {
            str(node_id): PersonRecord.from_dict(node_payload)
            for node_id, node_payload in resume_state.get("nodes", {}).items()
        }
        edges = [EdgeRecord.from_dict(item) for item in resume_state.get("edges", [])]
        visit_order = [str(v) for v in resume_state.get("visit_order", [])]
        warnings = [str(v) for v in resume_state.get("warnings", [])]
        stats = dict(default_stats)
        stats.update(resume_state.get("stats", {}))
        if str(resume_state.get("start_id", start_id_str)) != start_id_str:
            warnings.append(
                "Resume checkpoint start_id mismatch with CLI start_id; continuing with CLI start_id."
            )
    else:
        stack = [(start_id_str, 0)]
        visited = set()
        nodes = {}
        edges = []
        visit_order = []
        warnings = []
        stats = dict(default_stats)
    return stack, visited, nodes, edges, visit_order, warnings, stats


def _preload_status(
    *,
    person_id: str,
    depth: int,
    visited: set[str],
    traversal_config: TraversalConfig,
    exhaustive: bool,
    stack: list[tuple[str, int]],
    stats: dict,
    warnings: list[str],
) -> str:
    if person_id in visited:
        stats["revisited_skips"] += 1
        return "skip"

    if len(visited) >= traversal_config.max_nodes_hard:
        stack.append((person_id, depth))
        warnings.append(f"Traversal stopped: reached max_nodes_hard={traversal_config.max_nodes_hard}.")
        stats["hard_cap_hits"] += 1
        return "stop"

    if not exhaustive and traversal_config.max_nodes is not None and len(visited) >= traversal_config.max_nodes:
        stack.append((person_id, depth))
        warnings.append(f"Traversal stopped: reached max_nodes={traversal_config.max_nodes}.")
        stats["max_nodes_hits"] += 1
        return "stop"

    if not exhaustive and traversal_config.max_depth is not None and depth > traversal_config.max_depth:
        stats["depth_limit_hits"] += 1
        return "skip"

    return "load"


def _collect_next_nodes(
    *,
    person: PersonRecord,
    person_id: str,
    depth: int,
    include_advisors: bool,
    include_students: bool,
    edges: list[EdgeRecord],
    stats: dict,
) -> list[tuple[str, int]]:
    next_nodes: list[tuple[str, int]] = []
    if include_advisors:
        for degree_index, degree in enumerate(person.degrees):
            for advisor_slot, advisor in enumerate(degree.advisors, start=1):
                edges.append(
                    EdgeRecord(
                        relation_kind="advisor",
                        from_person_id=person_id,
                        to_person_id=advisor.id,
                        relation_slot=advisor_slot,
                        relation_name_raw=advisor.name,
                        from_degree_index=degree_index,
                        href_raw=advisor.href_raw,
                    )
                )
                stats["edge_count"] += 1
                stats["advisor_edge_count"] += 1
                if advisor.id:
                    next_nodes.append((advisor.id, depth + 1))

    if include_students:
        for student_slot, student in enumerate(person.students, start=1):
            edges.append(
                EdgeRecord(
                    relation_kind="student",
                    from_person_id=person_id,
                    to_person_id=student.id,
                    relation_slot=student_slot,
                    relation_name_raw=student.name,
                    href_raw=student.href_raw,
                    institution_raw=student.school_raw,
                    year_value=student.year_value,
                    year_text=student.year_text,
                )
            )
            stats["edge_count"] += 1
            stats["student_edge_count"] += 1
            if student.id:
                next_nodes.append((student.id, depth + 1))
    return next_nodes


def _maybe_checkpoint(
    *,
    checkpoint_path_obj: Path | None,
    checkpoint_every_nodes: int,
    stats: dict,
    start_id_str: str,
    traversal_config: TraversalConfig,
    stack: list[tuple[str, int]],
    visited: set[str],
    nodes: dict[str, PersonRecord],
    edges: list[EdgeRecord],
    visit_order: list[str],
    warnings: list[str],
) -> None:
    if checkpoint_path_obj is None or checkpoint_every_nodes <= 0:
        return
    if stats["visited_nodes"] % checkpoint_every_nodes != 0:
        return
    _write_checkpoint(
        checkpoint_path_obj,
        start_id=start_id_str,
        config=traversal_config,
        stack=stack,
        visited=visited,
        nodes=nodes,
        edges=edges,
        visit_order=visit_order,
        stats=stats,
        warnings=warnings,
        complete=False,
    )


def build_advisor_graph(
    start_id: str | int,
    person_loader: Callable[[str], PersonRecord],
    *,
    config: TraversalConfig | None = None,
    resume_state: dict | None = None,
    checkpoint_path: str | Path | None = None,
    checkpoint_every_nodes: int = 1,
) -> GraphResult:
    traversal_config = config or TraversalConfig()
    start_id_str = str(start_id)
    checkpoint_path_obj = Path(checkpoint_path) if checkpoint_path else None

    stop_ids = traversal_config.normalized_stop_ids()
    stop_names = traversal_config.normalized_stop_names()
    exhaustive = traversal_config.exhaustive
    direction = traversal_config.direction
    if direction not in {"advisor", "student", "both"}:
        raise ValueError(f"Invalid traversal direction: {direction}")
    include_advisors = direction in {"advisor", "both"}
    include_students = direction in {"student", "both"}

    default_stats = {
        "visited_nodes": 0,
        "edge_count": 0,
        "revisited_skips": 0,
        "stoplist_hits": 0,
        "depth_limit_hits": 0,
        "max_nodes_hits": 0,
        "hard_cap_hits": 0,
        "advisor_edge_count": 0,
        "student_edge_count": 0,
    }
    stack, visited, nodes, edges, visit_order, warnings, stats = _initialize_state(
        start_id_str=start_id_str,
        resume_state=resume_state,
        default_stats=default_stats,
    )

    # Ensure visitation invariants if checkpoint content was manually edited.
    visited.update(nodes.keys())
    terminated_early = False

    while stack:
        person_id, depth = stack.pop()

        status = _preload_status(
            person_id=person_id,
            depth=depth,
            visited=visited,
            traversal_config=traversal_config,
            exhaustive=exhaustive,
            stack=stack,
            stats=stats,
            warnings=warnings,
        )
        if status == "skip":
            continue
        if status == "stop":
            terminated_early = True
            break

        person = person_loader(person_id)
        visited.add(person_id)
        nodes[person_id] = person
        visit_order.append(person_id)
        stats["visited_nodes"] += 1

        if person_id in stop_ids or normalize_person_name(person.name) in stop_names:
            stats["stoplist_hits"] += 1
            continue

        if not exhaustive and traversal_config.max_depth is not None and depth >= traversal_config.max_depth:
            stats["depth_limit_hits"] += 1
            continue

        next_nodes = _collect_next_nodes(
            person=person,
            person_id=person_id,
            depth=depth,
            include_advisors=include_advisors,
            include_students=include_students,
            edges=edges,
            stats=stats,
        )

        # Push in reverse so relation ordering remains stable in DFS.
        for next_id, next_depth in reversed(next_nodes):
            stack.append((next_id, next_depth))

        _maybe_checkpoint(
            checkpoint_path_obj=checkpoint_path_obj,
            checkpoint_every_nodes=checkpoint_every_nodes,
            stats=stats,
            start_id_str=start_id_str,
            traversal_config=traversal_config,
            stack=stack,
            visited=visited,
            nodes=nodes,
            edges=edges,
            visit_order=visit_order,
            warnings=warnings,
        )

    if checkpoint_path_obj:
        complete = (not stack) and (not terminated_early)
        _write_checkpoint(
            checkpoint_path_obj,
            start_id=start_id_str,
            config=traversal_config,
            stack=stack,
            visited=visited,
            nodes=nodes,
            edges=edges,
            visit_order=visit_order,
            stats=stats,
            warnings=warnings,
            complete=complete,
        )

    return GraphResult(
        start_id=start_id_str,
        nodes=nodes,
        edges=edges,
        visit_order=visit_order,
        stats=stats,
        warnings=warnings,
        config=traversal_config.to_dict(),
    )


def build_lineage_graph(
    start_id: str | int,
    person_loader: Callable[[str], PersonRecord],
    *,
    config: TraversalConfig | None = None,
    resume_state: dict | None = None,
    checkpoint_path: str | Path | None = None,
    checkpoint_every_nodes: int = 1,
) -> GraphResult:
    return build_advisor_graph(
        start_id,
        person_loader,
        config=config,
        resume_state=resume_state,
        checkpoint_path=checkpoint_path,
        checkpoint_every_nodes=checkpoint_every_nodes,
    )
