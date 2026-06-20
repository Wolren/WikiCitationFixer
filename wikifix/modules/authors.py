"""
Author formatting module.

Supports two directions:
    - Vancouver → normal  (|vauthors= → |last=/|first=)  [default]
    - Normal → Vancouver  (|last=/|first= → |vauthors=)

The direction is controlled by the ``author_style`` context key:
    ``"normal"`` (default) → expand vauthors into last/first pairs
    ``"vancouver"``        → collapse last/first into a single vauthors field

Diagnostic-only checks (flag issues without modifying):
    - Multiple names in a single |lastN=|firstN= field
    - Numeric author names (OCLC import artifacts)
    - Generic/placeholder author names
    - |others= duplicating author/editor names
"""

import re
import unicodedata
from typing import Any

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult
from wikifix.logger import get_logger

log = get_logger()


def _param_re(name: str) -> str:
    """Return regex for ``| name = value`` with optional whitespace."""
    return rf"\|\s*{name}\s*=\s*([^\|}}]+)"


# Generic/placeholder names that should be flagged
_GENERIC_NAMES = {
    "anonymous",
    "anon",
    "author",
    "authors",
    "editor",
    "editors",
    "translator",
    "translators",
    "unknown",
    "n/a",
    "na",
    "none",
    "not applicable",
    "placeholder",
    "to be announced",
    "tba",
    "tbd",
}

# Separators that indicate multiple names crammed into one field
_MULTI_NAME_SEP = re.compile(r";\s*|\s+and\s+|\s*&\s*")


class AuthorModule(CitationModule):
    """Convert between Vancouver and normal author styles."""

    name = "authors"
    description = "Convert between Vancouver and normal author styles"

    # ------------------------------------------------------------------
    #  Vancouver → normal helpers
    # ------------------------------------------------------------------

    _VAUTHORS_RE = re.compile(_param_re("vauthors"))

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Strip diacritics for fuzzy matching (Lariviere == Larivière)."""
        return (
            unicodedata.normalize("NFKD", name)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )

    @staticmethod
    def _parse_vauthors(vauthors: str) -> list[tuple[str, str]]:
        """Parse a vauthors string into (last, initials) pairs.

        Handles "Smith JA, Doe JB, et al" → [("Smith", "JA"), ("Doe", "JB")]
        """
        authors = []
        for part in vauthors.split(","):
            part = part.strip()
            if not part or part.lower() in ("et al", "etal"):
                continue
            tokens = part.strip().split()
            if not tokens:
                continue
            last = tokens[0]
            initials = "".join(t for t in tokens[1:] if t.isupper() and t.isalpha())
            authors.append((last, initials))
        return authors

    @staticmethod
    def _vauthors_to_lastfirst(
        text: str,
        full_names: list[tuple[str, str]] | None = None,
        max_authors: int = 6,
    ) -> str:
        """Replace |vauthors=... with |lastN=/|firstN= pairs.

        Args:
            full_names: List of (family, given) from CrossRef to use full given
                names instead of parsed initials.
            max_authors: Cap the number of author pairs output (0 = unlimited).
        """
        m = AuthorModule._VAUTHORS_RE.search(text)
        if not m:
            return text
        vauthors_str = m.group(1).strip()
        pairs = AuthorModule._parse_vauthors(vauthors_str)
        if not pairs:
            return text

        # Substitute full names from CrossRef where available (positional match)
        if full_names:
            resolved = []
            for i, (ln, fn) in enumerate(pairs):
                if i < len(full_names) and AuthorModule._normalize_name(
                    full_names[i][0]
                ) == AuthorModule._normalize_name(ln):
                    resolved.append((full_names[i][0], full_names[i][1]))
                else:
                    resolved.append((ln, fn))
            pairs = resolved

        # Apply max_authors limit
        truncated = max_authors > 0 and len(pairs) > max_authors
        if truncated:
            pairs = pairs[:max_authors]

        text = AuthorModule._VAUTHORS_RE.sub("", text)
        text = text.strip().strip("|").strip()
        parts = []
        for i, (ln, fn) in enumerate(pairs, 1):
            lk = "last" if i == 1 else f"last{i}"
            fk = "first" if i == 1 else f"first{i}"
            parts.append(f"{lk}={ln}")
            if fn:
                parts.append(f"{fk}={fn}")

        author_block = "|".join(parts)
        if truncated:
            author_block += "|display-authors=etal"
        return f"|{author_block} |{text}" if text else f"|{author_block}"

    # ------------------------------------------------------------------
    #  Normal → Vancouver helpers
    # ------------------------------------------------------------------

    @staticmethod
    def extract_initials(fname: str) -> str:
        """Extract up to two uppercase initials from a given name."""
        if not fname:
            return ""
        return "".join(
            p[0].upper() for p in re.split(r"[\s\-\.]+", fname.strip()) if p
        )[:2]

    @staticmethod
    def _lastfirst_to_vauthors(text: str, max_authors: int = 6) -> str:
        """Replace |last=/|first= pairs with |vauthors=..."""
        if re.search(r"\|\s*vauthors\s*=", text):
            return text

        authors: list[tuple[str, str]] = []
        for i in range(1, 13):
            lk = f"last{i}"
            fk = f"first{i}"
            lm = re.search(_param_re(lk), text) or (
                re.search(_param_re("last"), text) if i == 1 else None
            )
            fm = re.search(_param_re(fk), text) or (
                re.search(_param_re("first"), text) if i == 1 else None
            )
            if lm:
                authors.append((lm.group(1).strip(), fm.group(1).strip() if fm else ""))
        if not authors:
            return text

        limit = max_authors if max_authors > 0 else len(authors)
        formatted = [
            f"{ln} {AuthorModule.extract_initials(fn)}"
            if AuthorModule.extract_initials(fn)
            else ln
            for ln, fn in authors[:limit]
        ]
        vauthors = ", ".join(formatted) + (", et al" if len(authors) > limit else "")

        for i in range(1, 13):
            lk = r"last\d?" if i == 1 else f"last{i}"
            fk = r"first\d?" if i == 1 else f"first{i}"
            text = re.sub(rf"\|\s*{lk}\s*=[^\|}}]+", "", text)
            text = re.sub(rf"\|\s*{fk}\s*=[^\|}}]+", "", text)
        text = re.sub(r"\|\s*\|", "|", text).strip().lstrip("|")

        return f"|vauthors={vauthors} |{text}" if text else f"|vauthors={vauthors}"

    # ------------------------------------------------------------------
    #  Process
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich_lastfirst(
        text: str, full_names: list[tuple[str, str]], max_authors: int = 6
    ) -> str:
        """Replace abbreviated first names with full names from external sources."""
        pairs = []
        for i in range(1, 13):
            lm = re.search(_param_re(f"last{i}"), text)
            lm = lm or (re.search(_param_re("last"), text) if i == 1 else None)
            if not lm:
                break
            fm = re.search(_param_re(f"first{i}"), text)
            fm = fm or (re.search(_param_re("first"), text) if i == 1 else None)
            pairs.append(
                (
                    lm.group(1).strip(),
                    fm.group(1).strip() if fm else "",
                    f"last{i}",
                    f"first{i}",
                )
            )

        limit = max_authors if max_authors > 0 else len(pairs)
        updated = False
        for i, (ln, fn, lk, fk) in enumerate(pairs):
            if i >= limit:
                break
            if i < len(full_names) and AuthorModule._normalize_name(
                full_names[i][0]
            ) == AuthorModule._normalize_name(ln):
                full_given = full_names[i][1].strip()
                if full_given and len(full_given) > len(fn):
                    text = re.sub(
                        _param_re(fk),
                        lambda m: f"| {fk} = {full_given}",
                        text,
                    )
                    updated = True
        return text if updated else text

    @staticmethod
    def _try_fetch_authors(api: Any, doi: str) -> list[tuple[str, str]]:
        """Fetch full author names from multiple sources, returning the best result.

        Tries CrossRef → OpenAlex → DataCite → PubMed in parallel, picks the
        one with the most complete (longest) given names.
        """
        tasks = [
            ("CrossRef", lambda d=doi: api.doi_to_authors(d)),
            ("OpenAlex", lambda d=doi: api.doi_to_authors_openalex(d)),
            ("DataCite", lambda d=doi: api.doi_to_authors_datacite(d)),
            ("PubMed", lambda d=doi: api.doi_to_authors_pubmed(d)),
        ]
        results = api.concurrent_fetch(tasks)
        best: list[tuple[str, str]] = []
        best_score = 0
        for result in results.values():
            if not result:
                continue
            score = sum(len(g) for _, g in result)
            if score > best_score:
                best = result
                best_score = score
        return best

    def process(self, text: str, context: dict[str, Any]) -> ProcessingResult:
        """Convert author styles and/or enrich abbreviated given names."""
        original = text
        changes = {"authors": False}
        style = context.get("author_style", "normal")
        refresh = context.get("refresh_authors", False)
        api = context.get("api")
        doi = context.get("doi")
        max_authors = context.get("max_authors", 6)

        if style == "normal":
            has_vauthors = bool(AuthorModule._VAUTHORS_RE.search(text))

            if has_vauthors:
                # Strip any existing last/first to avoid duplicates
                for i in range(1, 13):
                    lk = r"last\d?" if i == 1 else f"last{i}"
                    fk = r"first\d?" if i == 1 else f"first{i}"
                    text = re.sub(rf"\|\s*{lk}\s*=[^\|}}]+", "", text)
                    text = re.sub(rf"\|\s*{fk}\s*=[^\|}}]+", "", text)
                text = re.sub(r"\|\s*\|", "|", text).strip()
                # Vancouver → normal
                full_names = None
                if refresh and api and doi:
                    full_names = self._try_fetch_authors(api, doi)

                new_text = self._vauthors_to_lastfirst(
                    text, full_names=full_names, max_authors=max_authors
                )
                if new_text != text:
                    text = new_text
                    changes["authors"] = True
            else:
                # Already normal → enrich abbreviated first names
                if refresh and api and doi:
                    full_names = self._try_fetch_authors(api, doi)
                    if full_names:
                        new_text = self._enrich_lastfirst(
                            text, full_names, max_authors=max_authors
                        )
                        if new_text != text:
                            text = new_text
                            changes["authors"] = True
        elif style == "vancouver":
            # Normal → Vancouver
            if AuthorModule._VAUTHORS_RE.search(text):
                # Already has vauthors — strip redundant last/first fields
                for i in range(1, 13):
                    lk = r"last\d?" if i == 1 else f"last{i}"
                    fk = r"first\d?" if i == 1 else f"first{i}"
                    text = re.sub(rf"\|\s*{lk}\s*=[^\|}}]+", "", text)
                    text = re.sub(rf"\|\s*{fk}\s*=[^\|}}]+", "", text)
                text = re.sub(r"\|\s*\|", "|", text).strip()
            else:
                new_text = self._lastfirst_to_vauthors(text, max_authors=max_authors)
                if new_text != text:
                    text = new_text
            if text != original:
                changes["authors"] = True

        # --- Diagnostic-only checks (flag without modifying) ---

        # 1. Multiple names in a single field
        if not changes.get("multi-name-field"):
            for m in re.finditer(_param_re(r"(?:last|first)\d*"), text):
                val = m.group(1).strip()
                if _MULTI_NAME_SEP.search(val):
                    changes["multi-name-field"] = True
                    break

        # 2. Numeric author names
        if not changes.get("numeric-name"):
            for m in re.finditer(_param_re(r"last\d*"), text):
                val = m.group(1).strip()
                if val.isdigit():
                    changes["numeric-name"] = True
                    break

        # 3. Generic/placeholder author names
        if not changes.get("generic-name"):
            for m in re.finditer(_param_re(r"(?:last|first)\d*"), text):
                val = m.group(1).strip().lower()
                if val in _GENERIC_NAMES:
                    changes["generic-name"] = True
                    break

        # 4. |others= duplicating author names
        if not changes.get("others-duplicate"):
            others_m = re.search(_param_re("others"), text)
            if others_m:
                others_val = others_m.group(1).lower()
                # Collect all author/editor/translator names from the template
                seen = set()
                for m in re.finditer(
                    _param_re(r"(?:last|first|author|editor|translator)\d*"), text
                ):
                    name = m.group(1).strip().lower()
                    if name:
                        seen.add(name)
                if seen and any(n in others_val for n in seen if len(n) > 2):
                    changes["others-duplicate"] = True

        return ProcessingResult(text=text, changes=changes)
