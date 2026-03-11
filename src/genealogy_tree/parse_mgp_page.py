from __future__ import annotations

import json

from .fetch import fetch_with_retries
from .parser import parse_person_html

BASE_URL = "https://genealogy.math.ndsu.nodak.edu/id.php?id="


def parse_mgp_page(page_html: str) -> dict:
    """
    Compatibility function retained for older imports.
    Parses a single MGP page HTML and returns a dictionary payload.
    """
    return parse_person_html(page_html).to_dict()


def fetch_and_parse_mgp(id_number: int | str) -> dict:
    """
    Compatibility function retained for older imports.
    Fetches a single MGP page by ID and parses it.
    """
    person_id = str(id_number)
    url = f"{BASE_URL}{person_id}"
    fetch_result = fetch_with_retries(url)
    return parse_person_html(fetch_result.text, person_id=person_id, url=fetch_result.url).to_dict()


if __name__ == "__main__":
    example_id = "128986"
    data = fetch_and_parse_mgp(example_id)
    print(json.dumps(data, indent=2, ensure_ascii=False))
