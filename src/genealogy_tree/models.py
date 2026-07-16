from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Literal, TypedDict, cast

PARSER_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = PARSER_VERSION


class YearUnknown(TypedDict):
    kind: Literal["unknown"]


class YearMany(TypedDict):
    kind: Literal["years"]
    values: list[int]


class YearRaw(TypedDict):
    kind: Literal["raw"]
    text: str


type YearValue = YearUnknown | YearMany | YearRaw


def year_unknown() -> YearValue:
    return {"kind": "unknown"}


def year_many(values: list[int]) -> YearValue:
    deduped: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(int(value))
    return {"kind": "years", "values": deduped}


def year_raw(text: str) -> YearValue:
    return {"kind": "raw", "text": text}


def extract_numeric_years(text: str) -> list[int]:
    return [int(m.group(1)) for m in re.finditer(r"\b(\d{4})\b", text)]


def make_year_value(raw_text: str, numeric_years: list[int]) -> YearValue:
    if numeric_years:
        return year_many(numeric_years)
    if raw_text.strip():
        return year_raw(raw_text.strip())
    return year_unknown()


def year_value_sort_key(value: YearValue) -> tuple[int, int]:
    kind = value["kind"]
    if kind == "unknown":
        return (0, 0)
    if kind == "years":
        years_value = cast(YearMany, value)
        years = [int(y) for y in years_value["values"]]
        return (1, min(years) if years else 0)

    raw_value = cast(YearRaw, value)
    raw_text = raw_value["text"]
    years = extract_numeric_years(raw_text)
    if years:
        return (1, min(years))
    return (0, 0)


def normalize_person_name(name: str) -> str:
    return " ".join(name.casefold().split())


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return {}


def _require_mapping(raw_value: object, *, field_path: str) -> Mapping[str, object]:
    payload = _as_mapping(raw_value)
    if not payload:
        raise ValueError(f"{field_path} must be an object")
    return payload


def _coerce_year_value(raw_value: object, *, field_path: str) -> YearValue:
    payload = _require_mapping(raw_value, field_path=field_path)
    kind_value = payload.get("kind")
    if not isinstance(kind_value, str):
        raise ValueError(f"{field_path}.kind must be a string")
    kind = kind_value.strip()
    if kind == "unknown":
        return year_unknown()
    if kind == "years":
        values_raw = payload.get("values")
        if not isinstance(values_raw, list):
            raise ValueError(f"{field_path}.values must be a list of integers")
        values_raw_list = cast(list[object], values_raw)
        values: list[int] = []
        for idx, value in enumerate(values_raw_list):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field_path}.values[{idx}] must be an integer")
            values.append(value)
        if not values:
            raise ValueError(f"{field_path}.values must contain at least one year")
        return year_many(values)
    if kind == "raw":
        text_value = payload.get("text")
        if not isinstance(text_value, str):
            raise ValueError(f"{field_path}.text must be a string")
        text = text_value.strip()
        if not text:
            raise ValueError(f"{field_path}.text must be non-empty when kind='raw'")
        return year_raw(text)
    raise ValueError(
        f"{field_path}.kind must be one of 'unknown', 'years', or 'raw'; got {kind_value!r}"
    )


@dataclass(slots=True)
class InstitutionRecord:
    name_raw: str
    countries_raw: list[str] = field(default_factory=list)

    @property
    def country_raw_primary(self) -> str:
        if self.countries_raw:
            return self.countries_raw[0]
        return ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name_raw": self.name_raw,
            "countries_raw": list(self.countries_raw),
            "country_raw_primary": self.country_raw_primary,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        field_path: str = "institution",
    ) -> "InstitutionRecord":
        name_raw = payload.get("name_raw")
        if not isinstance(name_raw, str):
            raise ValueError(f"{field_path}.name_raw must be a string")
        countries_raw_value = payload.get("countries_raw", [])
        if not isinstance(countries_raw_value, list):
            raise ValueError(f"{field_path}.countries_raw must be a list of strings")
        countries_raw_objects = cast(list[object], countries_raw_value)
        countries_raw: list[str] = []
        for idx, country in enumerate(countries_raw_objects):
            if not isinstance(country, str):
                raise ValueError(f"{field_path}.countries_raw[{idx}] must be a string")
            countries_raw.append(country)
        return cls(
            name_raw=name_raw,
            countries_raw=countries_raw,
        )


@dataclass(slots=True)
class AdvisorRef:
    name: str
    id: str | None
    href_raw: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "id": self.id,
            "href_raw": self.href_raw,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        field_path: str = "advisor",
    ) -> "AdvisorRef":
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError(f"{field_path}.name must be a string")
        advisor_id = payload.get("id")
        if advisor_id is not None and not isinstance(advisor_id, str):
            raise ValueError(f"{field_path}.id must be a string or null")
        href_raw = payload.get("href_raw", "")
        if not isinstance(href_raw, str):
            raise ValueError(f"{field_path}.href_raw must be a string")
        return cls(
            name=name,
            id=advisor_id,
            href_raw=href_raw,
        )


@dataclass(slots=True)
class DegreeRecord:
    degree_type: str
    institutions: list[InstitutionRecord]
    year_value: YearValue
    year_text: str
    dissertation: str
    advisors: list[AdvisorRef]

    def to_dict(self) -> dict[str, object]:
        return {
            "degree_type": self.degree_type,
            "institutions": [item.to_dict() for item in self.institutions],
            "year": self.year_value,
            "year_text": self.year_text,
            "dissertation": self.dissertation,
            "advisors": [advisor.to_dict() for advisor in self.advisors],
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        field_path: str = "degree",
    ) -> "DegreeRecord":
        degree_type = payload.get("degree_type")
        if not isinstance(degree_type, str):
            raise ValueError(f"{field_path}.degree_type must be a string")
        institutions_raw = payload.get("institutions")
        if not isinstance(institutions_raw, list):
            raise ValueError(f"{field_path}.institutions must be a list")
        institutions_raw_list = cast(list[object], institutions_raw)
        institutions: list[InstitutionRecord] = []
        for idx, institution_raw in enumerate(institutions_raw_list):
            institutions.append(
                InstitutionRecord.from_dict(
                    _require_mapping(
                        institution_raw, field_path=f"{field_path}.institutions[{idx}]"
                    ),
                    field_path=f"{field_path}.institutions[{idx}]",
                )
            )
        advisors_raw = payload.get("advisors")
        if not isinstance(advisors_raw, list):
            raise ValueError(f"{field_path}.advisors must be a list")
        advisors_raw_list = cast(list[object], advisors_raw)
        advisors: list[AdvisorRef] = []
        for idx, advisor_raw in enumerate(advisors_raw_list):
            advisors.append(
                AdvisorRef.from_dict(
                    _require_mapping(
                        advisor_raw, field_path=f"{field_path}.advisors[{idx}]"
                    ),
                    field_path=f"{field_path}.advisors[{idx}]",
                )
            )
        year_text = payload.get("year_text")
        if not isinstance(year_text, str):
            raise ValueError(f"{field_path}.year_text must be a string")
        dissertation = payload.get("dissertation")
        if not isinstance(dissertation, str):
            raise ValueError(f"{field_path}.dissertation must be a string")
        return cls(
            degree_type=degree_type,
            institutions=institutions,
            year_value=_coerce_year_value(
                payload.get("year"), field_path=f"{field_path}.year"
            ),
            year_text=year_text,
            dissertation=dissertation,
            advisors=advisors,
        )


@dataclass(slots=True)
class PersonRecord:
    id: str
    name: str
    url: str
    degrees: list[DegreeRecord]
    source_snapshot: str = ""
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "degrees": [degree.to_dict() for degree in self.degrees],
            "source_snapshot": self.source_snapshot,
            "parse_warnings": list(self.parse_warnings),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        field_path: str = "person",
    ) -> "PersonRecord":
        if "students" in payload:
            raise ValueError(
                f"{field_path}.students is not supported in the advisor-only schema; regenerate artifacts"
            )
        person_id = payload.get("id")
        if not isinstance(person_id, str):
            raise ValueError(f"{field_path}.id must be a string")
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError(f"{field_path}.name must be a string")
        url = payload.get("url")
        if not isinstance(url, str):
            raise ValueError(f"{field_path}.url must be a string")
        degrees_raw = payload.get("degrees")
        if not isinstance(degrees_raw, list):
            raise ValueError(f"{field_path}.degrees must be a list")
        degrees_raw_list = cast(list[object], degrees_raw)
        degrees: list[DegreeRecord] = []
        for idx, degree_raw in enumerate(degrees_raw_list):
            degrees.append(
                DegreeRecord.from_dict(
                    _require_mapping(
                        degree_raw, field_path=f"{field_path}.degrees[{idx}]"
                    ),
                    field_path=f"{field_path}.degrees[{idx}]",
                )
            )
        source_snapshot = payload.get("source_snapshot", "")
        if not isinstance(source_snapshot, str):
            raise ValueError(f"{field_path}.source_snapshot must be a string")
        parse_warnings_raw = payload.get("parse_warnings", [])
        if not isinstance(parse_warnings_raw, list):
            raise ValueError(f"{field_path}.parse_warnings must be a list of strings")
        parse_warnings_raw_list = cast(list[object], parse_warnings_raw)
        parse_warnings: list[str] = []
        for idx, warning in enumerate(parse_warnings_raw_list):
            if not isinstance(warning, str):
                raise ValueError(f"{field_path}.parse_warnings[{idx}] must be a string")
            parse_warnings.append(warning)
        return cls(
            id=person_id,
            name=name,
            url=url,
            degrees=degrees,
            source_snapshot=source_snapshot,
            parse_warnings=parse_warnings,
        )


@dataclass(slots=True)
class EdgeRecord:
    relation_kind: str
    from_person_id: str
    to_person_id: str | None
    relation_slot: int
    relation_name_raw: str
    from_degree_index: int | None = None
    href_raw: str = ""
    institution_raw: str = ""
    year_value: YearValue = field(default_factory=year_unknown)
    year_text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "relation_kind": self.relation_kind,
            "from_person_id": self.from_person_id,
            "to_person_id": self.to_person_id,
            "relation_slot": self.relation_slot,
            "relation_name_raw": self.relation_name_raw,
            "from_degree_index": self.from_degree_index,
            "href_raw": self.href_raw,
            "institution_raw": self.institution_raw,
            "year": self.year_value,
            "year_text": self.year_text,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        field_path: str = "edge",
    ) -> "EdgeRecord":
        legacy_keys = [
            key
            for key in ("to_advisor_id", "advisor_slot", "advisor_name_raw")
            if key in payload
        ]
        if legacy_keys:
            joined = ", ".join(sorted(legacy_keys))
            raise ValueError(
                f"{field_path} uses legacy keys ({joined}); regenerate artifacts with canonical edge keys"
            )

        required_keys = (
            "relation_kind",
            "from_person_id",
            "to_person_id",
            "relation_slot",
            "relation_name_raw",
            "year",
            "year_text",
        )
        missing = [key for key in required_keys if key not in payload]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"{field_path} is missing required keys: {joined}")

        relation_kind = payload.get("relation_kind")
        if not isinstance(relation_kind, str):
            raise ValueError(f"{field_path}.relation_kind must be a string")
        from_person_id = payload.get("from_person_id")
        if not isinstance(from_person_id, str):
            raise ValueError(f"{field_path}.from_person_id must be a string")
        to_person_id_raw = payload.get("to_person_id")
        if to_person_id_raw is not None and not isinstance(to_person_id_raw, str):
            raise ValueError(f"{field_path}.to_person_id must be a string or null")
        relation_slot_raw = payload.get("relation_slot")
        if isinstance(relation_slot_raw, bool) or not isinstance(
            relation_slot_raw, int
        ):
            raise ValueError(f"{field_path}.relation_slot must be an integer")
        if relation_slot_raw < 1:
            raise ValueError(f"{field_path}.relation_slot must be >= 1")
        relation_name_raw = payload.get("relation_name_raw")
        if not isinstance(relation_name_raw, str):
            raise ValueError(f"{field_path}.relation_name_raw must be a string")

        from_degree_index_raw = payload.get("from_degree_index")
        if from_degree_index_raw is None:
            from_degree_index: int | None = None
        elif isinstance(from_degree_index_raw, bool) or not isinstance(
            from_degree_index_raw, int
        ):
            raise ValueError(
                f"{field_path}.from_degree_index must be an integer or null"
            )
        else:
            from_degree_index = from_degree_index_raw

        href_raw = payload.get("href_raw", "")
        if not isinstance(href_raw, str):
            raise ValueError(f"{field_path}.href_raw must be a string")
        institution_raw = payload.get("institution_raw", "")
        if not isinstance(institution_raw, str):
            raise ValueError(f"{field_path}.institution_raw must be a string")
        year_text = payload.get("year_text")
        if not isinstance(year_text, str):
            raise ValueError(f"{field_path}.year_text must be a string")

        return cls(
            relation_kind=relation_kind,
            from_person_id=from_person_id,
            to_person_id=to_person_id_raw,
            relation_slot=relation_slot_raw,
            relation_name_raw=relation_name_raw,
            from_degree_index=from_degree_index,
            href_raw=href_raw,
            institution_raw=institution_raw,
            year_value=_coerce_year_value(
                payload.get("year"), field_path=f"{field_path}.year"
            ),
            year_text=year_text,
        )


@dataclass(slots=True)
class GraphResult:
    start_id: str
    nodes: dict[str, PersonRecord]
    edges: list[EdgeRecord]
    visit_order: list[str]
    stats: dict[str, int]
    warnings: list[str]
    config: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "start_id": self.start_id,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "visit_order": list(self.visit_order),
            "stats": dict(self.stats),
            "warnings": list(self.warnings),
            "config": dict(self.config),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "GraphResult":  # noqa: C901
        required_keys = (
            "schema_version",
            "generator_version",
            "start_id",
            "nodes",
            "edges",
            "visit_order",
            "stats",
            "warnings",
            "config",
        )
        missing = [key for key in required_keys if key not in payload]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"graph is missing required keys: {joined}")

        schema_version_value = payload.get("schema_version")
        if not isinstance(schema_version_value, str):
            raise ValueError("graph.schema_version must be a string")
        if schema_version_value != SCHEMA_VERSION:
            raise ValueError(
                f"graph.schema_version={schema_version_value!r} is unsupported; expected {SCHEMA_VERSION!r}"
            )
        generator_version_value = payload.get("generator_version")
        if not isinstance(generator_version_value, str):
            raise ValueError("graph.generator_version must be a string")
        start_id_value = payload.get("start_id")
        if not isinstance(start_id_value, str):
            raise ValueError("graph.start_id must be a string")

        nodes_raw = payload.get("nodes")
        if not isinstance(nodes_raw, Mapping):
            raise ValueError("graph.nodes must be an object")
        nodes: dict[str, PersonRecord] = {}
        for node_id_raw, node_payload in cast(
            Mapping[object, object], nodes_raw
        ).items():
            node_id = str(node_id_raw)
            nodes[node_id] = PersonRecord.from_dict(
                _require_mapping(node_payload, field_path=f"graph.nodes[{node_id!r}]"),
                field_path=f"graph.nodes[{node_id!r}]",
            )

        edges_raw = payload.get("edges")
        if not isinstance(edges_raw, list):
            raise ValueError("graph.edges must be a list")
        edges_raw_list = cast(list[object], edges_raw)
        edges: list[EdgeRecord] = []
        for idx, edge_payload in enumerate(edges_raw_list):
            edges.append(
                EdgeRecord.from_dict(
                    _require_mapping(edge_payload, field_path=f"graph.edges[{idx}]"),
                    field_path=f"graph.edges[{idx}]",
                )
            )

        visit_order_raw = payload.get("visit_order")
        if not isinstance(visit_order_raw, list):
            raise ValueError("graph.visit_order must be a list")
        visit_order_list = cast(list[object], visit_order_raw)
        visit_order: list[str] = []
        for idx, node_id in enumerate(visit_order_list):
            if not isinstance(node_id, str):
                raise ValueError(f"graph.visit_order[{idx}] must be a string")
            visit_order.append(node_id)

        stats_raw = payload.get("stats")
        if not isinstance(stats_raw, Mapping):
            raise ValueError("graph.stats must be an object")
        stats: dict[str, int] = {}
        for key_raw, value in cast(Mapping[object, object], stats_raw).items():
            key = str(key_raw)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"graph.stats[{key!r}] must be an integer")
            stats[key] = value

        warnings_raw = payload.get("warnings")
        if not isinstance(warnings_raw, list):
            raise ValueError("graph.warnings must be a list")
        warnings_list = cast(list[object], warnings_raw)
        warnings: list[str] = []
        for idx, warning in enumerate(warnings_list):
            if not isinstance(warning, str):
                raise ValueError(f"graph.warnings[{idx}] must be a string")
            warnings.append(warning)

        config_raw = payload.get("config")
        if not isinstance(config_raw, Mapping):
            raise ValueError("graph.config must be an object")
        config = {
            str(key): value
            for key, value in cast(Mapping[object, object], config_raw).items()
        }

        return cls(
            start_id=start_id_value,
            nodes=nodes,
            edges=edges,
            visit_order=visit_order,
            stats=stats,
            warnings=warnings,
            config=config,
        )
