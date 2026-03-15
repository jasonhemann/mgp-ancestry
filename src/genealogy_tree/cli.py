from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import cast

from .lineage import TraversalConfig, build_advisor_graph, load_checkpoint
from .models import GraphResult, PersonRecord
from .parser import parse_person_html
from .snapshot_store import SnapshotStore
from .writers import write_gephi_exports, write_graph_json, write_markdown_lineage

DEFAULT_MAX_DEPTH = 20
DEFAULT_MAX_NODES = 500
DEFAULT_MAX_NODES_HARD = 10000
DEFAULT_SNAPSHOT_DIR = "data/snapshots"
DEFAULT_OUT_DIR = "out"


def _coerce_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _coerce_int(value: object, default: int) -> int:
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


def _coerce_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.casefold().strip()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        list_value = cast(list[object], value)
        return [_coerce_str(item) for item in list_value]
    if isinstance(value, tuple):
        tuple_value = cast(tuple[object, ...], value)
        return [_coerce_str(item) for item in tuple_value]
    return []


@dataclass(slots=True)
class BuildArgs:
    command: str
    start_id: str
    max_depth: int
    max_nodes: int
    max_nodes_hard: int
    stop_id: list[str]
    stop_name: list[str]
    exhaustive: bool
    refresh: bool
    snapshot_dir: str
    out_dir: str
    crawl_delay_seconds: float
    timeout_seconds: float
    checkpoint_path: str
    resume: bool
    checkpoint_every_nodes: int


@dataclass(slots=True)
class ExportGephiArgs:
    command: str
    lineage_json: str
    out_dir: str
    prefix: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mgp-ancestry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "build", help="Build advisor lineage graph from a start MGP ID"
    )
    _ = build_parser.add_argument(
        "start_id", help="Math Genealogy Project ID to start from"
    )
    _ = build_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    _ = build_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    _ = build_parser.add_argument(
        "--max-nodes-hard", type=int, default=DEFAULT_MAX_NODES_HARD
    )
    _ = build_parser.add_argument("--stop-id", action="append", default=[])
    _ = build_parser.add_argument("--stop-name", action="append", default=[])
    _ = build_parser.add_argument("--exhaustive", action="store_true")
    _ = build_parser.add_argument("--refresh", action="store_true")
    _ = build_parser.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR)
    _ = build_parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    _ = build_parser.add_argument("--crawl-delay-seconds", type=float, default=10.0)
    _ = build_parser.add_argument("--timeout-seconds", type=float, default=20.0)
    _ = build_parser.add_argument("--checkpoint-path", default="")
    _ = build_parser.add_argument("--resume", action="store_true")
    _ = build_parser.add_argument("--checkpoint-every-nodes", type=int, default=1)

    gephi_parser = subparsers.add_parser(
        "export-gephi", help="Export lineage JSON as Gephi CSV and GEXF"
    )
    _ = gephi_parser.add_argument("lineage_json", help="Path to lineage_*.json")
    _ = gephi_parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory for Gephi files (defaults beside JSON)",
    )
    _ = gephi_parser.add_argument(
        "--prefix",
        default="",
        help="Filename prefix (defaults to input JSON stem)",
    )
    return parser


def _namespace_to_build_args(namespace: argparse.Namespace) -> BuildArgs:
    return BuildArgs(
        command=_coerce_str(getattr(namespace, "command", ""), ""),
        start_id=_coerce_str(getattr(namespace, "start_id", ""), ""),
        max_depth=_coerce_int(
            getattr(namespace, "max_depth", DEFAULT_MAX_DEPTH), DEFAULT_MAX_DEPTH
        ),
        max_nodes=_coerce_int(
            getattr(namespace, "max_nodes", DEFAULT_MAX_NODES), DEFAULT_MAX_NODES
        ),
        max_nodes_hard=_coerce_int(
            getattr(namespace, "max_nodes_hard", DEFAULT_MAX_NODES_HARD),
            DEFAULT_MAX_NODES_HARD,
        ),
        stop_id=_coerce_str_list(getattr(namespace, "stop_id", [])),
        stop_name=_coerce_str_list(getattr(namespace, "stop_name", [])),
        exhaustive=_coerce_bool(getattr(namespace, "exhaustive", False)),
        refresh=_coerce_bool(getattr(namespace, "refresh", False)),
        snapshot_dir=_coerce_str(
            getattr(namespace, "snapshot_dir", DEFAULT_SNAPSHOT_DIR),
            DEFAULT_SNAPSHOT_DIR,
        ),
        out_dir=_coerce_str(
            getattr(namespace, "out_dir", DEFAULT_OUT_DIR), DEFAULT_OUT_DIR
        ),
        crawl_delay_seconds=_coerce_float(
            getattr(namespace, "crawl_delay_seconds", 10.0),
            10.0,
        ),
        timeout_seconds=_coerce_float(
            getattr(namespace, "timeout_seconds", 20.0), 20.0
        ),
        checkpoint_path=_coerce_str(getattr(namespace, "checkpoint_path", ""), ""),
        resume=_coerce_bool(getattr(namespace, "resume", False)),
        checkpoint_every_nodes=_coerce_int(
            getattr(namespace, "checkpoint_every_nodes", 1), 1
        ),
    )


def _namespace_to_export_gephi_args(namespace: argparse.Namespace) -> ExportGephiArgs:
    return ExportGephiArgs(
        command=_coerce_str(getattr(namespace, "command", ""), ""),
        lineage_json=_coerce_str(getattr(namespace, "lineage_json", ""), ""),
        out_dir=_coerce_str(getattr(namespace, "out_dir", ""), ""),
        prefix=_coerce_str(getattr(namespace, "prefix", ""), ""),
    )


def _resolve_traversal_config(args: BuildArgs) -> TraversalConfig:
    if args.exhaustive:
        max_depth = None if args.max_depth == DEFAULT_MAX_DEPTH else args.max_depth
        max_nodes = None if args.max_nodes == DEFAULT_MAX_NODES else args.max_nodes
    else:
        max_depth = args.max_depth
        max_nodes = args.max_nodes

    return TraversalConfig(
        max_depth=max_depth,
        max_nodes=max_nodes,
        max_nodes_hard=args.max_nodes_hard,
        stop_ids={str(value) for value in args.stop_id},
        stop_names={value for value in args.stop_name},
        exhaustive=args.exhaustive,
    )


def _run_build(args: BuildArgs) -> int:
    start_id = str(args.start_id)
    snapshot_store = SnapshotStore(
        Path(args.snapshot_dir),
        crawl_delay_seconds=args.crawl_delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )

    resume_state: dict[str, object] | None = None
    if args.resume:
        if not args.checkpoint_path:
            raise SystemExit("--resume requires --checkpoint-path")
        checkpoint_path = Path(args.checkpoint_path)
        if not checkpoint_path.exists():
            raise SystemExit(f"Checkpoint file does not exist: {checkpoint_path}")
        resume_state = load_checkpoint(checkpoint_path)

    def person_loader(person_id: str) -> PersonRecord:
        snapshot = snapshot_store.get_snapshot(person_id, refresh=args.refresh)
        return parse_person_html(
            snapshot.html,
            person_id=person_id,
            url=snapshot.url,
            source_snapshot=str(snapshot.html_path),
        )

    graph = build_advisor_graph(
        start_id,
        person_loader,
        config=_resolve_traversal_config(args),
        resume_state=resume_state,
        checkpoint_path=args.checkpoint_path or None,
        checkpoint_every_nodes=args.checkpoint_every_nodes,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = write_graph_json(graph, out_dir / f"lineage_{start_id}.json")
    md_path = write_markdown_lineage(graph, out_dir / f"lineage_{start_id}.md")

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")
    print(
        f"Visited nodes: {graph.stats['visited_nodes']}, edges: {graph.stats['edge_count']}"
    )
    return 0


def _run_export_gephi(args: ExportGephiArgs) -> int:
    lineage_path = Path(args.lineage_json)
    if not lineage_path.exists():
        raise SystemExit(f"Lineage JSON does not exist: {lineage_path}")

    raw_payload = cast(object, json.loads(lineage_path.read_text(encoding="utf-8")))
    if not isinstance(raw_payload, dict):
        raise SystemExit(f"Lineage JSON must be an object: {lineage_path}")
    payload = {
        str(key): value
        for key, value in cast(dict[object, object], raw_payload).items()
    }
    graph = GraphResult.from_dict(payload)

    prefix = args.prefix or lineage_path.stem
    out_dir = (
        Path(args.out_dir) if args.out_dir else lineage_path.parent / f"{prefix}_gephi"
    )

    result = write_gephi_exports(graph, out_dir, prefix=prefix)
    print(f"Wrote Gephi nodes CSV: {result.nodes_csv_path}")
    print(f"Wrote Gephi edges CSV: {result.edges_csv_path}")
    print(f"Wrote Gephi GEXF: {result.gexf_path}")
    print(
        f"Export summary: nodes={result.node_count}, edges={result.edge_count}, unresolved_edges={result.unresolved_edge_count}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    namespace = parser.parse_args(argv)
    command = _coerce_str(getattr(namespace, "command", ""), "")
    if command == "build":
        return _run_build(_namespace_to_build_args(namespace))
    if command == "export-gephi":
        return _run_export_gephi(_namespace_to_export_gephi_args(namespace))
    parser.print_usage(sys.stderr)
    print(f"{parser.prog}: error: Unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
