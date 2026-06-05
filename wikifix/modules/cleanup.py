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

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult
from wikifix.logger import get_logger

log = get_logger()

# Deprecated CS1/CS2 parameters and their replacements (if any)
_DEPRECATED = {
    "month": None,
    "day": None,
    "coauthors": None,
    "coauthor": None,
    "coeditors": None,
    "dateformat": None,
    "separator": None,
    "seperator": None,
    "author-separator": None,
    "author-name-separator": None,
}

_VALID_URL_STATUS = {"live", "dead", "unfit", "usurped", "bot: unknown"}

_ARCHIVED_COPY_PATTERNS = re.compile(
    r"^(archived\s+copy|untitled|no\s+title|\[no\s+title\]|resumo|"
    r"sin título|senza titolo|ohne titel|标题|タイトル)",  # common non-English placeholders
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

    _FIELD_RE = r"\|\s*{}\s*=\s*[^|]+"

    @staticmethod
    def _get_field(text: str, field: str) -> str | None:
        """Extract the value of a parameter from the citation body."""
        m = re.search(rf"\|\s*{re.escape(field)}\s*=\s*([^|]+)", text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _remove_field(text: str, field: str) -> str:
        """Remove a parameter and its value from the citation body."""
        return re.sub(
            CleanupModule._FIELD_RE.format(re.escape(field)), "", text, count=1
        )

    @staticmethod
    def _field_exists(text: str, field: str) -> bool:
        """Check whether a parameter name appears in the citation body."""
        return bool(re.search(rf"\|\s*{re.escape(field)}\s*=", text))

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
        has = CleanupModule._field_exists

        # cite thesis: |degree= or |type= containing "thesis"
        if has(text, "degree"):
            return "cite thesis"
        tm = re.search(r"\|\s*type\s*=\s*([^|]+)", text)
        if tm and "thesis" in tm.group(1).lower():
            return "cite thesis"

        # cite news: |newspaper=
        if has(text, "newspaper"):
            return "cite news"

        # cite magazine: |magazine=
        if has(text, "magazine"):
            return "cite magazine"

        # cite journal: |journal=, |bibcode=, |arxiv=
        if has(text, "journal") or has(text, "bibcode") or has(text, "arxiv"):
            return "cite journal"

        # cite web: |website=
        if has(text, "website"):
            return "cite web"

        # cite book: |isbn= and no periodical indicators
        # (|work= is excluded — it maps to |title= in cite book)
        if has(text, "isbn"):
            for field in ("journal", "website", "newspaper", "magazine"):
                if has(text, field):
                    return None
            return "cite book"

        # cite web (fallback): |work= and no other signals
        if has(text, "work"):
            return "cite web"

        return None

    def process(self, text: str, context: dict) -> ProcessingResult:
        """Apply CS1/CS2 maintenance fixes to a citation body."""
        changes = {}
        new_template_type = None
        template_type = context.get("template_type", "")
        t = template_type.lower()

        # --- 0. Convert {{citation}} to specific template ---
        rename_params: dict[str, str] = {}
        drop_params: set[str] = set()
        detected = None
        if t == "citation":
            detected = self._detect_citation_type(text)
            if detected:
                new_template_type = detected
                changes["citation-type"] = True
                # Set up parameter renames for the target type
                if detected == "cite book":
                    has_work = self._field_exists(text, "work")
                    has_title = self._field_exists(text, "title")
                    if has_work and has_title:
                        rename_params["title"] = "chapter"
                    if has_work:
                        rename_params["work"] = "title"
                    if self._field_exists(text, "place"):
                        rename_params["place"] = "location"
                    if has_work and self._field_exists(text, "url"):
                        rename_params["url"] = "chapter-url"
                elif detected == "cite journal":
                    if self._field_exists(text, "work"):
                        rename_params["work"] = "journal"
                    if self._field_exists(text, "place"):
                        rename_params["place"] = "location"
                elif detected == "cite web":
                    if self._field_exists(text, "work"):
                        rename_params["work"] = "website"
                    if self._field_exists(text, "place"):
                        rename_params["place"] = "location"
                elif detected in ("cite news", "cite magazine", "cite thesis"):
                    if self._field_exists(text, "place"):
                        rename_params["place"] = "location"

        # --- 1. Missing or empty |title= ---
        title_val = self._get_field(text, "title")
        if title_val is not None and not title_val.strip():
            text = self._remove_field(text, "title")
            changes["empty-title"] = True
        elif title_val is not None and _ARCHIVED_COPY_PATTERNS.match(title_val.strip()):
            changes["placeholder-title"] = True

        # --- 2. |location= without |publisher= in books ---
        if t.startswith("cite book") or t == "citation":
            loc = self._get_field(text, "location")
            pub = self._get_field(text, "publisher")
            if loc is not None and pub is None:
                changes["location-no-publisher"] = True

        # --- 3. |work=/|journal= with |isbn= (books don't use periodical params) ---
        if self._field_exists(text, "isbn"):
            for field in ("work", "journal", "website", "newspaper", "magazine"):
                if self._field_exists(text, field):
                    # Don't remove if citation→cite book will rename work→title
                    if (
                        field == "work"
                        and detected == "cite book"
                        and "work" in rename_params
                    ):
                        continue
                    text = self._remove_field(text, field)
                    changes["work-with-isbn"] = True

        # --- 4. Periodical conflicts ---
        if t.startswith("cite web") or t.startswith("cite news"):
            if self._field_exists(text, "journal"):
                text = self._remove_field(text, "journal")
                changes["periodical-conflict"] = True
            if t.startswith("cite web") and self._field_exists(text, "newspaper"):
                text = self._remove_field(text, "newspaper")
                changes["periodical-conflict"] = True
        if t.startswith("cite journal"):
            if self._field_exists(text, "work"):
                text = self._remove_field(text, "work")
                changes["periodical-conflict"] = True

        # --- 5. |url-status= validation ---
        status_val = self._get_field(text, "url-status")
        if status_val is not None and status_val.lower() not in _VALID_URL_STATUS:
            text = self._remove_field(text, "url-status")
            changes["invalid-url-status"] = True

        # --- 6. Both |page= and |pages= ---
        if self._field_exists(text, "page") and self._field_exists(text, "pages"):
            text = self._remove_field(text, "pages")
            changes["page-pages-conflict"] = True

        # --- 7. Deprecated parameters ---
        for depr in _DEPRECATED:
            if self._field_exists(text, depr):
                text = self._remove_field(text, depr)
                changes["deprecated-param"] = True

        # --- 8. Extra text in |volume=, |issue=, |page=, |edition= ---
        vol = self._get_field(text, "volume")
        if vol:
            cleaned = self._strip_extra_text(vol, "volume")
            if cleaned != vol:
                text = self._set_field(text, "volume", cleaned)
                changes["extra-text"] = True
        iss = self._get_field(text, "issue")
        if iss:
            cleaned = self._strip_extra_text(iss, "issue")
            if cleaned != iss:
                text = self._set_field(text, "issue", cleaned)
                changes["extra-text"] = True
        num = self._get_field(text, "number")
        if num:
            cleaned = self._strip_extra_text(num, "issue")
            if cleaned != num:
                text = self._set_field(text, "number", cleaned)
                changes["extra-text"] = True
        ed = self._get_field(text, "edition")
        if ed:
            cleaned = self._strip_extra_text(ed, "edition")
            if cleaned != ed:
                text = self._set_field(text, "edition", cleaned)
                changes["extra-text"] = True

        # --- 9. work/journal dedup: {{citation}} uses |work=, not |journal= ---
        if t == "citation":
            work_val = self._get_field(text, "work")
            journal_val = self._get_field(text, "journal")
            if (
                work_val is not None
                and journal_val is not None
                and work_val == journal_val
            ):
                text = self._remove_field(text, "journal")
                changes["work-journal-dedup"] = True

        # --- 10. year/date conflict: |date= is preferred, remove |year= ---
        date_val = self._get_field(text, "date")
        year_val = self._get_field(text, "year")
        if date_val is not None and year_val is not None:
            text = self._remove_field(text, "year")
            changes["year-date-conflict"] = True

        # --- 11. Orphaned |access-date= without |url= ---
        if self._field_exists(text, "access-date") and not self._field_exists(
            text, "url"
        ):
            text = self._remove_field(text, "access-date")
            changes["orphan-access-date"] = True

        # --- 12. Orphaned |doi-broken-date= without |doi= ---
        if self._field_exists(text, "doi-broken-date") and not self._field_exists(
            text, "doi"
        ):
            text = self._remove_field(text, "doi-broken-date")
            changes["orphan-doi-broken-date"] = True

        # --- 13. Empty parameter values ---
        for m in re.finditer(r"\|\s*([^=|}]+?)\s*=\s*(?:\||\}\})", text):
            param = m.group(1).strip().lower()
            if param:
                text = self._remove_field(text, param)
                changes["empty-param"] = True

        # --- 14. Parameter name typo correction ---
        for typo, correct in _TYPO_MAP.items():
            if typo != correct and self._field_exists(text, typo):
                rename_params[typo] = correct
                changes["typo-param"] = True

        # --- 15. External links in text parameter values ---
        for param in _TEXT_PARAMS:
            val = self._get_field(text, param)
            if val and re.search(r"https?://", val, re.IGNORECASE):
                changes["external-link"] = True
                # Only flag, don't auto-remove (user should fix)
                break

        # --- 16. ISBN validation + ISBN-10 → ISBN-13 conversion ---
        isbn_val = self._get_field(text, "isbn")
        if isbn_val:
            fixed = self._fix_isbn(isbn_val)
            if fixed is None:
                changes["invalid-isbn"] = True
            elif fixed != "".join(c for c in isbn_val if c not in "- "):
                text = self._set_field(text, "isbn", fixed)
                changes["isbn-normalized"] = True

        # --- 17. No-break space (\u00A0) in parameter values ---
        for m in re.finditer(r"\|\s*([^=]+?)\s*=\s*([^|]+)", text):
            param_name = m.group(1).strip().lower()
            val = m.group(2).strip()
            if "\u00a0" in val:
                fixed_val = val.replace("\u00a0", " ")
                pattern = (
                    rf"\|\s*{re.escape(m.group(1).strip())}\s*=\s*{re.escape(val)}"
                )
                text = re.sub(pattern, f"| {param_name} = {fixed_val}", text, count=1)
                changes["nbsp-fix"] = True

        # --- 18. Literal "None" value (case-insensitive) ---
        for m in re.finditer(
            r"\|\s*([^=]+?)\s*=\s*(None)\s*(?=\||\}\})", text, re.IGNORECASE
        ):
            param = m.group(1).strip().lower()
            text = self._remove_field(text, param)
            changes["none-value"] = True

        return ProcessingResult(
            text=text,
            changes=changes,
            new_template_type=new_template_type,
            rename_params=rename_params,
            drop_params=drop_params,
        )

    @staticmethod
    def _set_field(text: str, field: str, new_value: str) -> str:
        """Replace the entire |field= parameter with a clean version."""
        pattern = rf"\|\s*{re.escape(field)}\s*=\s*[^|]+"
        m = re.search(pattern, text)
        if not m:
            return text
        old = m.group(0).rstrip()
        return text.replace(old, f"| {field} = {new_value}", 1)

    @staticmethod
    def _strip_extra_text(value: str, field: str) -> str:
        """Strip leading/trailing volume/issue/page/edition prefixes from a value."""
        v = value.strip()
        v = re.sub(
            r"^(vol\.?\s*|volume\s*|v\.\s*|no\.?\s*|number\s*|issue\s*|"
            r"p\.\s*|pp\.\s*|page\s*|pages\s*|ed\.?\s*|edition\s*)",
            "",
            v,
            flags=re.IGNORECASE,
        ).strip()
        v = re.sub(
            r"\s*(vol\.?|volume|no\.?|number|issue|p\.|pp\.|"
            r"page|pages|ed\.?|edition)\s*$",
            "",
            v,
            flags=re.IGNORECASE,
        ).strip()
        return v
