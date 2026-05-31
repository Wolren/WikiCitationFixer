"""
Citation expansion module.

Fills in missing fields from external APIs when a citation has
a DOI, PMID, arXiv ID, or ISBN but lacks key metadata like
title, journal, authors, date, volume, issue, pages, or publisher.

Sources tried in order:
  - CrossRef (DOI → full metadata)
  - Europe PMC (DOI/PMID → full metadata)
  - arXiv API (arXiv ID → metadata)
  - Open Library (ISBN → book metadata)
"""

import html
import re

from wikifix.base import CitationModule
from wikifix.config import Mode, ProcessingResult


FIELD_ALIASES = {
    "journal": ["journal", "website", "work", "newspaper", "magazine"],
    "publisher": ["publisher", "publication-place"],
    "type": ["type", "series", "department"],
}


def _has_field(text: str, field: str) -> bool:
    return bool(re.search(rf"\|\s*{field}\s*=", text))


def _add_field(text: str, name: str, value: str) -> str:
    if _has_field(text, name):
        return text
    return text + f" |{name}={value}"


_WIKIPEDIA_PUBLISHER_SUFFIXES = [
    r",?\s+(Publishing|Publishers|Publications|Published)\s*$",
    r",?\s+(Inc|Ltd|LLC|LLP|Corporation|Corp|Company|Co|KG)\s*\.?\s*$",
    r",?\s+&?\s*(Co|Company|Associates|Partners)\s*\.?\s*$",
    r"\s+AG\s*$",
    r"\s+[Gg]mb[Hh]\s*$",
    r"\s+S\.\s*A\.?\s*$",
    r"\s+S\.?\s*p\.?\s*a\.?\s*$",
    r"\s+S\.?\s*r\.?\s*l\.?\s*$",
    r"\s+B\.?\s*V\.?\s*$",
    r"\s+S\.?\s*A\.?\s*S\.?\s*$",
    r"\s+Verlag\s*$",
]


def _clean_publisher(pub: str) -> str:
    """Clean a publisher string per Wikipedia conventions.

    Strips corporate suffixes (Inc, Ltd, LLC, AG, etc.) and trailing
    parenthetical English translations. Keeps "Press" and "University
    Press" as-is. Preserves original-language diacritics when present.
    """
    result = pub.strip()
    result = re.sub(r"\s*\([^)]*\)\s*$", "", result).strip()
    for pattern in _WIKIPEDIA_PUBLISHER_SUFFIXES:
        result = re.sub(pattern, "", result).strip()
    return result if result else pub.strip()


def _clean_journal(name: str) -> str:
    """Clean a journal/website/work name per Wikipedia conventions.

    Strips parenthetical English translations and normalises whitespace.
    """
    result = name.strip()
    result = re.sub(r"\s*\([^)]*\)\s*$", "", result).strip()
    return result if result else name.strip()


def _format_date_from_parts(date_parts: list) -> str:
    if not date_parts:
        return ""
    parts = date_parts
    month_map = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }
    year = parts[0]
    month = month_map.get(parts[1], parts[1]) if len(parts) >= 2 else None
    day = parts[2] if len(parts) >= 3 else None
    if day and month:
        return f"{day} {month} {year}"
    if month:
        return f"{month} {year}"
    return str(year)


def _format_date_string(s: str) -> str:
    """Parse a date string (YYYY-MM-DD or YYYY) into Wikipedia format."""
    s = s.strip()
    parts = s.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return _format_date_from_parts([int(parts[0]), int(parts[1]), int(parts[2])])
    if len(parts) == 1 and parts[0].isdigit():
        return parts[0]
    return s


class ExpandModule(CitationModule):
    name = "expand"
    description = "Expand citations with metadata from DOI/PMID/arXiv/ISBN"

    def _expand_from_doi(self, text: str, doi: str, api) -> str:
        """Try CrossRef then Europe PMC to fill fields via DOI."""
        msg = api.fetch_crossref(doi)
        if msg:
            if not _has_field(text, "title"):
                title = msg.get("title", [None])[0]
                if title:
                    text = _add_field(text, "title", html.unescape(title))

            if not _has_field(text, "journal"):
                container = (msg.get("container-title") or [None])[0]
                if container:
                    for alias in FIELD_ALIASES["journal"]:
                        if _has_field(text, alias):
                            break
                    else:
                        text = _add_field(text, "journal", _clean_journal(container))

            if not _has_field(text, "volume"):
                vol = msg.get("volume")
                if vol:
                    text = _add_field(text, "volume", str(vol))

            if not _has_field(text, "issue") and not _has_field(text, "number"):
                issue = msg.get("issue")
                if issue:
                    text = _add_field(text, "issue", str(issue))

            if not _has_field(text, "page") and not _has_field(text, "pages"):
                pages = msg.get("page")
                if pages:
                    text = _add_field(text, "pages", pages)

            if not _has_field(text, "date") and not _has_field(text, "year"):
                date_parts = msg.get("published-print", {}).get("date-parts", [None])[0]
                if not date_parts:
                    date_parts = msg.get("published-online", {}).get(
                        "date-parts", [None]
                    )[0]
                if not date_parts:
                    date_parts = msg.get("issued", {}).get("date-parts", [None])[0]
                if date_parts:
                    date_str = _format_date_from_parts(date_parts)
                    if date_str:
                        text = _add_field(text, "date", date_str)

            if not _has_field(text, "publisher"):
                pub = msg.get("publisher")
                if pub:
                    text = _add_field(text, "publisher", _clean_publisher(pub))

        # Try Europe PMC as supplement
        epmc = api.fetch_europepmc(doi)
        if epmc:
            if not _has_field(text, "title") and epmc.get("title"):
                text = _add_field(text, "title", html.unescape(epmc["title"]))
            if not _has_field(text, "journal"):
                j = epmc.get("journalTitle") or epmc.get("bookOrReportDetails", {}).get(
                    "publisher"
                )
                if j:
                    text = _add_field(text, "journal", _clean_journal(j))
            if not _has_field(text, "volume") and epmc.get("volume"):
                text = _add_field(text, "volume", str(epmc["volume"]))
            if not _has_field(text, "issue") and epmc.get("issue"):
                text = _add_field(text, "issue", str(epmc["issue"]))
            if not _has_field(text, "page") and not _has_field(text, "pages"):
                p = epmc.get("pageInfo")
                if p:
                    text = _add_field(text, "pages", p)
            if not _has_field(text, "date"):
                epmc_date = epmc.get("firstPublicationDate") or epmc.get("pubYear")
                if epmc_date:
                    text = _add_field(text, "date", _format_date_string(str(epmc_date)))
            if not _has_field(text, "pmid"):
                pid = epmc.get("source") == "MED" and epmc.get("id")
                if pid:
                    text = _add_field(text, "pmid", str(pid))
            if not _has_field(text, "pmc"):
                pmcid = epmc.get("pmcid") or (
                    epmc.get("id") if epmc.get("source") == "PMC" else None
                )
                if pmcid:
                    text = _add_field(text, "pmc", str(pmcid).removeprefix("PMC"))

        return text

    def _expand_from_pmid(self, text: str, pmid: str, api) -> str:
        """Fill fields from Europe PMC by PMID."""
        epmc = api.pmid_to_metadata_europepmc(pmid)
        if not epmc:
            return text
        if not _has_field(text, "title") and epmc.get("title"):
            text = _add_field(text, "title", html.unescape(epmc["title"]))
        if not _has_field(text, "journal"):
            j = epmc.get("journalTitle")
            if j:
                text = _add_field(text, "journal", _clean_journal(j))
        if not _has_field(text, "volume") and epmc.get("volume"):
            text = _add_field(text, "volume", str(epmc["volume"]))
        if not _has_field(text, "issue") and epmc.get("issue"):
            text = _add_field(text, "issue", str(epmc["issue"]))
        if not _has_field(text, "page") and not _has_field(text, "pages"):
            p = epmc.get("pageInfo")
            if p:
                text = _add_field(text, "pages", p)
        if not _has_field(text, "date"):
            d = epmc.get("firstPublicationDate") or epmc.get("pubYear")
            if d:
                text = _add_field(text, "date", _format_date_string(str(d)))
        return text

    def _expand_from_arxiv(self, text: str, arxiv_id: str, api) -> str:
        """Fill fields from arXiv API."""
        data = api.fetch_arxiv(arxiv_id)
        if not data:
            return text
        if not _has_field(text, "title") and data.get("title"):
            text = _add_field(text, "title", data["title"])
        if not _has_field(text, "date") and data.get("date"):
            text = _add_field(text, "date", data["date"])
        if not _has_field(text, "doi") and data.get("doi"):
            text = _add_field(text, "doi", data["doi"])
        return text

    def _expand_from_isbn(self, text: str, isbn: str, api) -> str:
        """Fill fields from Open Library by ISBN."""
        data = api.fetch_openlibrary(isbn)
        if not data:
            return text
        if not _has_field(text, "title") and data.get("title"):
            text = _add_field(text, "title", data["title"])
        if not _has_field(text, "date") and data.get("date"):
            text = _add_field(text, "date", data["date"])
        if not _has_field(text, "publisher") and data.get("publisher"):
            text = _add_field(text, "publisher", _clean_publisher(data["publisher"]))
        return text

    def process(self, text: str, context: dict) -> ProcessingResult:
        start = text
        api = context.get("api")
        if not api:
            return ProcessingResult(text=text, changes={"expand": False})

        doi = context.get("doi")
        pmid = context.get("pmid")
        arxiv_m = re.search(r"\|\s*arxiv\s*=\s*([^\|}]+)", text)
        arxiv_id = arxiv_m.group(1).strip() if arxiv_m else None
        isbn_m = re.search(r"\|\s*isbn\s*=\s*([^\|}]+)", text)
        isbn = isbn_m.group(1).strip() if isbn_m else None

        if doi:
            text = self._expand_from_doi(text, doi, api)
        if pmid:
            text = self._expand_from_pmid(text, pmid, api)
        if arxiv_id:
            text = self._expand_from_arxiv(text, arxiv_id, api)
        if isbn:
            text = self._expand_from_isbn(text, isbn, api)

        changed = text != start
        if changed:
            print(f"    + Expanded with metadata")
        return ProcessingResult(text=text, changes={"expand": changed})
