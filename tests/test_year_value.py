from __future__ import annotations

from genealogy_tree.models import year_many, year_raw, year_unknown, year_value_sort_key


def test_year_value_sorting_contract():
    values = [
        year_many([1900]),
        year_unknown(),
        year_many([1950, 1940]),
        year_raw("unknown"),
    ]
    sorted_values = sorted(values, key=year_value_sort_key)
    assert sorted_values[0]["kind"] in {"unknown", "raw"}
    assert sorted_values[-1]["kind"] == "years"
