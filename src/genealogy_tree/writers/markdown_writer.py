from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from ..models import GraphResult


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


def _format_year_value(value: Mapping[str, object]) -> str:
    kind = _coerce_str(value.get("kind"), "unknown")
    if kind == "years":
        years = [_coerce_str(v) for v in _as_object_list(value.get("values"))]
        return ", ".join(years)
    if kind == "raw":
        return _coerce_str(value.get("text"), "")
    return "Unknown"


def _format_degree_payload(degree: Mapping[str, object]) -> str:
    institutions = [_as_mapping(item) for item in _as_object_list(degree.get("institutions"))]
    institution_names = [
        _coerce_str(item.get("name_raw"), "") for item in institutions if _coerce_str(item.get("name_raw"), "")
    ]
    institution_text = ", ".join(institution_names) or "Unknown institution"
    year_text = _format_year_value(_as_mapping(degree.get("year", {"kind": "unknown"})))
    degree_type = _coerce_str(degree.get("degree_type"), "") or "Unknown degree"
    dissertation = _coerce_str(degree.get("dissertation"), "") or "Unknown dissertation"
    return f"{degree_type}; institutions: {institution_text}; year: {year_text}; dissertation: {dissertation}"


def render_markdown_lineage(graph: GraphResult) -> str:
    data = graph.to_dict()
    start_id = _coerce_str(data.get("start_id"), "")

    raw_nodes = _as_mapping(data.get("nodes", {}))
    nodes: dict[str, Mapping[str, object]] = {
        _coerce_str(node_id): _as_mapping(node_payload) for node_id, node_payload in raw_nodes.items()
    }
    edges = [_as_mapping(edge) for edge in _as_object_list(data.get("edges", []))]
    stats = _as_mapping(data.get("stats", {}))

    adjacency: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for edge in edges:
        from_id = _coerce_str(edge.get("from_person_id"), "")
        if from_id:
            adjacency[from_id].append(edge)

    start_node = nodes.get(start_id, {"name": "Unknown"})
    lines: list[str] = [
        f"# Advisor Lineage for {_coerce_str(start_node.get('name'), 'Unknown')} ({start_id})",
        "",
        "## Run Summary",
        f"- Nodes visited: {_coerce_int(stats.get('visited_nodes'), 0)}",
        f"- Edges collected: {_coerce_int(stats.get('edge_count'), 0)}",
        f"- Advisor edges: {_coerce_int(stats.get('advisor_edge_count'), 0)}",
        f"- Revisited skips: {_coerce_int(stats.get('revisited_skips'), 0)}",
    ]

    warnings = [_coerce_str(w) for w in _as_object_list(data.get("warnings", []))]
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {warning}" for warning in warnings])

    lines.extend(["", "## Traversal Tree"])
    rendered: set[str] = set()

    def emit_node(person_id: str, indent: int) -> None:
        node = nodes.get(person_id)
        prefix = " " * indent
        if node is None:
            lines.append(f"{prefix}- Unknown node ({person_id})")
            return

        anchor = f"node-{person_id}"
        node_name = _coerce_str(node.get("name"), "Unknown")
        if person_id in rendered:
            lines.append(f"{prefix}- {node_name} ({person_id}) [see above](#{anchor})")
            return

        rendered.add(person_id)
        node_url = _coerce_str(node.get("url"), "")
        lines.append(f"{prefix}- <a id=\"{anchor}\"></a>{node_name} ({person_id}) - [MGP]({node_url})")
        source_snapshot = _coerce_str(node.get("source_snapshot"), "")
        if source_snapshot:
            lines.append(f"{prefix}  - snapshot: `{source_snapshot}`")

        degree_payloads = [_as_mapping(item) for item in _as_object_list(node.get("degrees", []))]
        for idx, degree_payload in enumerate(degree_payloads, start=1):
            lines.append(f"{prefix}  - degree {idx}: {_format_degree_payload(degree_payload)}")

        for edge in adjacency.get(person_id, []):
            relation_kind = _coerce_str(edge.get("relation_kind"), "advisor")
            relation_name = _coerce_str(edge.get("relation_name_raw"), "Unknown")
            relation_slot = _coerce_int(edge.get("relation_slot"), 1)
            target_id_raw = edge.get("to_person_id")
            target_id = _coerce_str(target_id_raw) if target_id_raw is not None else ""

            if relation_kind == "student":
                label = f"student {relation_slot}"
                institution_raw = _coerce_str(edge.get("institution_raw"), "")
                year_display = _format_year_value(_as_mapping(edge.get("year", {"kind": "unknown"})))
                suffix_parts: list[str] = []
                if institution_raw:
                    suffix_parts.append(f"school: {institution_raw}")
                if year_display != "Unknown":
                    suffix_parts.append(f"year: {year_display}")
                suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
            else:
                degree_index_raw = edge.get("from_degree_index")
                if degree_index_raw is None:
                    label = f"advisor {relation_slot}"
                else:
                    degree_index = _coerce_int(degree_index_raw, 0)
                    label = f"advisor {relation_slot} (degree {degree_index + 1})"
                suffix = ""

            if target_id:
                lines.append(f"{prefix}  - {label}: {relation_name}{suffix}")
                emit_node(target_id, indent + 4)
            else:
                lines.append(f"{prefix}  - {label}: {relation_name}{suffix} (unresolvable)")

    emit_node(start_id, 0)

    lines.extend(
        [
            "",
            "## Year Value Notes",
            "- `unknown` means no year was present.",
            "- `years` captures one or more parsed years in source order.",
            "- `raw` preserves non-numeric year text exactly.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_markdown_lineage(graph: GraphResult, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_text(render_markdown_lineage(graph), encoding="utf-8")
    return output
