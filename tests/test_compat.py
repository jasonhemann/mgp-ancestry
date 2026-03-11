from __future__ import annotations

import importlib

from genealogy_tree.fetch import FetchResult
from genealogy_tree.parse_mgp_page import fetch_and_parse_mgp, parse_mgp_page


def test_parse_mgp_page_compat_shape(load_fixture_html):
    payload = parse_mgp_page(load_fixture_html("75750"))
    assert payload["name"] == "Daniel Paul Friedman"
    assert "degrees" in payload
    assert "institutions" in payload["degrees"][0]
    assert "year" in payload["degrees"][0]


def test_fetch_and_parse_wrapper(monkeypatch, load_fixture_html):
    fixture_html = load_fixture_html("57670")
    module = importlib.import_module("genealogy_tree.parse_mgp_page")

    def fake_fetch(url: str):
        return FetchResult(text=fixture_html, status_code=200, url=url)

    monkeypatch.setattr(module, "fetch_with_retries", fake_fetch)
    payload = fetch_and_parse_mgp("57670")
    assert payload["id"] == "57670"
    assert payload["name"] == "Christian August Hausen"
    assert payload["url"].endswith("id.php?id=57670")
