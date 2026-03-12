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
        <p style="text-align: center">Advisor: text without links</p>
      </body>
    </html>
    """
    person = parse_person_html(html, person_id="x")
    payload = person.to_dict()
    assert payload["degrees"][0]["advisors"][0]["id"] is None
    assert any(
        "Country/institution count mismatch" in warning
        for warning in payload["parse_warnings"]
    )


def test_parse_advisor_line_ignores_footer_advisor_id_links():
    html = """
    <html>
      <body>
        <h2 style="text-align: center;">Footer Noise Person</h2>
        <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
          <span>Ph.D. <span style="color:#006633">Alpha University</span> 2000</span>
          <img alt="CountryX" />
        </div>
        <div style="text-align: center"><span id="thesisTitle">Thesis</span></div>
        <p style="text-align: center; line-height: 2.75ex">
          Advisor: <a href="id.php?id=12345">Real Advisor</a><br />
        </p>
        <p style="font-size: small; text-align: center">
          If you have additional information, use the
          <a href="submit-data.php?id=999&edit=0">update form</a>.
          To submit students, use the
          <a href="submit-data.php?id=NEW&edit=0">new data form</a>,
          noting this mathematician's MGP ID of 999 for the advisor ID.
        </p>
      </body>
    </html>
    """
    person = parse_person_html(html, person_id="x")
    payload = person.to_dict()
    advisors = payload["degrees"][0]["advisors"]
    assert advisors == [
        {"name": "Real Advisor", "id": "12345", "href_raw": "id.php?id=12345"}
    ]


def test_parse_129079_multi_degree_multi_advisor_unknown_advisor(load_fixture_html):
    person = parse_person_html(load_fixture_html("129079"), person_id="129079")
    payload = person.to_dict()

    assert payload["id"] == "129079"
    assert payload["name"] == "Johannes Fridericus Weidlerus"
    assert len(payload["degrees"]) == 4
    assert [advisor["id"] for advisor in payload["degrees"][1]["advisors"]] == [
        "198623",
        "125886",
    ]
    unknown_advisor = payload["degrees"][3]["advisors"][0]
    assert unknown_advisor["name"] == "Unknown"
    assert unknown_advisor["id"] is None


def test_parse_47025_multi_institution_multi_country(load_fixture_html):
    person = parse_person_html(load_fixture_html("47025"), person_id="47025")
    degree = person.to_dict()["degrees"][0]
    institutions = degree["institutions"]

    assert len(institutions) == 3
    assert institutions[0]["name_raw"] == "Georg-August-Universität Göttingen"
    assert institutions[1]["name_raw"] == "Justus-Liebig-Universität Gießen"
    assert institutions[2]["name_raw"] == "Universität Erfurt"
    assert [inst["country_raw_primary"] for inst in institutions] == [
        "Germany",
        "Germany",
        "Germany",
    ]


def test_parse_128938_multi_year_value(load_fixture_html):
    person = parse_person_html(load_fixture_html("128938"), person_id="128938")
    degree = person.to_dict()["degrees"][0]
    year_value = degree["year"]
    assert year_value["kind"] == "years"
    assert year_value["values"] == [1684, 1686]


def test_no_null_year_values(load_fixture_html):
    for person_id in ("47025", "129079", "128938"):
        person = parse_person_html(load_fixture_html(person_id), person_id=person_id)
        payload = person.to_dict()
        for degree in payload["degrees"]:
            year_value = degree["year"]
            assert isinstance(year_value, dict)
            assert "kind" in year_value


def test_fixture_parsing_excludes_footer_form_links(load_fixture_html):
    person = parse_person_html(load_fixture_html("129079"), person_id="129079")
    payload = person.to_dict()
    advisor_names = [
        advisor["name"]
        for degree in payload["degrees"]
        for advisor in degree["advisors"]
    ]
    assert "update form" not in advisor_names
    assert "new data form" not in advisor_names
