from __future__ import annotations

from genealogy_tree.parser import parse_person_html


def test_person_record_contract(load_fixture_html):
    payload = parse_person_html(load_fixture_html("75750"), person_id="75750").to_dict()
    assert set(payload.keys()) == {
        "id",
        "name",
        "url",
        "degrees",
        "source_snapshot",
        "parse_warnings",
    }

    degree = payload["degrees"][0]
    required_degree_keys = {
        "degree_type",
        "institutions",
        "year",
        "year_text",
        "dissertation",
        "advisors",
    }
    assert required_degree_keys.issubset(degree.keys())
    assert degree["year"]["kind"] in {"unknown", "year", "years", "raw"}


def test_institution_contract(load_fixture_html):
    payload = parse_person_html(load_fixture_html("47025"), person_id="47025").to_dict()
    institution = payload["degrees"][0]["institutions"][0]
    assert set(institution.keys()) == {"name_raw", "countries_raw", "country_raw_primary"}
