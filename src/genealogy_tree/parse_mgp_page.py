import re
import requests
from bs4 import BeautifulSoup


def parse_mgp_page(page_html):
    """
    Extract from a single MGP page HTML:
      {
        "name": str,
        "degrees": [
          {
            "degree_type": str,                # E.g. "Dr. phil.", "Magister artium", ...
            "universities": [                  # Each entry: {"name": "some Uni", "country": "Germany"}
              {"name": str, "country": str or None},
              ...
            ],
            "year": str or None,               # E.g. "1853"
            "dissertation": str or None,       # Dissertation title (if present)
            "advisors": [
              { "name": str, "id": str or None },
              ...
            ]
          },
          ...
        ]
      }
    """

    soup = BeautifulSoup(page_html, "html.parser")

    # 1) Person's name
    # Usually inside <h2 style="text-align: center; ...">
    h2_tag = soup.find("h2", style=re.compile(r"text-align:\s*center"))
    name = h2_tag.get_text(strip=True) if h2_tag else "Unknown"

    # 2) Parse each "degree block" -- typically:
    #     <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
    #        <span> Dr. phil. <span>Universität X and Universität Y</span> 1853</span>
    #        <img ... alt="Germany" .../>
    #        <img ... alt="Germany" .../>
    #     </div>
    #
    # Followed by:
    #     <div style="text-align: center">Dissertation: <span id="thesisTitle">...</span></div>
    #     <p>Advisor 1: <a href="id.php?id=XXXX">Name</a> ...</p>
    #     <p>Advisor 2: <a href="id.php?id=YYYY">Name</a> ...</p>
    #
    # Then possibly another <div ...> for the next degree, or "Students:" block, or nothing.

    degree_divs = soup.find_all(
        "div",
        style=lambda s: s and "line-height: 30px" in s and "text-align: center" in s
    )

    degrees = []

    # We'll iterate each "degree block," then read subsequent siblings
    # until we either see the next degree block or a "Students:" block or run out of siblings.
    # In that gap, we look for "Dissertation:" and "Advisor" blocks.
    for i, deg_div in enumerate(degree_divs):
        # Parse the main text of the degree block
        # e.g. "Dr. phil. Universität Berlin 1853"
        raw_text = deg_div.get_text(" ", strip=True)

        # Gather country flags (one for each university, typically)
        flag_imgs = deg_div.find_all("img", alt=True)
        countries = [img["alt"].strip() for img in flag_imgs]

        # The <span style="color:#006633"> typically holds the universities
        uni_span = deg_div.find("span", style=re.compile(r"color:\s*#006633"))
        if uni_span:
            universities_text = uni_span.get_text(" ", strip=True)
        else:
            universities_text = ""

        # Extract a 4-digit year if present
        match_year = re.search(r"\b(\d{4})\b", raw_text)
        year = match_year.group(1) if match_year else None

        # Heuristic to get the degree type (the text *before* the universities)
        # We'll remove the year from that portion if it appears.
        if universities_text in raw_text:
            start_idx = raw_text.index(universities_text)
            degree_type_candidate = raw_text[:start_idx].strip()
            # remove any embedded year
            degree_type_candidate = re.sub(r"\b\d{4}\b", "", degree_type_candidate).strip()
            degree_type = degree_type_candidate
        else:
            # fallback if the structure is unusual
            degree_type = raw_text

        # Split the universities text on "and" for multiple universities
        uni_list = [u.strip() for u in universities_text.split(" and ")] if universities_text else []

        # Pair them with the countries we found
        universities = []
        for idx, uni_name in enumerate(uni_list):
            ctry = countries[idx] if idx < len(countries) else None
            universities.append({"name": uni_name, "country": ctry})

        # We'll now read siblings until we see the next "degree block" or "Students:" block, or no more siblings
        # Searching for:
        #   (1) <div> containing "Dissertation:"
        #   (2) <p> or <div> containing "Advisor"
        dissertation = None
        advisors = []
        sibling = deg_div.next_sibling

        while sibling:
            # Some siblings might be strings, newlines, or empty tags.
            # let's skip those
            if sibling.name in ["div", "p"]:
                text = sibling.get_text(" ", strip=True).lower() if sibling else ""
                # If this is the next degree block, break
                if sibling.name == "div" and sibling.has_attr("style"):
                    style_val = sibling["style"]
                    if "line-height: 30px" in style_val and "text-align: center" in style_val:
                        # It's another degree block => break
                        break
                # If we see "students:" we break
                if "students:" in text:
                    break
                # If there's "dissertation:" in text, parse the actual title from <span id="thesisTitle">
                if "dissertation:" in text:
                    thesis_span = sibling.find("span", id="thesisTitle")
                    if thesis_span:
                        tmp = thesis_span.get_text(" ", strip=True)
                        # MGP sometimes puts "(none)" or an empty string
                        if tmp and tmp.lower() != "(none)":
                            dissertation = tmp
                # If there's "advisor" in text, parse each <a> link
                if "advisor" in text:
                    # Usually something like: "Advisor 1: <a href="id.php?id=XXXX">Name</a>"
                    a_tags = sibling.find_all("a", href=True)
                    if a_tags:
                        for a in a_tags:
                            adv_name = a.get_text(strip=True)
                            adv_href = a["href"]
                            # If it's a link like "id.php?id=128046", extract just the numeric ID
                            if "id.php?id=" in adv_href:
                                parts = adv_href.split("id.php?id=")
                                adv_id = parts[1] if len(parts) == 2 else None
                            else:
                                adv_id = None
                            advisors.append({"name": adv_name, "id": adv_id})
                    else:
                        # Possibly "Advisor: Unknown"
                        if "unknown" in text:
                            advisors.append({"name": "Unknown", "id": None})
                        else:
                            # fallback
                            advisors.append({"name": sibling.get_text(" ", strip=True), "id": None})

            sibling = sibling.next_sibling

        degree_info = {
            "degree_type": degree_type.strip() if degree_type else None,
            "universities": universities,
            "year": year,
            "dissertation": dissertation,
            "advisors": advisors
        }
        degrees.append(degree_info)

    return {
        "name": name,
        "degrees": degrees
    }


def fetch_and_parse_mgp(id_number):
    """
    Fetch a single MGP page by ID and parse it into a structured dict
    using parse_mgp_page.
    """
    base_url = "https://genealogy.math.ndsu.nodak.edu/id.php?id="
    url = f"{base_url}{id_number}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()  # raise exception if 4xx/5xx
    return parse_mgp_page(resp.text)


if __name__ == "__main__":
    # Example: test on Johann Andreas Planer (id=128986)
    example_id = 128986
    data = fetch_and_parse_mgp(example_id)
    import json
    print(json.dumps(data, indent=2, ensure_ascii=False))
