#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

YEAR_RE = re.compile(r"\b(\d{4})\b")
WHITESPACE_RE = re.compile(r"\s+")
TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class CollapsedEdge:
    source: str
    target: str
    multiplicity: int
    relation_names: tuple[str, ...]
    degree_indexes: tuple[int, ...]


def parse_bool(value: str) -> bool:
    text = value.strip().lower()
    if text in TRUTHY:
        return True
    if text in FALSY:
        return False
    raise argparse.ArgumentTypeError(f"Invalid bool value: {value}")


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a JSON object: {config_path}")
    return payload


def config_get(config: dict[str, Any], section: str, key: str, default: Any) -> Any:
    section_value = config.get(section, {})
    if isinstance(section_value, dict) and key in section_value:
        return section_value[key]
    return default


def parse_year_from_payload(year_payload: dict[str, Any]) -> int | None:
    kind = str(year_payload.get("kind", "unknown"))
    if kind == "year":
        value = year_payload.get("value")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit() and len(value) == 4:
            return int(value)
        return None
    if kind == "years":
        values = [int(v) for v in year_payload.get("values", []) if str(v).isdigit()]
        return min(values) if values else None
    if kind == "raw":
        text = str(year_payload.get("text", ""))
        values = [int(m.group(1)) for m in YEAR_RE.finditer(text)]
        return min(values) if values else None
    return None


def earliest_degree_year(node_payload: dict[str, Any]) -> int | None:
    years: list[int] = []
    for degree in node_payload.get("degrees", []):
        if not isinstance(degree, dict):
            continue
        year_payload = degree.get("year", {})
        if not isinstance(year_payload, dict):
            continue
        maybe_year = parse_year_from_payload(year_payload)
        if maybe_year is not None:
            years.append(maybe_year)
    return min(years) if years else None


def trim_label(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3] + "..."


def normalize_display_name(name: str) -> str:
    collapsed = WHITESPACE_RE.sub(" ", name).strip()
    return collapsed or "Unknown"


def dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def normalize_resolved_edges(payload: dict[str, Any]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for edge in payload.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = edge.get("from_person_id")
        target = edge.get("to_person_id")
        if source is None or target is None:
            continue
        resolved.append(edge)
    return resolved


def collapse_edges(resolved_edges: list[dict[str, Any]], collapse_parallel: bool) -> list[CollapsedEdge]:
    if not collapse_parallel:
        collapsed: list[CollapsedEdge] = []
        for edge in resolved_edges:
            degree_raw = edge.get("from_degree_index")
            degree_indexes = (int(degree_raw),) if degree_raw is not None else tuple()
            relation_name = str(edge.get("relation_name_raw", "")).strip()
            relation_names = (relation_name,) if relation_name else tuple()
            collapsed.append(
                CollapsedEdge(
                    source=str(edge["from_person_id"]),
                    target=str(edge["to_person_id"]),
                    multiplicity=1,
                    relation_names=relation_names,
                    degree_indexes=degree_indexes,
                )
            )
        return collapsed

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in resolved_edges:
        key = (str(edge["from_person_id"]), str(edge["to_person_id"]))
        groups[key].append(edge)

    collapsed: list[CollapsedEdge] = []
    for (source, target), edges in sorted(groups.items()):
        relation_names = sorted(
            {
                str(edge.get("relation_name_raw", "")).strip()
                for edge in edges
                if str(edge.get("relation_name_raw", "")).strip()
            }
        )
        degree_indexes = sorted(
            {
                int(edge["from_degree_index"])
                for edge in edges
                if edge.get("from_degree_index") is not None
            }
        )
        collapsed.append(
            CollapsedEdge(
                source=source,
                target=target,
                multiplicity=len(edges),
                relation_names=tuple(relation_names),
                degree_indexes=tuple(degree_indexes),
            )
        )
    return collapsed


def compute_depths(start_id: str, collapsed_edges: list[CollapsedEdge]) -> dict[str, int]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in collapsed_edges:
        adjacency[edge.source].append(edge.target)

    depths: dict[str, int] = {start_id: 0}
    queue: deque[str] = deque([start_id])
    while queue:
        node_id = queue.popleft()
        depth = depths[node_id]
        for target in adjacency.get(node_id, []):
            if target in depths:
                continue
            depths[target] = depth + 1
            queue.append(target)
    return depths


def attrs_to_dot(attrs: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in attrs.items():
        parts.append(f'{key}="{dot_escape(str(value))}"')
    return ", ".join(parts)


def build_dot(
    payload: dict[str, Any],
    collapsed_edges: list[CollapsedEdge],
    depths: dict[str, int],
    config: dict[str, Any],
    *,
    max_label_chars: int,
    include_year: bool,
) -> str:
    start_id = str(payload["start_id"])
    nodes = payload.get("nodes", {})

    max_depth = max(depths.values(), default=0)
    for node_id in sorted(nodes.keys()):
        if node_id not in depths:
            max_depth += 1
            depths[node_id] = max_depth

    graph_attrs = {
        "rankdir": str(config_get(config, "graph", "rankdir", "BT")),
        "splines": str(config_get(config, "graph", "splines", "true")),
        "overlap": str(config_get(config, "graph", "overlap", "false")),
        "newrank": str(config_get(config, "graph", "newrank", "true")),
        "remincross": str(config_get(config, "graph", "remincross", "true")),
        "mclimit": str(config_get(config, "graph", "mclimit", 10)),
        "nodesep": str(config_get(config, "graph", "nodesep", 0.35)),
        "ranksep": str(config_get(config, "graph", "ranksep", 0.9)),
        "bgcolor": str(config_get(config, "graph", "bgcolor", "white")),
    }

    node_defaults = {
        "shape": str(config_get(config, "node", "shape", "box")),
        "style": str(config_get(config, "node", "style", "rounded,filled")),
        "fillcolor": str(config_get(config, "node", "fillcolor", "#f8fafc")),
        "color": str(config_get(config, "node", "color", "#334155")),
        "fontname": str(config_get(config, "node", "fontname", "Helvetica")),
        "fontsize": str(config_get(config, "node", "fontsize", 10)),
    }

    edge_defaults = {
        "color": str(config_get(config, "edge", "color", "#64748b")),
        "arrowsize": str(config_get(config, "edge", "arrowsize", 0.7)),
        "fontname": str(config_get(config, "edge", "fontname", "Helvetica")),
        "fontsize": str(config_get(config, "edge", "fontsize", 9)),
    }

    start_fillcolor = str(config_get(config, "start_node", "fillcolor", "#dbeafe"))
    start_color = str(config_get(config, "start_node", "color", "#1d4ed8"))

    penwidth_min = float(config_get(config, "edge", "penwidth_min", 0.8))
    penwidth_step = float(config_get(config, "edge", "penwidth_step", 0.45))
    penwidth_max = float(config_get(config, "edge", "penwidth_max", 3.2))

    lines: list[str] = ["digraph lineage {"]
    lines.append(f"  graph [{attrs_to_dot(graph_attrs)}];")
    lines.append(f"  node [{attrs_to_dot(node_defaults)}];")
    lines.append(f"  edge [{attrs_to_dot(edge_defaults)}];")

    for node_id in sorted(nodes.keys(), key=lambda n: (depths.get(n, 10**9), n)):
        node_payload = nodes.get(node_id, {}) if isinstance(nodes, dict) else {}
        raw_name = str(node_payload.get("name", "Unknown"))
        display_name = normalize_display_name(raw_name)
        label = trim_label(display_name, max_label_chars)

        if include_year:
            year = earliest_degree_year(node_payload if isinstance(node_payload, dict) else {})
            if year is not None:
                label = f"{label} ({year})"

        node_attrs: dict[str, Any] = {
            "label": label,
            "tooltip": f"{node_id} | {display_name}",
        }
        url = str(node_payload.get("url", "")) if isinstance(node_payload, dict) else ""
        if url:
            node_attrs["URL"] = url
            node_attrs["target"] = "_blank"
        if node_id == start_id:
            node_attrs["fillcolor"] = start_fillcolor
            node_attrs["color"] = start_color

        lines.append(f'  "{dot_escape(node_id)}" [{attrs_to_dot(node_attrs)}];')

    for edge in collapsed_edges:
        penwidth = max(penwidth_min, min(penwidth_max, penwidth_min + (edge.multiplicity - 1) * penwidth_step))
        edge_attrs: dict[str, Any] = {
            "weight": edge.multiplicity,
            "penwidth": f"{penwidth:.2f}",
            "tooltip": f"count={edge.multiplicity}",
        }
        if edge.multiplicity > 1:
            edge_attrs["label"] = f"x{edge.multiplicity}"

        tooltip_parts: list[str] = [f"count={edge.multiplicity}"]
        if edge.degree_indexes:
            tooltip_parts.append("degree_indexes=" + ",".join(str(v) for v in edge.degree_indexes))
        if edge.relation_names:
            tooltip_parts.append("advisors=" + ", ".join(edge.relation_names))
        edge_attrs["tooltip"] = " | ".join(tooltip_parts)

        lines.append(
            f'  "{dot_escape(edge.source)}" -> "{dot_escape(edge.target)}" [{attrs_to_dot(edge_attrs)}];'
        )

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def render_with_graphviz(engine: str, dot_path: Path, output_path: Path, fmt: str) -> None:
    try:
        subprocess.run(
            [engine, f"-T{fmt}", str(dot_path), "-o", str(output_path)],
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"Graphviz engine not found: {engine}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise SystemExit(f"Graphviz render failed ({fmt}): {stderr}") from exc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render lineage JSON with Graphviz.")
    parser.add_argument("--input", required=True, help="Path to lineage_*.json")
    parser.add_argument("--output-dir", required=True, help="Directory for dot/svg/png output")
    parser.add_argument("--format", choices=["dot", "svg", "png", "all"], default="all")
    parser.add_argument("--engine", default="dot", help="Graphviz engine executable (default: dot)")
    parser.add_argument("--collapse-parallel", type=parse_bool, default=True)
    parser.add_argument("--max-label-chars", type=int, default=40)
    parser.add_argument("--include-year", type=parse_bool, default=True)
    default_config = Path(__file__).resolve().parents[1] / "config" / "vertical_ancestry.json"
    parser.add_argument("--config", default=str(default_config), help="JSON layout/style config")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if "start_id" not in payload or "nodes" not in payload or "edges" not in payload:
        raise SystemExit("Lineage JSON missing required keys: start_id, nodes, edges")

    resolved_edges = normalize_resolved_edges(payload)
    collapsed_edges = collapse_edges(resolved_edges, collapse_parallel=args.collapse_parallel)
    depths = compute_depths(str(payload["start_id"]), collapsed_edges)

    config_path = Path(args.config)
    config = load_config(config_path)

    dot_text = build_dot(
        payload,
        collapsed_edges,
        depths,
        config,
        max_label_chars=args.max_label_chars,
        include_year=args.include_year,
    )

    start_id = str(payload["start_id"])
    dot_path = output_dir / f"lineage_{start_id}.dot"
    dot_path.write_text(dot_text, encoding="utf-8")
    print(f"Wrote DOT: {dot_path}")

    formats: list[str]
    if args.format == "all":
        formats = ["svg", "png"]
    elif args.format == "dot":
        formats = []
    else:
        formats = [args.format]

    for fmt in formats:
        render_path = output_dir / f"lineage_{start_id}.{fmt}"
        render_with_graphviz(args.engine, dot_path, render_path, fmt)
        print(f"Wrote {fmt.upper()}: {render_path}")

    parallel_edge_pairs = sum(1 for edge in collapsed_edges if edge.multiplicity > 1)
    print(
        "Summary: "
        f"nodes={len(payload.get('nodes', {}))}, "
        f"resolved_edges={len(resolved_edges)}, "
        f"emitted_edges={len(collapsed_edges)}, "
        f"parallel_pairs={parallel_edge_pairs}, "
        f"collapse_parallel={args.collapse_parallel}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
