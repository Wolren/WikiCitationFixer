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
from typing import Any

from wikifix.base import CitationModule
from wikifix.config import Mode, ProcessingResult
from wikifix.logger import get_logger

log = get_logger()


FIELD_ALIASES = {
    "journal": ["journal", "website", "work", "newspaper", "magazine"],
    "publisher": ["publisher", "publication-place"],
    "type": ["type", "series", "department"],
}


def _has_field(text: str, field: str) -> bool:
    """Check whether a parameter already exists in the citation body."""
    return bool(re.search(rf"\|\s*{field}\s*=", text))


def _add_field(text: str, name: str, value: str, force: bool = False) -> str:
    """Append or replace a parameter in the citation body."""
    if _has_field(text, name):
        if not force:
            return text
        text = re.sub(rf"\|\s*{re.escape(name)}\s*=[^\|]+", "", text)
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


def _format_date_from_parts(date_parts: list[int]) -> str:
    """Format [year, month, day] list into Wikipedia date string."""
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
    """Expand citations with metadata from external APIs."""

    name = "expand"
    description = "Expand citations with metadata from DOI/PMID/arXiv/ISBN"

    @staticmethod
    def _can_use_journal(template_type: str) -> bool:
        """journal is only valid for cite journal and CS2 citation templates."""
        t = template_type.lower()
        return t in ("citation",) or t.startswith("cite journal")

    @staticmethod
    def _container_field(template_type: str) -> str:
        """Return the appropriate container field for the template type."""
        t = template_type.lower()
        if t.startswith("cite journal") or t == "citation":
            return "journal"
        if t.startswith("cite web"):
            return "website"
        if t.startswith("cite news"):
            return "newspaper"
        if t.startswith("cite magazine"):
            return "magazine"
        return "journal"  # fallback

    def _expand_from_doi(
        self, text: str, doi: str, api: Any, template_type: str, force: bool = False
    ) -> str:
        """Try CrossRef then Europe PMC to fill fields via DOI."""
        msg = api.fetch_crossref(doi)
        if msg:
            if force or not _has_field(text, "title"):
                title = msg.get("title", [None])[0]
                if title:
                    text = _add_field(text, "title", html.unescape(title), force=force)

            if force or not _has_field(text, "journal"):
                container = (msg.get("container-title") or [None])[0]
                if container:
                    field = self._container_field(template_type)
                    if field != "journal" or self._can_use_journal(template_type):
                        text = _add_field(
                            text, field, _clean_journal(container), force=force
                        )

            if not template_type.lower().startswith("cite book"):
                if force or not _has_field(text, "volume"):
                    vol = msg.get("volume")
                    if vol:
                        text = _add_field(text, "volume", str(vol), force=force)

            if (force or not _has_field(text, "issue")) and not _has_field(
                text, "number"
            ):
                issue = msg.get("issue")
                if issue:
                    text = _add_field(text, "issue", str(issue), force=force)

            if _has_field(text, "page") and _has_field(text, "pages"):
                pass  # both already present, don't touch
            elif _has_field(text, "article-number"):
                pass  # article-number already set, skip pages
            elif force or not (_has_field(text, "page") or _has_field(text, "pages")):
                pages = msg.get("page")
                if pages:
                    fld = "pages" if not _has_field(text, "page") else "page"
                    text = _add_field(text, fld, pages, force=force)

            if (force or not _has_field(text, "date")) and not _has_field(text, "year"):
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
                        text = _add_field(text, "date", date_str, force=force)

            if force or not _has_field(text, "publisher"):
                t = template_type.lower()
                if not t.startswith("cite journal"):
                    pub = msg.get("publisher")
                    if pub:
                        text = _add_field(
                            text, "publisher", _clean_publisher(pub), force=force
                        )

        # Try Europe PMC as supplement
        epmc = api.fetch_europepmc(doi)
        if epmc:
            if (force or not _has_field(text, "title")) and epmc.get("title"):
                text = _add_field(
                    text, "title", html.unescape(epmc["title"]), force=force
                )
            j_field = self._container_field(template_type)
            if force or not _has_field(text, j_field):
                j = epmc.get("journalTitle") or epmc.get("bookOrReportDetails", {}).get(
                    "publisher"
                )
                if j and (j_field != "journal" or self._can_use_journal(template_type)):
                    text = _add_field(text, j_field, _clean_journal(j), force=force)
            if not template_type.lower().startswith("cite book"):
                if (force or not _has_field(text, "volume")) and epmc.get("volume"):
                    text = _add_field(text, "volume", str(epmc["volume"]), force=force)
            if (force or not _has_field(text, "issue")) and epmc.get("issue"):
                text = _add_field(text, "issue", str(epmc["issue"]), force=force)
            if (
                not _has_field(text, "page")
                and not _has_field(text, "pages")
                and not _has_field(text, "article-number")
            ):
                p = epmc.get("pageInfo")
                if p:
                    text = _add_field(text, "pages", p, force=force)
            if force or not _has_field(text, "date"):
                epmc_date = epmc.get("firstPublicationDate") or epmc.get("pubYear")
                if epmc_date:
                    text = _add_field(
                        text, "date", _format_date_string(str(epmc_date)), force=force
                    )
            if force or not _has_field(text, "pmid"):
                pid = epmc.get("source") == "MED" and epmc.get("id")
                if pid:
                    text = _add_field(text, "pmid", str(pid), force=force)
            if force or not _has_field(text, "pmc"):
                pmcid = epmc.get("pmcid") or (
                    epmc.get("id") if epmc.get("source") == "PMC" else None
                )
                if pmcid:
                    text = _add_field(
                        text, "pmc", str(pmcid).removeprefix("PMC"), force=force
                    )

        return text

    def _expand_from_pmid(
        self, text: str, pmid: str, api: Any, template_type: str, force: bool = False
    ) -> str:
        """Fill fields from Europe PMC by PMID."""
        epmc = api.pmid_to_metadata_europepmc(pmid)
        if not epmc:
            return text
        if (force or not _has_field(text, "title")) and epmc.get("title"):
            text = _add_field(text, "title", html.unescape(epmc["title"]), force=force)
        j_field = self._container_field(template_type)
        if force or not _has_field(text, j_field):
            j = epmc.get("journalTitle")
            if j and (j_field != "journal" or self._can_use_journal(template_type)):
                text = _add_field(text, j_field, _clean_journal(j), force=force)
        if not template_type.lower().startswith("cite book"):
            if (force or not _has_field(text, "volume")) and epmc.get("volume"):
                text = _add_field(text, "volume", str(epmc["volume"]), force=force)
        if (force or not _has_field(text, "issue")) and epmc.get("issue"):
            text = _add_field(text, "issue", str(epmc["issue"]), force=force)
        if (
            not _has_field(text, "page")
            and not _has_field(text, "pages")
            and not _has_field(text, "article-number")
        ):
            p = epmc.get("pageInfo")
            if p:
                text = _add_field(text, "pages", p, force=force)
        if force or not _has_field(text, "date"):
            d = epmc.get("firstPublicationDate") or epmc.get("pubYear")
            if d:
                text = _add_field(
                    text, "date", _format_date_string(str(d)), force=force
                )
        return text

    def _expand_from_arxiv(
        self, text: str, arxiv_id: str, api: Any, force: bool = False
    ) -> str:
        """Fill fields from arXiv API."""
        data = api.fetch_arxiv(arxiv_id)
        if not data:
            return text
        if force or not _has_field(text, "title"):
            if data.get("title"):
                text = _add_field(text, "title", data["title"], force=force)
        if force or not _has_field(text, "date"):
            if data.get("date"):
                text = _add_field(text, "date", data["date"], force=force)
        if force or not _has_field(text, "doi"):
            if data.get("doi"):
                text = _add_field(text, "doi", data["doi"], force=force)
        return text

    def _expand_from_isbn(
        self, text: str, isbn: str, api: Any, force: bool = False
    ) -> str:
        """Fill fields from Open Library by ISBN."""
        data = api.fetch_openlibrary(isbn)
        if not data:
            return text
        if force or not _has_field(text, "title"):
            if data.get("title"):
                text = _add_field(text, "title", data["title"], force=force)
        if force or not _has_field(text, "date"):
            if data.get("date"):
                text = _add_field(text, "date", data["date"], force=force)
        if force or not _has_field(text, "publisher"):
            if data.get("publisher"):
                text = _add_field(
                    text, "publisher", _clean_publisher(data["publisher"]), force=force
                )
        return text

    def _extract_doi_from_url(self, text: str) -> str | None:
        """Extract a DOI from |url=https://doi.org/... if no |doi= already exists."""
        if _has_field(text, "doi"):
            return None
        url_m = re.search(r"\|\s*url\s*=\s*([^\|}]+)", text)
        if not url_m:
            return None
        url = url_m.group(1).strip()
        m = re.match(r"https?://(?:dx\.)?doi\.org/(.+)$", url, re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    def _expand_from_title(
        self, text: str, title: str, api: Any, template_type: str
    ) -> str:
        """Search for a DOI by title, then expand from it."""
        doi = api.doi_from_title(title)
        if doi:
            text = self._expand_from_doi(text, doi, api, template_type)
        return text

    def process(self, text: str, context: dict[str, Any]) -> ProcessingResult:
        """Fill in missing citation fields from DOI/PMID/arXiv/ISBN metadata."""
        start = text
        api = context.get("api")
        mode: Mode = context.get("mode", Mode.INCREMENTAL)
        if not api:
            return ProcessingResult(text=text, changes={"expand": False})

        doi = context.get("doi")
        pmid = context.get("pmid")
        template_type = context.get("template_type", "citation")
        arxiv_m = re.search(r"\|\s*arxiv\s*=\s*([^\|}]+)", text)
        arxiv_id = arxiv_m.group(1).strip() if arxiv_m else None
        isbn_m = re.search(r"\|\s*isbn\s*=\s*([^\|}]+)", text)
        isbn = isbn_m.group(1).strip() if isbn_m else None

        # Extract DOI from |url= if no explicit |doi= field
        if not doi:
            doi = self._extract_doi_from_url(text)

        # Force-refresh: when a DOI is present, strip all expandable fields
        # and re-fetch from CrossRef/Europe PMC. Without a DOI there is no
        # reliable source to re-fetch from, so run incrementally.
        is_book = template_type.lower().startswith("cite book")
        if mode == Mode.FORCE_REFRESH and doi:
            strip_fields = [
                "title",
                "journal",
                "website",
                "work",
                "newspaper",
                "magazine",
                "issue",
                "pages",
                "page",
                "date",
                "publisher",
            ]
            if not is_book:
                strip_fields.append("volume")
            text = re.sub(
                r"\|\s*(?:" + "|".join(strip_fields) + r")\s*=[^\|]+",
                "",
                text,
            )
            force = True
        else:
            force = False

        if doi:
            text = self._expand_from_doi(text, doi, api, template_type, force=force)
        if pmid:
            text = self._expand_from_pmid(text, pmid, api, template_type)
        if arxiv_id:
            text = self._expand_from_arxiv(text, arxiv_id, api)
        if isbn:
            text = self._expand_from_isbn(text, isbn, api)

        # Title→DOI expansion: if no DOI was found and no expansion happened, try title
        if not doi and not pmid and not arxiv_id and not isbn:
            title_val = context.get("title") or self._get_field(text, "title")
            if title_val:
                text = self._expand_from_title(text, title_val, api, template_type)

        changed = text != start
        if changed:
            log.info("    + Expanded with metadata")
        return ProcessingResult(text=text, changes={"expand": changed})

    @staticmethod
    def _get_field(text: str, field: str) -> str | None:
        """Extract the value of a parameter from the citation body."""
        m = re.search(rf"\|\s*{re.escape(field)}\s*=\s*([^|]+)", text)
        return m.group(1).strip() if m else None
