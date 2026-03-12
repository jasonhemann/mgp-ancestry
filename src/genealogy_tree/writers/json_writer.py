from __future__ import annotations

import json
from pathlib import Path

from ..models import GraphResult


def write_graph_json(graph: GraphResult, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return output
