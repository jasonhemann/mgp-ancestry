from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Literal, TypedDict, cast

PARSER_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = PARSER_VERSION


class YearUnknown(TypedDict):
    kind: Literal["unknown"]


class YearSingle(TypedDict):
    kind: Literal["year"]
    value: int


class YearMany(TypedDict):
    kind: Literal["years"]
    values: list[int]


class YearRaw(TypedDict):
    kind: Literal["raw"]
    text: str


type YearValue = YearUnknown | YearSingle | YearMany | YearRaw


def year_unknown() -> YearValue:
    return {"kind": "unknown"}


def year_single(value: int) -> YearValue:
    return {"kind": "year", "value": int(value)}


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
    if len(numeric_years) == 1:
        return year_single(numeric_years[0])
    if len(numeric_years) > 1:
        return year_many(numeric_years)
    if raw_text.strip():
        return year_raw(raw_text.strip())
    return year_unknown()


def year_value_sort_key(value: YearValue) -> tuple[int, int]:
    kind = value["kind"]
    if kind == "unknown":
        return (0, 0)
    if kind == "year":
        year_value = cast(YearSingle, value)
        return (1, int(year_value["value"]))
    if kind == "years":
        years_value = cast(YearMany, value)
        years = [int(y) for y in years_value["values"]]
        return (2, min(years) if years else 0)

    raw_value = cast(YearRaw, value)
    raw_text = raw_value["text"]
    years = extract_numeric_years(raw_text)
    if len(years) == 1:
        return (1, years[0])
    if len(years) > 1:
        return (2, min(years))
    return (0, 0)


def normalize_person_name(name: str) -> str:
    return " ".join(name.casefold().split())


def _coerce_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
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
        list_value = cast(list[object], value)
        return list(list_value)
    if isinstance(value, tuple):
        tuple_value = cast(tuple[object, ...], value)
        return list(tuple_value)
    return []


def _coerce_year_value(raw_value: object) -> YearValue:
    payload = _as_mapping(raw_value)
    kind = _coerce_str(payload.get("kind"), "unknown")
    if kind == "year":
        return year_single(_coerce_int(payload.get("value"), 0))
    if kind == "years":
        values = [_coerce_int(v, 0) for v in _as_object_list(payload.get("values"))]
        return year_many(values)
    if kind == "raw":
        return year_raw(_coerce_str(payload.get("text"), ""))
    return year_unknown()


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
    def from_dict(cls, payload: Mapping[str, object]) -> "InstitutionRecord":
        return cls(
            name_raw=_coerce_str(payload.get("name_raw"), ""),
            countries_raw=[_coerce_str(v) for v in _as_object_list(payload.get("countries_raw"))],
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
    def from_dict(cls, payload: Mapping[str, object]) -> "AdvisorRef":
        return cls(
            name=_coerce_str(payload.get("name"), "Unknown"),
            id=_coerce_optional_str(payload.get("id")),
            href_raw=_coerce_str(payload.get("href_raw"), ""),
        )


@dataclass(slots=True)
class StudentRef:
    name: str
    id: str | None
    href_raw: str = ""
    school_raw: str = ""
    year_value: YearValue = field(default_factory=year_unknown)
    year_text: str = ""
    descendants_text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "id": self.id,
            "href_raw": self.href_raw,
            "school_raw": self.school_raw,
            "year": self.year_value,
            "year_text": self.year_text,
            "descendants_text": self.descendants_text,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "StudentRef":
        year_value = _coerce_year_value(payload.get("year"))
        return cls(
            name=_coerce_str(payload.get("name"), "Unknown"),
            id=_coerce_optional_str(payload.get("id")),
            href_raw=_coerce_str(payload.get("href_raw"), ""),
            school_raw=_coerce_str(payload.get("school_raw"), ""),
            year_value=year_value,
            year_text=_coerce_str(payload.get("year_text"), ""),
            descendants_text=_coerce_str(payload.get("descendants_text"), ""),
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
    def from_dict(cls, payload: Mapping[str, object]) -> "DegreeRecord":
        institutions = [
            InstitutionRecord.from_dict(_as_mapping(v))
            for v in _as_object_list(payload.get("institutions"))
        ]
        advisors = [AdvisorRef.from_dict(_as_mapping(v)) for v in _as_object_list(payload.get("advisors"))]
        return cls(
            degree_type=_coerce_str(payload.get("degree_type"), ""),
            institutions=institutions,
            year_value=_coerce_year_value(payload.get("year")),
            year_text=_coerce_str(payload.get("year_text"), ""),
            dissertation=_coerce_str(payload.get("dissertation"), ""),
            advisors=advisors,
        )


@dataclass(slots=True)
class PersonRecord:
    id: str
    name: str
    url: str
    degrees: list[DegreeRecord]
    students: list[StudentRef] = field(default_factory=list)
    source_snapshot: str = ""
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "degrees": [degree.to_dict() for degree in self.degrees],
            "students": [student.to_dict() for student in self.students],
            "source_snapshot": self.source_snapshot,
            "parse_warnings": list(self.parse_warnings),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "PersonRecord":
        degrees = [DegreeRecord.from_dict(_as_mapping(v)) for v in _as_object_list(payload.get("degrees"))]
        students = [StudentRef.from_dict(_as_mapping(v)) for v in _as_object_list(payload.get("students"))]
        parse_warnings = [_coerce_str(v) for v in _as_object_list(payload.get("parse_warnings"))]
        return cls(
            id=_coerce_str(payload.get("id"), ""),
            name=_coerce_str(payload.get("name"), "Unknown"),
            url=_coerce_str(payload.get("url"), ""),
            degrees=degrees,
            students=students,
            source_snapshot=_coerce_str(payload.get("source_snapshot"), ""),
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
    def from_dict(cls, payload: Mapping[str, object]) -> "EdgeRecord":
        target = payload.get("to_person_id")
        if target is None:
            target = payload.get("to_advisor_id")

        relation_kind = _coerce_str(payload.get("relation_kind"), "advisor")
        if "to_advisor_id" in payload and "relation_kind" not in payload:
            relation_kind = "advisor"

        relation_slot_raw = payload.get("relation_slot")
        if relation_slot_raw is None:
            relation_slot_raw = payload.get("advisor_slot", 1)

        from_degree_index_raw = payload.get("from_degree_index")
        from_degree_index = (
            _coerce_int(from_degree_index_raw) if from_degree_index_raw is not None else None
        )

        return cls(
            relation_kind=relation_kind,
            from_person_id=_coerce_str(payload.get("from_person_id"), ""),
            to_person_id=_coerce_optional_str(target),
            relation_slot=_coerce_int(relation_slot_raw, 1),
            relation_name_raw=_coerce_str(
                payload.get("relation_name_raw", payload.get("advisor_name_raw", "Unknown")),
                "Unknown",
            ),
            from_degree_index=from_degree_index,
            href_raw=_coerce_str(payload.get("href_raw"), ""),
            institution_raw=_coerce_str(payload.get("institution_raw"), ""),
            year_value=_coerce_year_value(payload.get("year")),
            year_text=_coerce_str(payload.get("year_text"), ""),
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
    def from_dict(cls, payload: dict[str, Any]) -> "GraphResult":
        return cls(
            start_id=str(payload.get("start_id", "")),
            nodes={
                str(node_id): PersonRecord.from_dict(node_payload)
                for node_id, node_payload in payload.get("nodes", {}).items()
            },
            edges=[EdgeRecord.from_dict(edge_payload) for edge_payload in payload.get("edges", [])],
            visit_order=[str(node_id) for node_id in payload.get("visit_order", [])],
            stats=dict(payload.get("stats", {})),
            warnings=[str(warning) for warning in payload.get("warnings", [])],
            config=dict(payload.get("config", {})),
        )
