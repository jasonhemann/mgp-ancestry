from __future__ import annotations

from bs4 import BeautifulSoup

from genealogy_tree.parser import extract_name, parse_person_html


def test_extract_name_fallback_to_title():
    html = "<html><head><title>Only Title - The Mathematics Genealogy Project</title></head><body></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert extract_name(soup) == "Only Title"


def test_parse_no_degree_blocks_warning():
    html = "<html><head><title>No Degree - The Mathematics Genealogy Project</title></head><body><h2>No Degree</h2></body></html>"
    person = parse_person_html(html, person_id="x")
    payload = person.to_dict()
    assert payload["degrees"] == []
    assert "No modern degree blocks found on page." in payload["parse_warnings"]


def test_parse_country_institution_mismatch_warning():
    html = """
    <html>
      <body>
        <h2 style="text-align: center;">Mismatch Person</h2>
        <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
          <span>Ph.D. <span style="color:#006633">Alpha University and Beta University</span> 1900</span>
          <img alt="CountryX" />
          <img alt="CountryY" />
          <img alt="CountryZ" />
        </div>
        <div style="text-align: center"><span id="thesisTitle">Thesis</span></div>
        <p style="text-align: center">Advisor text without links</p>
      </body>
    </html>
    """
    person = parse_person_html(html, person_id="x")
    payload = person.to_dict()
    assert payload["degrees"][0]["advisors"][0]["id"] is None
    assert any("Country/institution count mismatch" in warning for warning in payload["parse_warnings"])


def test_parse_57670_multi_advisor(load_fixture_html):
    person = parse_person_html(load_fixture_html("57670"), person_id="57670")
    payload = person.to_dict()

    assert payload["id"] == "57670"
    assert payload["name"] == "Christian August Hausen"
    assert len(payload["degrees"]) == 1
    advisors = payload["degrees"][0]["advisors"]
    assert [advisor["id"] for advisor in advisors] == ["72669", "128986"]


def test_parse_128986_multiple_degrees(load_fixture_html):
    person = parse_person_html(load_fixture_html("128986"), person_id="128986")
    payload = person.to_dict()
    assert payload["name"] == "Johann Andreas Planer"
    assert len(payload["degrees"]) == 2
    assert payload["degrees"][0]["year"]["kind"] == "year"
    assert payload["degrees"][0]["year"]["value"] == 1686
    assert payload["degrees"][1]["dissertation"].startswith("Disputatio medica inauguralis")


def test_parse_47025_multi_institution_multi_country(load_fixture_html):
    person = parse_person_html(load_fixture_html("47025"), person_id="47025")
    degree = person.to_dict()["degrees"][0]
    institutions = degree["institutions"]

    assert len(institutions) == 3
    assert institutions[0]["name_raw"] == "Georg-August-Universität Göttingen"
    assert institutions[1]["name_raw"] == "Justus-Liebig-Universität Gießen"
    assert institutions[2]["name_raw"] == "Universität Erfurt"
    assert [inst["country_raw_primary"] for inst in institutions] == ["Germany", "Germany", "Germany"]


def test_parse_129079_unknown_advisor(load_fixture_html):
    person = parse_person_html(load_fixture_html("129079"), person_id="129079")
    payload = person.to_dict()
    assert len(payload["degrees"]) == 4
    unknown_advisor = payload["degrees"][3]["advisors"][0]
    assert unknown_advisor["name"] == "Unknown"
    assert unknown_advisor["id"] is None


def test_parse_128938_multi_year_value(load_fixture_html):
    person = parse_person_html(load_fixture_html("128938"), person_id="128938")
    degree = person.to_dict()["degrees"][0]
    year_value = degree["year"]
    assert year_value["kind"] == "years"
    assert year_value["values"] == [1684, 1686]


def test_no_null_year_values(load_fixture_html):
    for person_id in ("57670", "75750", "128986", "47025", "129079", "128938"):
        person = parse_person_html(load_fixture_html(person_id), person_id=person_id)
        payload = person.to_dict()
        for degree in payload["degrees"]:
            year_value = degree["year"]
            assert isinstance(year_value, dict)
            assert "kind" in year_value
