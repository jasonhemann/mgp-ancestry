from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .lineage import TraversalConfig, build_advisor_graph, load_checkpoint
from .parser import parse_person_html
from .snapshot_store import SnapshotStore
from .writers import write_graph_json, write_markdown_lineage

DEFAULT_MAX_DEPTH = 20
DEFAULT_MAX_NODES = 500
DEFAULT_MAX_NODES_HARD = 10000
DEFAULT_SNAPSHOT_DIR = "data/snapshots"
DEFAULT_OUT_DIR = "out"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="genealogy-tree")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build advisor lineage graph from a start MGP ID")
    build_parser.add_argument("start_id", help="Math Genealogy Project ID to start from")
    build_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    build_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    build_parser.add_argument("--max-nodes-hard", type=int, default=DEFAULT_MAX_NODES_HARD)
    build_parser.add_argument("--stop-id", action="append", default=[])
    build_parser.add_argument("--stop-name", action="append", default=[])
    build_parser.add_argument("--direction", choices=["advisor", "student", "both"], default="advisor")
    build_parser.add_argument("--exhaustive", action="store_true")
    build_parser.add_argument("--refresh", action="store_true")
    build_parser.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR)
    build_parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    build_parser.add_argument("--crawl-delay-seconds", type=float, default=10.0)
    build_parser.add_argument("--timeout-seconds", type=float, default=20.0)
    build_parser.add_argument("--checkpoint-path", default="")
    build_parser.add_argument("--resume", action="store_true")
    build_parser.add_argument("--checkpoint-every-nodes", type=int, default=1)
    return parser


def _resolve_traversal_config(args: argparse.Namespace) -> TraversalConfig:
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
        direction=args.direction,
    )


def _run_build(args: argparse.Namespace) -> int:
    start_id = str(args.start_id)
    snapshot_store = SnapshotStore(
        Path(args.snapshot_dir),
        crawl_delay_seconds=args.crawl_delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )

    resume_state = None
    if args.resume:
        if not args.checkpoint_path:
            raise SystemExit("--resume requires --checkpoint-path")
        checkpoint_path = Path(args.checkpoint_path)
        if not checkpoint_path.exists():
            raise SystemExit(f"Checkpoint file does not exist: {checkpoint_path}")
        resume_state = load_checkpoint(checkpoint_path)

    def person_loader(person_id: str):
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
        "Visited nodes: "
        f"{graph.stats['visited_nodes']}, "
        f"edges: {graph.stats['edge_count']} "
        f"(advisor={graph.stats.get('advisor_edge_count', 0)}, "
        f"student={graph.stats.get('student_edge_count', 0)})"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        return _run_build(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
