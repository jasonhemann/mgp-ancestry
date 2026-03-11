from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import cast

from .models import (
    EdgeRecord,
    GENERATOR_VERSION,
    GraphResult,
    PersonRecord,
    SCHEMA_VERSION,
    normalize_person_name,
)

type StackItem = tuple[str, int]
type StatsDict = dict[str, int]


def _coerce_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return {}


def _as_object_list(value: object) -> list[object]:
    if isinstance(value, list):
        return list(cast(list[object], value))
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    return []


def _as_object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(key): item for key, item in mapping.items()}


@dataclass(slots=True)
class TraversalConfig:
    max_depth: int | None = 20
    max_nodes: int | None = 500
    max_nodes_hard: int = 10000
    stop_ids: set[str] | None = None
    stop_names: set[str] | None = None
    exhaustive: bool = False

    def normalized_stop_ids(self) -> set[str]:
        return set(self.stop_ids or set())

    def normalized_stop_names(self) -> set[str]:
        return {normalize_person_name(name) for name in (self.stop_names or set())}

    def to_dict(self) -> dict[str, object]:
        return {
            "max_depth": self.max_depth,
            "max_nodes": self.max_nodes,
            "max_nodes_hard": self.max_nodes_hard,
            "stop_ids": sorted(self.normalized_stop_ids()),
            "stop_names": sorted(self.normalized_stop_names()),
            "exhaustive": self.exhaustive,
        }


def load_checkpoint(checkpoint_path: str | Path) -> dict[str, object]:
    path = Path(checkpoint_path)
    payload_obj = cast(object, json.loads(path.read_text(encoding="utf-8")))
    return _as_object_dict(payload_obj)


def _serialize_open_stack(stack: list[StackItem]) -> list[dict[str, object]]:
    return [{"id": person_id, "depth": depth} for person_id, depth in stack]


def _deserialize_open_stack(payload: list[dict[str, object]]) -> list[StackItem]:
    return [(_coerce_str(item.get("id"), ""), _coerce_int(item.get("depth"), 0)) for item in payload]


def _write_checkpoint(
    checkpoint_path: Path,
    *,
    start_id: str,
    config: TraversalConfig,
    stack: list[StackItem],
    visited: set[str],
    nodes: dict[str, PersonRecord],
    edges: list[EdgeRecord],
    visit_order: list[str],
    stats: StatsDict,
    warnings: list[str],
    complete: bool,
) -> None:
    checkpoint_payload: dict[str, object] = {
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
    _ = checkpoint_path.write_text(
        json.dumps(checkpoint_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _initialize_state(
    *,
    start_id_str: str,
    resume_state: dict[str, object] | None,
    default_stats: StatsDict,
) -> tuple[
    list[StackItem],
    set[str],
    dict[str, PersonRecord],
    list[EdgeRecord],
    list[str],
    list[str],
    StatsDict,
]:
    if resume_state:
        open_stack_payload = [
            _as_object_dict(item) for item in _as_object_list(resume_state.get("open_stack", []))
        ]
        stack = _deserialize_open_stack(open_stack_payload)
        if not stack:
            stack = [(start_id_str, 0)]

        visited: set[str] = {
            _coerce_str(v) for v in _as_object_list(resume_state.get("visited_ids", []))
        }

        nodes: dict[str, PersonRecord] = {}
        for node_id, node_payload in _as_object_dict(resume_state.get("nodes", {})).items():
            nodes[_coerce_str(node_id)] = PersonRecord.from_dict(_as_mapping(node_payload))

        edges = [
            EdgeRecord.from_dict(_as_mapping(item))
            for item in _as_object_list(resume_state.get("edges", []))
        ]
        visit_order = [_coerce_str(v) for v in _as_object_list(resume_state.get("visit_order", []))]
        warnings = [_coerce_str(v) for v in _as_object_list(resume_state.get("warnings", []))]

        stats: StatsDict = dict(default_stats)
        for key, raw_value in _as_object_dict(resume_state.get("stats", {})).items():
            stats[_coerce_str(key)] = _coerce_int(raw_value, stats.get(_coerce_str(key), 0))

        if _coerce_str(resume_state.get("start_id"), start_id_str) != start_id_str:
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
    stack: list[StackItem],
    stats: StatsDict,
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
    edges: list[EdgeRecord],
    stats: StatsDict,
) -> list[StackItem]:
    next_nodes: list[StackItem] = []
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
    return next_nodes


def _maybe_checkpoint(
    *,
    checkpoint_path_obj: Path | None,
    checkpoint_every_nodes: int,
    stats: StatsDict,
    start_id_str: str,
    traversal_config: TraversalConfig,
    stack: list[StackItem],
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
    resume_state: dict[str, object] | None = None,
    checkpoint_path: str | Path | None = None,
    checkpoint_every_nodes: int = 1,
) -> GraphResult:
    traversal_config = config or TraversalConfig()
    start_id_str = str(start_id)
    checkpoint_path_obj = Path(checkpoint_path) if checkpoint_path else None

    stop_ids = traversal_config.normalized_stop_ids()
    stop_names = traversal_config.normalized_stop_names()
    exhaustive = traversal_config.exhaustive

    default_stats: StatsDict = {
        "visited_nodes": 0,
        "edge_count": 0,
        "revisited_skips": 0,
        "stoplist_hits": 0,
        "depth_limit_hits": 0,
        "max_nodes_hits": 0,
        "hard_cap_hits": 0,
        "advisor_edge_count": 0,
    }
    stack, visited, nodes, edges, visit_order, warnings, stats = _initialize_state(
        start_id_str=start_id_str,
        resume_state=resume_state,
        default_stats=default_stats,
    )

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
            edges=edges,
            stats=stats,
        )

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
    resume_state: dict[str, object] | None = None,
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
