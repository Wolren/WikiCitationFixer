"""
Cleanup module for common CS1/CS2 maintenance issues.

Fixes:
- Missing or empty |title=
- "Archived copy" / placeholder |title=
- |location= without |publisher= in cite book
- |work=/|journal=/|website= with |isbn= in books
- Periodical conflicts (cite web + |journal=, cite journal + |work=)
- |url-status= invalid values
- Both |page= and |pages=
- Deprecated parameters (month, day, coauthors, ...)
- Extra text in |volume=, |issue=, |page=, |edition=
- year/date conflict
- work/journal dedup in {{citation}}
- Orphaned |access-date= without |url=
- Orphaned |doi-broken-date= without |doi=
- Empty parameter values
- Common parameter name misspellings
- External links in text parameters (title, publisher, etc.)
- ISBN validation + ISBN-10 to ISBN-13 conversion
"""

import re
from typing import Any

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult
from wikifix.field_utils import get_field, has_field, remove_field, set_field
from wikifix.logger import get_logger

log = get_logger()

# Deprecated CS1/CS2 parameters and their replacements (if any)
_DEPRECATED = frozenset(
    {
        "month",
        "day",
        "coauthors",
        "coauthor",
        "coeditors",
        "dateformat",
        "separator",
        "seperator",
        "author-separator",
        "author-name-separator",
    }
)
_DEPRECATED_RE = re.compile(
    r"\|\s*(?:" + "|".join(re.escape(p) for p in _DEPRECATED) + r")\s*=[^|]+"
)

_VALID_URL_STATUS = {"live", "dead", "unfit", "usurped", "bot: unknown"}

_ARCHIVED_COPY_PATTERNS = re.compile(
    r"^(archived\s+copy|untitled|no\s+title|\[no\s+title\]|resumo|"
    r"sin título|senza titolo|ohne titel|标题|タイトル)",
    re.IGNORECASE,
)

# Common parameter name typos → correct name
_TYPO_MAP = {
    "pubisher": "publisher",
    "piblisher": "publisher",
    "pblisher": "publisher",
    "joural": "journal",
    "journa": "journal",
    "jouurnal": "journal",
    "retreived": "access-date",
    "retrived": "access-date",
    "acces-date": "access-date",
    "accesdate": "access-date",
    "accessdate": "access-date",
    "accsess-date": "access-date",
    "volum": "volume",
    "volue": "volume",
    "iss": "issue",
    "issu": "issue",
    "edtion": "edition",
    "editon": "edition",
    "publication": "publisher",
    "publishr": "publisher",
    "publlisher": "publisher",
    "titl": "title",
    "tiitle": "title",
    "locatiion": "location",
    "locaton": "location",
    "lang": "language",
    "languge": "language",
    "languaage": "language",
    "lanugage": "language",
    "isbn": "isbn",  # valid
    "issn": "issn",  # valid
    "url": "url",  # valid
    "doi": "doi",  # valid
    "pmid": "pmid",  # valid
    "pmc": "pmc",  # valid
}

# Text parameters that should not contain external URLs
_TEXT_PARAMS = {
    "title",
    "script-title",
    "trans-title",
    "chapter",
    "trans-chapter",
    "publisher",
    "journal",
    "work",
    "website",
    "newspaper",
    "magazine",
    "series",
    "department",
    "type",
    "description",
    "quote",
    "others",
    "edition",
}


class CleanupModule(CitationModule):
    """Fix common CS1/CS2 template maintenance issues."""

    name = "cleanup"
    description = "Fix CS1/CS2 maintenance issues"

    @staticmethod
    def _fix_isbn(raw: str) -> str | None:
        """Validate and normalize an ISBN.

        Returns:
            ISBN-13 (digits only, no hyphens) if valid, None if invalid.
            Converts ISBN-10 to ISBN-13 automatically.
            Accepts ISBN-10 or ISBN-13 with or without hyphens.
        """
        digits = re.sub(r"[^0-9X]", "", raw.upper())
        if len(digits) == 10:
            total = 0
            for i in range(9):
                if not digits[i].isdigit():
                    return None
                total += int(digits[i]) * (10 - i)
            orig_check = digits[9]
            expected: int | str = 11 - (total % 11)
            if expected == 11:
                expected = 0
            elif expected == 10:
                expected = "X"
            if str(expected) != orig_check:
                return None
            isbn13 = "978" + digits[:9]
            total = 0
            for i, ch in enumerate(isbn13):
                w = 1 if i % 2 == 0 else 3
                total += int(ch) * w
            calc_check = (10 - (total % 10)) % 10
            return isbn13 + str(calc_check)
        elif len(digits) == 13:
            total = 0
            for i in range(12):
                if not digits[i].isdigit():
                    return None
                w = 1 if i % 2 == 0 else 3
                total += int(digits[i]) * w
            calc_check = (10 - (total % 10)) % 10
            if int(digits[12]) == calc_check:
                return digits  # return normalized digit-only form
            return None
        return None

    @staticmethod
    def _detect_citation_type(text: str) -> str | None:
        """Detect specific template type for a generic {{citation}} body."""
        # cite thesis: |degree= or |type= containing "thesis"
        if has_field(text, "degree"):
            return "cite thesis"
        tm = re.search(r"\|\s*type\s*=\s*([^|]+)", text)
        if tm and "thesis" in tm.group(1).lower():
            return "cite thesis"

        # cite news: |newspaper=
        if has_field(text, "newspaper"):
            return "cite news"

        # cite magazine: |magazine=
        if has_field(text, "magazine"):
            return "cite magazine"

        # cite journal: |journal=, |bibcode= (arxiv alone can't supply journal)
        if has_field(text, "journal") or has_field(text, "bibcode"):
            return "cite journal"

        # cite web: |website=
        if has_field(text, "website"):
            return "cite web"

        # cite book: |isbn= and no periodical indicators
        # (|work= is excluded — it maps to |title= in cite book)
        if has_field(text, "isbn"):
            for field in ("journal", "website", "newspaper", "magazine"):
                if has_field(text, field):
                    return None
            return "cite book"

        # cite web (fallback): |work= and no other signals
        if has_field(text, "work"):
            return "cite web"

        return None

    def process(self, text: str, context: dict[str, Any]) -> ProcessingResult:
        """Apply CS1/CS2 maintenance fixes to a citation body."""
        changes: dict[str, bool] = {}
        template_type = context.get("template_type", "")
        t = template_type.lower()
        rename_params: dict[str, str] = {}
        drop_params: set[str] = set()

        new_template_type, rename_params = self._detect_template_type(
            text, t, changes, rename_params
        )
        text = self._fix_title_issues(text, changes)
        self._flag_location_no_publisher(text, t, changes)
        text = self._fix_work_with_isbn(text, changes)
        text = self._fix_periodical_conflicts(text, t, changes)
        text = self._fix_url_status(text, changes)
        text = self._fix_page_pages_conflict(text, changes)
        text = self._fix_deprecated_params(text, changes)
        text = self._fix_extra_text_values(text, changes)
        text = self._fix_work_journal_dedup(text, t, changes)
        text = self._fix_year_date_conflict(text, changes)
        text = self._fix_orphan_params(text, changes)
        text = self._fix_empty_params(text, changes)
        rename_params = self._fix_typo_params(text, changes, rename_params)
        self._flag_external_links(text, changes)
        text = self._fix_isbn_param(text, changes)
        text = self._fix_nbsp_values(text, changes)
        text = self._fix_none_values(text, changes)
        self._flag_missing_essentials(text, t, changes)

        return ProcessingResult(
            text=text,
            changes=changes,
            new_template_type=new_template_type,
            rename_params=rename_params,
            drop_params=drop_params,
        )

    @staticmethod
    def _detect_template_type(
        text: str, t: str, changes: dict[str, bool], rename_params: dict[str, str]
    ) -> tuple[str | None, dict[str, str]]:
        """Convert {{citation}} to a specific template type."""
        if t != "citation":
            return None, rename_params
        detected = CleanupModule._detect_citation_type(text)
        if not detected:
            return None, rename_params
        changes["citation-type"] = True
        if detected == "cite book":
            has_work = has_field(text, "work")
            has_title = has_field(text, "title")
            if has_work and has_title:
                rename_params["title"] = "chapter"
            if has_work:
                rename_params["work"] = "title"
            if has_field(text, "place"):
                rename_params["place"] = "location"
            if has_work and has_field(text, "url"):
                rename_params["url"] = "chapter-url"
        elif detected == "cite journal":
            if has_field(text, "work"):
                rename_params["work"] = "journal"
            if has_field(text, "place"):
                rename_params["place"] = "location"
        elif detected == "cite web":
            if has_field(text, "work"):
                rename_params["work"] = "website"
            if has_field(text, "place"):
                rename_params["place"] = "location"
        elif detected in ("cite news", "cite magazine", "cite thesis"):
            if has_field(text, "place"):
                rename_params["place"] = "location"
        return detected, rename_params

    @staticmethod
    def _fix_title_issues(text: str, changes: dict[str, bool]) -> str:
        """Fix missing or placeholder titles."""
        title_val = get_field(text, "title")
        if title_val is not None and not title_val.strip():
            text = remove_field(text, "title")
            changes["empty-title"] = True
        elif title_val is not None and _ARCHIVED_COPY_PATTERNS.match(title_val.strip()):
            changes["placeholder-title"] = True
        return text

    @staticmethod
    def _flag_location_no_publisher(
        text: str, t: str, changes: dict[str, bool]
    ) -> None:
        """Flag location without publisher in books."""
        if t.startswith("cite book") or t == "citation":
            loc = get_field(text, "location")
            pub = get_field(text, "publisher")
            if loc is not None and pub is None:
                changes["location-no-publisher"] = True

    @staticmethod
    def _fix_work_with_isbn(text: str, changes: dict[str, bool]) -> str:
        """Remove periodical params when ISBN is present."""
        if not has_field(text, "isbn"):
            return text
        for field in ("work", "journal", "website", "newspaper", "magazine"):
            if has_field(text, field):
                text = remove_field(text, field)
                changes["work-with-isbn"] = True
        return text

    @staticmethod
    def _fix_periodical_conflicts(text: str, t: str, changes: dict[str, bool]) -> str:
        """Fix cite web/journal conflicts."""
        if t.startswith("cite web") or t.startswith("cite news"):
            if has_field(text, "journal"):
                text = remove_field(text, "journal")
                changes["periodical-conflict"] = True
            if t.startswith("cite web") and has_field(text, "newspaper"):
                text = remove_field(text, "newspaper")
                changes["periodical-conflict"] = True
        if t.startswith("cite journal") and has_field(text, "work"):
            text = remove_field(text, "work")
            changes["periodical-conflict"] = True
        return text

    @staticmethod
    def _fix_url_status(text: str, changes: dict[str, bool]) -> str:
        """Remove invalid url-status values."""
        status_val = get_field(text, "url-status")
        if status_val is not None and status_val.lower() not in _VALID_URL_STATUS:
            text = remove_field(text, "url-status")
            changes["invalid-url-status"] = True
        return text

    @staticmethod
    def _fix_page_pages_conflict(text: str, changes: dict[str, bool]) -> str:
        """Remove |pages= when |page= is also present."""
        if has_field(text, "page") and has_field(text, "pages"):
            text = remove_field(text, "pages")
            changes["page-pages-conflict"] = True
        return text

    @staticmethod
    def _fix_deprecated_params(text: str, changes: dict[str, bool]) -> str:
        """Remove deprecated parameters via a single combined regex."""
        new_text, count = _DEPRECATED_RE.subn("", text, count=0)
        if count:
            text = re.sub(r"\|\s*\|", "|", new_text)
            changes["deprecated-param"] = True
        return text

    @staticmethod
    def _fix_extra_text_values(text: str, changes: dict[str, bool]) -> str:
        """Strip extra text from volume, issue, page, edition."""
        for field in ("volume", "issue", "number", "edition"):
            val = get_field(text, field)
            if val:
                kind = "issue" if field == "number" else field
                cleaned = CleanupModule._strip_extra_text(val, kind)
                if cleaned != val:
                    text = set_field(text, field, cleaned)
                    changes["extra-text"] = True
        return text

    @staticmethod
    def _fix_work_journal_dedup(text: str, t: str, changes: dict[str, bool]) -> str:
        """Remove duplicate |journal= when |work= is the same value."""
        if t != "citation":
            return text
        work_val = get_field(text, "work")
        journal_val = get_field(text, "journal")
        if work_val is not None and journal_val is not None and work_val == journal_val:
            text = remove_field(text, "journal")
            changes["work-journal-dedup"] = True
        return text

    @staticmethod
    def _fix_year_date_conflict(text: str, changes: dict[str, bool]) -> str:
        """Remove |year= when |date= is present."""
        if get_field(text, "date") is not None and get_field(text, "year") is not None:
            text = remove_field(text, "year")
            changes["year-date-conflict"] = True
        return text

    @staticmethod
    def _fix_orphan_params(text: str, changes: dict[str, bool]) -> str:
        """Remove access-date/doi-broken-date without their parent param."""
        if has_field(text, "access-date") and not has_field(text, "url"):
            text = remove_field(text, "access-date")
            changes["orphan-access-date"] = True
        if has_field(text, "doi-broken-date") and not has_field(text, "doi"):
            text = remove_field(text, "doi-broken-date")
            changes["orphan-doi-broken-date"] = True
        return text

    @staticmethod
    def _fix_empty_params(text: str, changes: dict[str, bool]) -> str:
        """Remove parameters with empty values (single-pass)."""
        empty_re = re.compile(r"\|\s*([^=|}]+?)\s*=\s*(?=\||\}\})")
        new_text, count = empty_re.subn("", text)
        if count:
            text = re.sub(r"\|\s*\|", "|", new_text)
            changes["empty-param"] = True
        return text

    @staticmethod
    def _fix_typo_params(
        text: str, changes: dict[str, bool], rename_params: dict[str, str]
    ) -> dict[str, str]:
        """Fix common parameter name typos via a single combined scan."""
        typos = [t for t, c in _TYPO_MAP.items() if t != c]
        if not typos:
            return rename_params
        typo_pattern = re.compile(
            r"\|\s*(" + "|".join(re.escape(t) for t in typos) + r")\s*="
        )
        for m in typo_pattern.finditer(text):
            name = m.group(1).strip().lower()
            correct = _TYPO_MAP.get(name)
            if correct and name != correct:
                rename_params[name] = correct
                changes["typo-param"] = True
        return rename_params

    @staticmethod
    def _flag_external_links(text: str, changes: dict[str, bool]) -> None:
        """Flag external URLs in text parameters."""
        for param in _TEXT_PARAMS:
            val = get_field(text, param)
            if val and re.search(r"https?://", val, re.IGNORECASE):
                changes["external-link"] = True
                break

    @staticmethod
    def _fix_isbn_param(text: str, changes: dict[str, bool]) -> str:
        """Validate and normalize ISBN, convert ISBN-10 to ISBN-13."""
        isbn_val = get_field(text, "isbn")
        if not isbn_val:
            return text
        fixed = CleanupModule._fix_isbn(isbn_val)
        if fixed is None:
            changes["invalid-isbn"] = True
        elif fixed != "".join(c for c in isbn_val if c not in "- "):
            text = set_field(text, "isbn", fixed)
            changes["isbn-normalized"] = True
        return text

    @staticmethod
    def _fix_nbsp_values(text: str, changes: dict[str, bool]) -> str:
        """Replace no-break spaces (\\u00A0) with regular spaces (single-pass)."""

        def _replace_nbsp(m: re.Match[str]) -> str:
            name = m.group(1).strip()
            val = m.group(2)
            if "\u00a0" in val:
                changes["nbsp-fix"] = True
                fixed_val = val.replace("\u00a0", " ")
                return f"| {name.lower()} = {fixed_val}"
            return m.group(0)

        return re.sub(
            r"\|\s*([^=]+?)\s*=\s*([^|]+)",
            _replace_nbsp,
            text,
        )

    @staticmethod
    def _fix_none_values(text: str, changes: dict[str, bool]) -> str:
        """Remove parameters with literal 'None' values (single-pass)."""
        new_text, count = re.subn(
            r"\|\s*[^=|}]+?\s*=\s*None\s*(?=\||\}\})",
            "",
            text,
            flags=re.IGNORECASE,
        )
        if count:
            text = re.sub(r"\|\s*\|", "|", new_text)
            changes["none-value"] = True
        return text

    @staticmethod
    def _flag_missing_essentials(text: str, t: str, changes: dict[str, bool]) -> None:
        """Flag missing essential parameters."""
        if not has_field(text, "title"):
            changes["missing-title"] = True
        if not has_field(text, "date") and not has_field(text, "year"):
            changes["missing-date"] = True
        if t.startswith("cite web") and not has_field(text, "url"):
            changes["missing-url"] = True
        if t.startswith("cite book") and not has_field(text, "publisher"):
            changes["missing-publisher"] = True

    _STRIP_LEADING = re.compile(
        r"^(vol\.?\s*|volume\s*|v\.\s*|no\.?\s*|number\s*|issue\s*|"
        r"p\.\s*|pp\.\s*|page\s*|pages\s*|ed\.?\s*|edition\s*)",
        re.IGNORECASE,
    )
    _STRIP_TRAILING = re.compile(
        r"\s*(vol\.?|volume|no\.?|number|issue|p\.|pp\.|"
        r"page|pages|ed\.?|edition)\s*$",
        re.IGNORECASE,
    )

    @staticmethod
    def _strip_extra_text(value: str, field: str) -> str:
        v = value.strip()
        v = CleanupModule._STRIP_LEADING.sub("", v).strip()
        v = CleanupModule._STRIP_TRAILING.sub("", v).strip()
        return v
