from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re

PARSER_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = PARSER_VERSION

YearValue = dict[str, Any]


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
    kind = value.get("kind", "unknown")
    if kind == "unknown":
        return (0, 0)
    if kind == "year":
        return (1, int(value["value"]))
    if kind == "years":
        years = [int(y) for y in value.get("values", [])]
        return (2, min(years) if years else 0)

    # raw sorts as unknown unless parseable.
    raw_text = str(value.get("text", ""))
    years = extract_numeric_years(raw_text)
    if len(years) == 1:
        return (1, years[0])
    if len(years) > 1:
        return (2, min(years))
    return (0, 0)


def normalize_person_name(name: str) -> str:
    return " ".join(name.casefold().split())


@dataclass(slots=True)
class InstitutionRecord:
    name_raw: str
    countries_raw: list[str] = field(default_factory=list)

    @property
    def country_raw_primary(self) -> str:
        if self.countries_raw:
            return self.countries_raw[0]
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name_raw": self.name_raw,
            "countries_raw": list(self.countries_raw),
            "country_raw_primary": self.country_raw_primary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InstitutionRecord":
        return cls(
            name_raw=str(payload.get("name_raw", "")),
            countries_raw=[str(v) for v in payload.get("countries_raw", [])],
        )


@dataclass(slots=True)
class AdvisorRef:
    name: str
    id: str | None
    href_raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "id": self.id,
            "href_raw": self.href_raw,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AdvisorRef":
        raw_id = payload.get("id")
        advisor_id = str(raw_id) if raw_id is not None else None
        return cls(
            name=str(payload.get("name", "Unknown")),
            id=advisor_id,
            href_raw=str(payload.get("href_raw", "")),
        )


@dataclass(slots=True)
class DegreeRecord:
    degree_type: str
    institutions: list[InstitutionRecord]
    year_value: YearValue
    year_text: str
    dissertation: str
    advisors: list[AdvisorRef]

    def to_dict(self) -> dict[str, Any]:
        return {
            "degree_type": self.degree_type,
            "institutions": [item.to_dict() for item in self.institutions],
            "year": self.year_value,
            "year_text": self.year_text,
            "dissertation": self.dissertation,
            "advisors": [advisor.to_dict() for advisor in self.advisors],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DegreeRecord":
        year_value = payload.get("year", {"kind": "unknown"})
        return cls(
            degree_type=str(payload.get("degree_type", "")),
            institutions=[InstitutionRecord.from_dict(v) for v in payload.get("institutions", [])],
            year_value=dict(year_value),
            year_text=str(payload.get("year_text", "")),
            dissertation=str(payload.get("dissertation", "")),
            advisors=[AdvisorRef.from_dict(v) for v in payload.get("advisors", [])],
        )


@dataclass(slots=True)
class PersonRecord:
    id: str
    name: str
    url: str
    degrees: list[DegreeRecord]
    source_snapshot: str = ""
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "degrees": [degree.to_dict() for degree in self.degrees],
            "source_snapshot": self.source_snapshot,
            "parse_warnings": list(self.parse_warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersonRecord":
        return cls(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "Unknown")),
            url=str(payload.get("url", "")),
            degrees=[DegreeRecord.from_dict(v) for v in payload.get("degrees", [])],
            source_snapshot=str(payload.get("source_snapshot", "")),
            parse_warnings=[str(v) for v in payload.get("parse_warnings", [])],
        )


@dataclass(slots=True)
class EdgeRecord:
    from_person_id: str
    to_advisor_id: str | None
    from_degree_index: int
    advisor_slot: int
    advisor_name_raw: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_person_id": self.from_person_id,
            "to_advisor_id": self.to_advisor_id,
            "from_degree_index": self.from_degree_index,
            "advisor_slot": self.advisor_slot,
            "advisor_name_raw": self.advisor_name_raw,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EdgeRecord":
        to_advisor_id = payload.get("to_advisor_id")
        return cls(
            from_person_id=str(payload.get("from_person_id", "")),
            to_advisor_id=str(to_advisor_id) if to_advisor_id is not None else None,
            from_degree_index=int(payload.get("from_degree_index", 0)),
            advisor_slot=int(payload.get("advisor_slot", 1)),
            advisor_name_raw=str(payload.get("advisor_name_raw", "Unknown")),
        )


@dataclass(slots=True)
class GraphResult:
    start_id: str
    nodes: dict[str, PersonRecord]
    edges: list[EdgeRecord]
    visit_order: list[str]
    stats: dict[str, Any]
    warnings: list[str]
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
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
