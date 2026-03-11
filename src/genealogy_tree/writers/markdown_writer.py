from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..models import GraphResult


def _format_year_value(value: dict) -> str:
    kind = value.get("kind", "unknown")
    if kind == "year":
        return str(value.get("value", ""))
    if kind == "years":
        return ", ".join(str(v) for v in value.get("values", []))
    if kind == "raw":
        return str(value.get("text", ""))
    return "Unknown"


def _format_degree_payload(degree: dict) -> str:
    institutions = degree.get("institutions", [])
    institution_text = (
        ", ".join(item.get("name_raw", "") for item in institutions if item.get("name_raw")) or "Unknown institution"
    )
    year_text = _format_year_value(degree.get("year", {"kind": "unknown"}))
    degree_type = degree.get("degree_type", "") or "Unknown degree"
    dissertation = degree.get("dissertation", "") or "Unknown dissertation"
    return f"{degree_type}; institutions: {institution_text}; year: {year_text}; dissertation: {dissertation}"


def render_markdown_lineage(graph: GraphResult) -> str:
    data = graph.to_dict()
    start_id = data["start_id"]
    nodes = data["nodes"]
    edges = data["edges"]
    stats = data["stats"]

    adjacency: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        adjacency[edge["from_person_id"]].append(edge)

    start_node = nodes.get(start_id, {"name": "Unknown"})
    lines: list[str] = [
        f"# Advisor Lineage for {start_node['name']} ({start_id})",
        "",
        "## Run Summary",
        f"- Nodes visited: {stats.get('visited_nodes', 0)}",
        f"- Edges collected: {stats.get('edge_count', 0)}",
        f"- Advisor edges: {stats.get('advisor_edge_count', 0)}",
        f"- Revisited skips: {stats.get('revisited_skips', 0)}",
    ]

    warnings = list(data.get("warnings", []))
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {warning}" for warning in warnings])

    lines.extend(["", "## Traversal Tree"])
    rendered: set[str] = set()

    def emit_node(person_id: str, indent: int) -> None:
        node = nodes.get(person_id)
        prefix = " " * indent
        if not node:
            lines.append(f"{prefix}- Unknown node ({person_id})")
            return

        anchor = f"node-{person_id}"
        if person_id in rendered:
            lines.append(f"{prefix}- {node['name']} ({person_id}) [see above](#{anchor})")
            return

        rendered.add(person_id)
        lines.append(f"{prefix}- <a id=\"{anchor}\"></a>{node['name']} ({person_id}) - [MGP]({node['url']})")
        if node.get("source_snapshot"):
            lines.append(f"{prefix}  - snapshot: `{node['source_snapshot']}`")

        degree_payloads = node.get("degrees", [])
        for idx, degree_payload in enumerate(degree_payloads, start=1):
            lines.append(f"{prefix}  - degree {idx}: {_format_degree_payload(degree_payload)}")

        for edge in adjacency.get(person_id, []):
            relation_kind = edge.get("relation_kind", "advisor")
            relation_name = edge.get("relation_name_raw", "Unknown")
            relation_slot = int(edge.get("relation_slot", 1))
            target_id = edge.get("to_person_id")

            if relation_kind == "student":
                label = f"student {relation_slot}"
                institution_raw = edge.get("institution_raw", "")
                year_display = _format_year_value(edge.get("year", {"kind": "unknown"}))
                suffix_parts: list[str] = []
                if institution_raw:
                    suffix_parts.append(f"school: {institution_raw}")
                if year_display != "Unknown":
                    suffix_parts.append(f"year: {year_display}")
                suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
            else:
                degree_index = edge.get("from_degree_index")
                if degree_index is None:
                    label = f"advisor {relation_slot}"
                else:
                    label = f"advisor {relation_slot} (degree {int(degree_index) + 1})"
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
            "- `year` is a single parsed year.",
            "- `years` captures multiple parsed years in source order.",
            "- `raw` preserves non-numeric year text exactly.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_markdown_lineage(graph: GraphResult, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown_lineage(graph), encoding="utf-8")
    return output
