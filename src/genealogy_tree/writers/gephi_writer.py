from __future__ import annotations

from collections import defaultdict, deque
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET

from ..models import GraphResult, YearMany, YearRaw, YearValue, extract_numeric_years

GEXF_NS = "http://www.gexf.net/1.2draft"


@dataclass(slots=True)
class GephiExportResult:
    nodes_csv_path: Path
    edges_csv_path: Path
    gexf_path: Path
    node_count: int
    edge_count: int
    unresolved_edge_count: int


def _year_value_to_numeric(year_value: YearValue) -> int | None:
    kind = year_value["kind"]
    if kind == "years":
        values = cast(YearMany, year_value)["values"]
        return min(values) if values else None
    if kind == "raw":
        values = extract_numeric_years(cast(YearRaw, year_value)["text"])
        return min(values) if values else None
    return None


def _ordinal(value: int) -> str:
    suffix = "th"
    if value % 100 not in {11, 12, 13}:
        if value % 10 == 1:
            suffix = "st"
        elif value % 10 == 2:
            suffix = "nd"
        elif value % 10 == 3:
            suffix = "rd"
    return f"{value}{suffix}"


def _century_from_year(year: int | None) -> str:
    if year is None:
        return ""
    century = ((year - 1) // 100) + 1
    return _ordinal(century)


def _compute_depths(graph: GraphResult) -> dict[str, int]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.to_person_id:
            adjacency[edge.from_person_id].append(edge.to_person_id)

    depths: dict[str, int] = {graph.start_id: 0}
    queue: deque[str] = deque([graph.start_id])
    while queue:
        node_id = queue.popleft()
        depth = depths[node_id]
        for next_id in adjacency.get(node_id, []):
            if next_id not in depths:
                depths[next_id] = depth + 1
                queue.append(next_id)
    return depths


def _ordered_node_ids(graph: GraphResult) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    for node_id in graph.visit_order:
        if node_id in graph.nodes and node_id not in seen:
            seen.add(node_id)
            ordered.append(node_id)

    for node_id in sorted(graph.nodes.keys()):
        if node_id not in seen:
            seen.add(node_id)
            ordered.append(node_id)
    return ordered


def _collect_node_values(graph: GraphResult) -> list[dict[str, str | int]]:
    depths = _compute_depths(graph)
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    for edge in graph.edges:
        if edge.to_person_id:
            out_degree[edge.from_person_id] += 1
            in_degree[edge.to_person_id] += 1

    rows: list[dict[str, str | int]] = []
    for node_id in _ordered_node_ids(graph):
        person = graph.nodes[node_id]

        institutions: list[str] = []
        countries: list[str] = []
        seen_institutions: set[str] = set()
        seen_countries: set[str] = set()
        year_candidates: list[int] = []

        for degree in person.degrees:
            maybe_year = _year_value_to_numeric(degree.year_value)
            if maybe_year is not None:
                year_candidates.append(maybe_year)
            for institution in degree.institutions:
                if institution.name_raw and institution.name_raw not in seen_institutions:
                    seen_institutions.add(institution.name_raw)
                    institutions.append(institution.name_raw)
                for country in institution.countries_raw:
                    if country and country not in seen_countries:
                        seen_countries.add(country)
                        countries.append(country)

        earliest_year = min(year_candidates) if year_candidates else None
        row: dict[str, str | int] = {
            "id": node_id,
            "label": person.name,
            "mgp_url": person.url,
            "is_start": 1 if node_id == graph.start_id else 0,
            "depth": depths.get(node_id, -1),
            "degree_count": len(person.degrees),
            "parse_warning_count": len(person.parse_warnings),
            "earliest_degree_year": earliest_year if earliest_year is not None else "",
            "century": _century_from_year(earliest_year),
            "countries_raw": "|".join(countries),
            "institutions_raw": "|".join(institutions),
            "advisor_out_degree": out_degree.get(node_id, 0),
            "advisor_in_degree": in_degree.get(node_id, 0),
        }
        rows.append(row)
    return rows


def _collect_edge_values(graph: GraphResult) -> tuple[list[dict[str, str | int]], int]:
    rows: list[dict[str, str | int]] = []
    unresolved_count = 0
    edge_index = 0
    for edge in graph.edges:
        if not edge.to_person_id:
            unresolved_count += 1
            continue
        edge_index += 1
        maybe_year = _year_value_to_numeric(edge.year_value)
        rows.append(
            {
                "id": f"e{edge_index}",
                "source": edge.from_person_id,
                "target": edge.to_person_id,
                "type": "Directed",
                "label": f"{edge.relation_kind}_{edge.relation_slot}",
                "relation_kind": edge.relation_kind,
                "relation_slot": edge.relation_slot,
                "from_degree_index": edge.from_degree_index if edge.from_degree_index is not None else "",
                "relation_name_raw": edge.relation_name_raw,
                "href_raw": edge.href_raw,
                "year_kind": edge.year_value.get("kind", "unknown"),
                "year_value": maybe_year if maybe_year is not None else "",
                "year_text": edge.year_text,
                "institution_raw": edge.institution_raw,
            }
        )
    return rows, unresolved_count


def _write_csv(output_path: Path, rows: list[dict[str, str | int]], fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_gexf(output_path: Path, node_rows: list[dict[str, str | int]], edge_rows: list[dict[str, str | int]]) -> None:
    ET.register_namespace("", GEXF_NS)

    gexf = ET.Element(f"{{{GEXF_NS}}}gexf", {"version": "1.2"})
    meta = ET.SubElement(gexf, f"{{{GEXF_NS}}}meta", {"lastmodifieddate": date.today().isoformat()})
    creator = ET.SubElement(meta, f"{{{GEXF_NS}}}creator")
    creator.text = "genealogy-tree"
    description = ET.SubElement(meta, f"{{{GEXF_NS}}}description")
    description.text = "Advisor-only lineage export"

    graph_el = ET.SubElement(
        gexf,
        f"{{{GEXF_NS}}}graph",
        {
            "defaultedgetype": "directed",
            "mode": "static",
        },
    )

    node_attr_fields = [
        ("mgp_url", "mgp_url", "string"),
        ("is_start", "is_start", "integer"),
        ("depth", "depth", "integer"),
        ("degree_count", "degree_count", "integer"),
        ("parse_warning_count", "parse_warning_count", "integer"),
        ("earliest_degree_year", "earliest_degree_year", "integer"),
        ("century", "century", "string"),
        ("countries_raw", "countries_raw", "string"),
        ("institutions_raw", "institutions_raw", "string"),
        ("advisor_out_degree", "advisor_out_degree", "integer"),
        ("advisor_in_degree", "advisor_in_degree", "integer"),
    ]
    edge_attr_fields = [
        ("relation_kind", "relation_kind", "string"),
        ("relation_slot", "relation_slot", "integer"),
        ("from_degree_index", "from_degree_index", "integer"),
        ("relation_name_raw", "relation_name_raw", "string"),
        ("href_raw", "href_raw", "string"),
        ("year_kind", "year_kind", "string"),
        ("year_value", "year_value", "integer"),
        ("year_text", "year_text", "string"),
        ("institution_raw", "institution_raw", "string"),
    ]

    node_attrs_el = ET.SubElement(graph_el, f"{{{GEXF_NS}}}attributes", {"class": "node"})
    for attr_id, title, attr_type in node_attr_fields:
        _ = ET.SubElement(
            node_attrs_el,
            f"{{{GEXF_NS}}}attribute",
            {"id": attr_id, "title": title, "type": attr_type},
        )

    edge_attrs_el = ET.SubElement(graph_el, f"{{{GEXF_NS}}}attributes", {"class": "edge"})
    for attr_id, title, attr_type in edge_attr_fields:
        _ = ET.SubElement(
            edge_attrs_el,
            f"{{{GEXF_NS}}}attribute",
            {"id": attr_id, "title": title, "type": attr_type},
        )

    nodes_el = ET.SubElement(graph_el, f"{{{GEXF_NS}}}nodes")
    for row in node_rows:
        node_id = str(row["id"])
        label = str(row["label"])
        node_el = ET.SubElement(nodes_el, f"{{{GEXF_NS}}}node", {"id": node_id, "label": label})
        attvalues = ET.SubElement(node_el, f"{{{GEXF_NS}}}attvalues")
        for attr_id, _, _ in node_attr_fields:
            value = row.get(attr_id, "")
            if value == "":
                continue
            _ = ET.SubElement(
                attvalues,
                f"{{{GEXF_NS}}}attvalue",
                {"for": attr_id, "value": str(value)},
            )

    edges_el = ET.SubElement(graph_el, f"{{{GEXF_NS}}}edges")
    for row in edge_rows:
        edge_id = str(row["id"])
        label = str(row["label"])
        edge_el = ET.SubElement(
            edges_el,
            f"{{{GEXF_NS}}}edge",
            {
                "id": edge_id,
                "source": str(row["source"]),
                "target": str(row["target"]),
                "label": label,
                "type": "directed",
            },
        )
        attvalues = ET.SubElement(edge_el, f"{{{GEXF_NS}}}attvalues")
        for attr_id, _, _ in edge_attr_fields:
            value = row.get(attr_id, "")
            if value == "":
                continue
            _ = ET.SubElement(
                attvalues,
                f"{{{GEXF_NS}}}attvalue",
                {"for": attr_id, "value": str(value)},
            )

    tree = ET.ElementTree(gexf)
    ET.indent(tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def write_gephi_exports(
    graph: GraphResult,
    output_dir: str | Path,
    *,
    prefix: str = "lineage",
) -> GephiExportResult:
    output_root = Path(output_dir)
    node_rows = _collect_node_values(graph)
    edge_rows, unresolved_count = _collect_edge_values(graph)

    nodes_csv_path = output_root / f"{prefix}_nodes.csv"
    edges_csv_path = output_root / f"{prefix}_edges.csv"
    gexf_path = output_root / f"{prefix}.gexf"

    _write_csv(
        nodes_csv_path,
        node_rows,
        fieldnames=[
            "id",
            "label",
            "mgp_url",
            "is_start",
            "depth",
            "degree_count",
            "parse_warning_count",
            "earliest_degree_year",
            "century",
            "countries_raw",
            "institutions_raw",
            "advisor_out_degree",
            "advisor_in_degree",
        ],
    )
    _write_csv(
        edges_csv_path,
        edge_rows,
        fieldnames=[
            "id",
            "source",
            "target",
            "type",
            "label",
            "relation_kind",
            "relation_slot",
            "from_degree_index",
            "relation_name_raw",
            "href_raw",
            "year_kind",
            "year_value",
            "year_text",
            "institution_raw",
        ],
    )
    _write_gexf(gexf_path, node_rows, edge_rows)

    return GephiExportResult(
        nodes_csv_path=nodes_csv_path,
        edges_csv_path=edges_csv_path,
        gexf_path=gexf_path,
        node_count=len(node_rows),
        edge_count=len(edge_rows),
        unresolved_edge_count=unresolved_count,
    )
