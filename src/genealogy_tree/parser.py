from __future__ import annotations

import re
from bs4 import BeautifulSoup
from bs4.element import Tag

from .models import (
    AdvisorRef,
    DegreeRecord,
    InstitutionRecord,
    PersonRecord,
    StudentRef,
    extract_numeric_years,
    make_year_value,
)

MGP_TITLE_SUFFIX = " - The Mathematics Genealogy Project"
MGP_ID_REGEX = re.compile(r"id\.php\?id=(\d+)")


def extract_name(soup: BeautifulSoup) -> str:
    centered_h2 = soup.find("h2", style=re.compile(r"text-align\s*:\s*center", re.I))
    if centered_h2:
        text = centered_h2.get_text(" ", strip=True)
        if text:
            return text

    first_h2 = soup.find("h2")
    if first_h2:
        text = first_h2.get_text(" ", strip=True)
        if text:
            return text

    title = soup.find("title")
    if title:
        title_text = title.get_text(" ", strip=True)
        if title_text.endswith(MGP_TITLE_SUFFIX):
            title_text = title_text[: -len(MGP_TITLE_SUFFIX)]
        if title_text:
            return title_text.strip()

    return "Unknown"


def _is_degree_block(tag: Tag) -> bool:
    if tag.name != "div":
        return False
    style = tag.attrs.get("style", "")
    if not isinstance(style, str):
        return False
    return "line-height: 30px" in style and "text-align: center" in style


def _split_top_level_and(text: str) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    current: list[str] = []
    depth = 0
    idx = 0
    marker = " and "
    while idx < len(text):
        char = text[idx]
        if char == "(":
            depth += 1
            current.append(char)
            idx += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            current.append(char)
            idx += 1
            continue
        if depth == 0 and text.startswith(marker, idx):
            part = "".join(current).strip()
            if part:
                chunks.append(part)
            current = []
            idx += len(marker)
            continue
        current.append(char)
        idx += 1

    tail = "".join(current).strip()
    if tail:
        chunks.append(tail)
    return chunks


def _extract_year_text(raw_text: str, universities_text: str) -> str:
    if universities_text and universities_text in raw_text:
        return raw_text.split(universities_text, 1)[1].strip(" ,;")
    return raw_text.strip()


def _parse_institutions(
    universities_text: str,
    countries_raw: list[str],
    parse_warnings: list[str],
) -> list[InstitutionRecord]:
    parts = _split_top_level_and(universities_text)
    if not parts and universities_text.strip():
        parts = [universities_text.strip()]
    if not parts:
        return []

    institutions: list[InstitutionRecord] = [InstitutionRecord(name_raw=part, countries_raw=[]) for part in parts]
    if not countries_raw:
        return institutions

    if len(parts) == len(countries_raw):
        for idx, institution in enumerate(institutions):
            institution.countries_raw = [countries_raw[idx]]
        return institutions

    parse_warnings.append(
        "Country/institution count mismatch for degree block: "
        f"{len(parts)} institution names vs {len(countries_raw)} country flags."
    )

    if len(parts) == 1:
        institutions[0].countries_raw = list(countries_raw)
        return institutions

    if len(countries_raw) == 1:
        for institution in institutions:
            institution.countries_raw = [countries_raw[0]]
        return institutions

    for institution in institutions:
        institution.countries_raw = list(countries_raw)
    return institutions


def _parse_degree_siblings(degree_div: Tag) -> tuple[str, list[AdvisorRef]]:
    dissertation = ""
    advisors: list[AdvisorRef] = []

    for sibling in degree_div.next_siblings:
        sibling_name = getattr(sibling, "name", None)
        if sibling_name not in ("div", "p"):
            continue
        sibling_tag = sibling
        if not isinstance(sibling_tag, Tag):
            continue

        text = sibling_tag.get_text(" ", strip=True)
        lower_text = text.lower()

        if _is_degree_block(sibling_tag):
            break
        if "students:" in lower_text:
            break

        if "dissertation:" in lower_text:
            thesis_span = sibling_tag.find("span", id="thesisTitle")
            if thesis_span:
                value = thesis_span.get_text(" ", strip=True)
            else:
                value = re.sub(r"(?i)^.*dissertation:\s*", "", text).strip()
            if value and value.lower() != "(none)":
                dissertation = value

        if "advisor" in lower_text:
            advisor_links = sibling_tag.find_all("a", href=True)
            if advisor_links:
                for link in advisor_links:
                    href_raw = str(link.attrs.get("href", "")).strip()
                    name = link.get_text(" ", strip=True)
                    id_match = MGP_ID_REGEX.search(href_raw)
                    advisor_id = id_match.group(1) if id_match else None
                    advisors.append(AdvisorRef(name=name or "Unknown", id=advisor_id, href_raw=href_raw))
            elif "unknown" in lower_text:
                advisors.append(AdvisorRef(name="Unknown", id=None, href_raw=""))
            else:
                fallback = text.strip() or "Unknown"
                advisors.append(AdvisorRef(name=fallback, id=None, href_raw=""))

    return dissertation, advisors


def _parse_students(soup: BeautifulSoup) -> list[StudentRef]:
    students_header = None
    for paragraph in soup.find_all("p"):
        if not isinstance(paragraph, Tag):
            continue
        text = paragraph.get_text(" ", strip=True).lower()
        if "students:" in text:
            students_header = paragraph
            break

    if students_header is None:
        return []

    table = students_header.find_next("table")
    if table is None or not isinstance(table, Tag):
        return []

    students: list[StudentRef] = []
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        if row.find("th") is not None:
            continue

        cells = row.find_all("td")
        if not cells:
            continue

        name_cell = cells[0]
        name_link = name_cell.find("a", href=True)
        href_raw = ""
        student_id: str | None = None
        if name_link:
            href_raw = str(name_link.attrs.get("href", "")).strip()
            id_match = MGP_ID_REGEX.search(href_raw)
            student_id = id_match.group(1) if id_match else None
            name = name_link.get_text(" ", strip=True) or name_cell.get_text(" ", strip=True) or "Unknown"
        else:
            name = name_cell.get_text(" ", strip=True) or "Unknown"

        school_raw = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""
        year_text = cells[2].get_text(" ", strip=True) if len(cells) > 2 else ""
        descendants_text = cells[3].get_text(" ", strip=True) if len(cells) > 3 else ""
        year_value = make_year_value(year_text, extract_numeric_years(year_text))

        students.append(
            StudentRef(
                name=name,
                id=student_id,
                href_raw=href_raw,
                school_raw=school_raw,
                year_value=year_value,
                year_text=year_text,
                descendants_text=descendants_text,
            )
        )

    return students


def parse_person_html(
    page_html: str,
    *,
    person_id: str = "",
    url: str = "",
    source_snapshot: str = "",
) -> PersonRecord:
    soup = BeautifulSoup(page_html, "html.parser")
    parse_warnings: list[str] = []
    name = extract_name(soup)

    degree_divs = soup.find_all("div", style=lambda s: isinstance(s, str) and "line-height: 30px" in s and "text-align: center" in s)

    degrees: list[DegreeRecord] = []
    for degree_div in degree_divs:
        if not isinstance(degree_div, Tag):
            continue
        raw_text = degree_div.get_text(" ", strip=True)
        flag_tags = degree_div.find_all("img", alt=True)
        countries = [str(tag.attrs.get("alt", "")).strip() for tag in flag_tags if str(tag.attrs.get("alt", "")).strip()]

        uni_span = degree_div.find("span", style=re.compile(r"color\s*:\s*#006633", re.I))
        universities_text = uni_span.get_text(" ", strip=True) if uni_span else ""

        institutions = _parse_institutions(universities_text, countries, parse_warnings)

        if universities_text and universities_text in raw_text:
            degree_type = raw_text.split(universities_text, 1)[0].strip()
        else:
            degree_type = raw_text.strip()
        degree_type = re.sub(r"\b\d{4}\b", "", degree_type).strip()

        year_text = _extract_year_text(raw_text, universities_text)
        year_numbers = extract_numeric_years(raw_text)
        year_value = make_year_value(year_text, year_numbers)

        dissertation, advisors = _parse_degree_siblings(degree_div)
        degrees.append(
            DegreeRecord(
                degree_type=degree_type,
                institutions=institutions,
                year_value=year_value,
                year_text=year_text,
                dissertation=dissertation,
                advisors=advisors,
            )
        )

    if not degree_divs:
        parse_warnings.append("No modern degree blocks found on page.")
    students = _parse_students(soup)

    return PersonRecord(
        id=str(person_id or ""),
        name=name,
        url=url,
        degrees=degrees,
        students=students,
        source_snapshot=source_snapshot,
        parse_warnings=parse_warnings,
    )
