"""
Parameter sorting module.

Reorders citation parameters according to Wikipedia conventions:
authors → translators → date → editors → title → work → URL → volume/issue
→ publisher → pages → identifiers → archive → access → quote → misc
"""

import re

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult


# Priority order — lower number = earlier position
# Based on the full parameter set documented at Template:Cite journal
_PRIORITY = {
    # Authors
    "vauthors": 10,
    "last": 20,
    "first": 21,
    "author-link": 22,
    "display-authors": 23,
    "author-mask": 24,
    "author": 25,
    "collaboration": 26,
    # Date
    "df": 50,
    "date": 51,
    "year": 52,
    "orig-date": 53,
    "location": 55,
    "publication-place": 55,
    # Editors
    "veditors": 60,
    "editor-last": 61,
    "editor-first": 62,
    "editor-link": 63,
    "display-editors": 64,
    "editor-mask": 65,
    # Title
    "title": 80,
    "script-title": 81,
    "title-link": 82,
    # URL
    "url": 90,
    "url-access": 91,
    "trans-title": 92,
    "format": 93,
    # Work
    "department": 100,
    "journal": 101,
    "website": 102,
    "work": 103,
    "newspaper": 104,
    "magazine": 105,
    "encyclopedia": 106,
    "script-journal": 107,
    "trans-journal": 108,
    # Type, series, language
    "type": 110,
    "series": 111,
    "language": 112,
    # Volume, issue
    "volume": 120,
    "issue": 121,
    "article-number": 122,
    "number": 122,
    # Interviewers
    "interviewer-last": 130,
    "interviewer-first": 131,
    "interviewer-link": 132,
    # Translators
    "translator-last": 140,
    "translator-first": 141,
    "translator-link": 142,
    # Others, name-list-style
    "others": 150,
    "name-list-style": 151,
    # Edition, publisher
    "edition": 160,
    "publisher": 161,
    "publication-date": 162,
    # Time
    "minutes": 170,
    "time-caption": 171,
    "time": 172,
    # Pages
    "page": 180,
    "pages": 181,
    "at": 182,
    "no-pp": 183,
    # Identifiers
    "arxiv": 190,
    "asin": 191,
    "bibcode": 192,
    "biorxiv": 193,
    "citeseerx": 194,
    "doi": 195,
    "doi-access": 195,
    "doi-broken-date": 195,
    "eissn": 196,
    "hdl": 197,
    "isbn": 198,
    "ismn": 199,
    "issn": 200,
    "jstor": 201,
    "lccn": 202,
    "medrxiv": 203,
    "mr": 204,
    "oclc": 205,
    "ol": 206,
    "osti": 207,
    "pmc": 208,
    "pmc-embargo-date": 208,
    "pmid": 209,
    "rfc": 210,
    "sbn": 211,
    "ssrn": 212,
    "s2cid": 213,
    "zbl": 214,
    "id": 215,
    # Archive
    "url-status": 220,
    "archive-url": 221,
    "archive-format": 222,
    "archive-date": 223,
    # Access
    "access-date": 230,
    "via": 231,
    "agency": 232,
    # Quote
    "quote-page": 240,
    "quote-pages": 241,
    "quote": 242,
    "script-quote": 243,
    "trans-quote": 244,
    # Misc
    "mode": 250,
    "ref": 251,
    "postscript": 252,
}

# Numbered parameter groups: (sort_group_priority, sub_order_within_number)
# Keys are the base name (without number suffix).
# These groups interleave by number: last1, first1, link1, last2, first2, link2, ...
_NUM_GROUP = {
    "last": (20, 1),
    "first": (20, 2),
    "author-link": (20, 3),
    "editor-last": (61, 1),
    "editor-first": (61, 2),
    "editor-link": (61, 3),
    "translator-last": (140, 1),
    "translator-first": (140, 2),
    "translator-link": (140, 3),
    "interviewer-last": (130, 1),
    "interviewer-first": (130, 2),
    "interviewer-link": (130, 3),
}

_NUMBERED_BASES = (
    set(_NUM_GROUP.keys())
    - {
        "display-interviewers",
        "display-translators",
        "display-editors",
    }
) | {"author-mask", "editor-mask"}


def _parse_param_name(name: str):
    """Return (base_name, number) for a parameter name."""
    name = name.strip().lower()
    for base in _NUMBERED_BASES:
        if name == base:
            return (base, 1)
        if name.startswith(base) and name[len(base) :].isdigit():
            return (base, int(name[len(base) :]))
    return (name, 0)


def _sort_key(param_name: str):
    """Produce a sort tuple for a parameter name.

    Numbered parameters within the same group (e.g. last/first/author-link)
    are interleaved by number: last1, first1, author-link1, last2, first2, ...
    Unnumbered parameters sort after all numbered entries of their group.
    """
    base, num = _parse_param_name(param_name)
    group = _NUM_GROUP.get(base)
    if group and num > 0:
        # Numbered param: sort within its group by number, then by sub-order
        return (group[0], 0, num, group[1])
    # Unnumbered param: use its direct priority
    priority = _PRIORITY.get(base, 999)
    return (priority, 1, 0, 0)


class SortModule(CitationModule):
    name = "sort"
    description = "Reorder parameters to Wikipedia standard order"

    @staticmethod
    def _parse_params(body: str):
        """Extract (full_match, name, value) triples from citation body."""
        params = []
        idx = 0
        while idx < len(body):
            m = re.search(r"\|\s*([^=|}]+?)\s*=\s*", body[idx:])
            if not m:
                break
            start = idx + m.start()
            name = m.group(1).strip().lower()
            # Find value end: next | or end of string, respecting {{}} and [[]]
            val_start = idx + m.end()
            depth = 0
            in_link = False
            in_value = True
            end = val_start
            while end < len(body):
                ch = body[end]
                if ch == "{" and end + 1 < len(body) and body[end + 1] == "{":
                    depth += 1
                    end += 1
                elif ch == "}" and end + 1 < len(body) and body[end + 1] == "}":
                    depth = max(0, depth - 1)
                    end += 1
                elif ch == "[" and end + 1 < len(body) and body[end + 1] == "[":
                    in_link = True
                    end += 1
                elif ch == "]" and end + 1 < len(body) and body[end + 1] == "]":
                    in_link = False
                    end += 1
                elif ch == "|" and depth == 0 and not in_link:
                    break
                end += 1

            value = body[val_start:end].strip()
            params.append((start, end, name, value))
            idx = end

        return params

    def process(self, text: str, context: dict) -> ProcessingResult:
        start = text
        params = self._parse_params(text)
        if len(params) <= 1:
            return ProcessingResult(text=text, changes={})

        # Capture position of first param BEFORE sorting mutates the list
        first_start = params[0][0]
        prefix = text[:first_start]

        # Sort by key; stable sort preserves original order for equal keys
        params.sort(key=lambda p: _sort_key(p[2]))

        # Rebuild
        sorted_body = " ".join(f"| {p[2]} = {p[3]}" for p in params)
        text = prefix + sorted_body

        return ProcessingResult(text=text, changes={"sort": text != start})
