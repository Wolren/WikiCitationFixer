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
_PRIORITY = {
    "vauthors": 10,
    "last": 20,
    "first": 21,
    "author-link": 22,
    "author-mask": 23,
    "display-authors": 24,
    "author": 25,
    "collaboration": 30,
    "name-list-style": 31,
    "translator-last": 40,
    "translator-first": 41,
    "translator-link": 42,
    "df": 50,
    "date": 51,
    "year": 52,
    "orig-date": 53,
    "veditors": 60,
    "editor-last": 61,
    "editor-first": 62,
    "editor-link": 63,
    "display-editors": 64,
    "location": 70,
    "title": 80,
    "script-title": 81,
    "title-link": 82,
    "url": 90,
    "url-access": 91,
    "trans-title": 92,
    "format": 93,
    "department": 100,
    "journal": 101,
    "website": 102,
    "work": 103,
    "newspaper": 104,
    "magazine": 105,
    "encyclopedia": 106,
    "type": 110,
    "series": 111,
    "language": 112,
    "volume": 120,
    "issue": 121,
    "article-number": 122,
    "edition": 130,
    "publication-place": 131,
    "publisher": 132,
    "publication-date": 133,
    "page": 140,
    "pages": 141,
    "at": 142,
    "arxiv": 150,
    "asin": 151,
    "bibcode": 152,
    "biorxiv": 153,
    "citeseerx": 154,
    "doi": 155,
    "eissn": 156,
    "hdl": 157,
    "isbn": 158,
    "ismn": 159,
    "issn": 160,
    "jstor": 161,
    "lccn": 162,
    "medrxiv": 163,
    "mr": 164,
    "oclc": 165,
    "ol": 166,
    "osti": 167,
    "pmc": 168,
    "pmid": 169,
    "rfc": 170,
    "s2cid": 171,
    "ssrn": 172,
    "zbl": 173,
    "id": 174,
    "url-status": 180,
    "archive-url": 181,
    "archive-format": 182,
    "archive-date": 183,
    "access-date": 190,
    "via": 191,
    "agency": 192,
    "quote": 200,
    "script-quote": 201,
    "trans-quote": 202,
    "quote-page": 203,
    "quote-pages": 204,
    "others": 210,
    "mode": 211,
    "ref": 212,
    "postscript": 213,
}

_NUMBERED_BASES = {
    "last",
    "first",
    "author-link",
    "author-mask",
    "translator-last",
    "translator-first",
    "translator-link",
    "editor-last",
    "editor-first",
    "editor-link",
}


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
    """Produce a sort tuple for a parameter name."""
    base, num = _parse_param_name(param_name)
    priority = _PRIORITY.get(base, 999)
    return (priority, num if num else 0, param_name)


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
        sorted_body = "".join(f"| {p[2]} = {p[3]}" for p in params)
        text = prefix + sorted_body

        return ProcessingResult(text=text, changes={"sort": text != start})
