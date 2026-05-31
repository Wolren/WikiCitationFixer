"""
Author formatting module.

Supports two directions:
    - Vancouver → normal  (|vauthors= → |last=/|first=)  [default]
    - Normal → Vancouver  (|last=/|first= → |vauthors=)

The direction is controlled by the ``author_style`` context key:
    ``"normal"`` (default) → expand vauthors into last/first pairs
    ``"vancouver"``        → collapse last/first into a single vauthors field
"""

import re
import unicodedata
from typing import List, Optional, Tuple

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult


def _param_re(name: str) -> str:
    """Return regex for ``| name = value`` with optional whitespace."""
    return rf"\|\s*{name}\s*=\s*([^\|}}]+)"


class AuthorModule(CitationModule):
    name = "authors"
    description = "Convert between Vancouver (|vauthors=) and normal (|last=/|first=) author styles"

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
    def _parse_vauthors(vauthors: str) -> List[Tuple[str, str]]:
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
        full_names: Optional[List[Tuple[str, str]]] = None,
        max_authors: int = 6,
    ) -> str:
        """Replace |vauthors=... with |lastN=/|firstN= pairs.

        If *full_names* is provided (list of (family, given) from CrossRef),
        use full given names instead of parsed initials.

        *max_authors* caps the number of author pairs output (0 = unlimited).
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

        authors: List[Tuple[str, str]] = []
        for i in range(1, 13):
            lk = "last" if i == 1 else f"last{i}"
            fk = "first" if i == 1 else f"first{i}"
            lm = re.search(_param_re(lk), text)
            fm = re.search(_param_re(fk), text)
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
            lk = "last" if i == 1 else f"last{i}"
            fk = "first" if i == 1 else f"first{i}"
            text = re.sub(rf"\|\s*{lk}\s*=[^\|}}]+", "", text)
            text = re.sub(rf"\|\s*{fk}\s*=[^\|}}]+", "", text)
        text = re.sub(r"\|\s*\|", "|", text).strip().lstrip("|")

        return f"|vauthors={vauthors} |{text}" if text else f"|vauthors={vauthors}"

    # ------------------------------------------------------------------
    #  Process
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich_lastfirst(
        text: str, full_names: List[Tuple[str, str]], max_authors: int = 6
    ) -> str:
        """Replace abbreviated first names in existing last/first pairs with full names from sources."""
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
                        lambda m, v=re.escape(full_given): f"| {fk} = {v}",
                        text,
                    )
                    updated = True
        return text if updated else text

    @staticmethod
    def _try_fetch_authors(api, doi: str) -> list:
        """Fetch full author names from multiple sources, returning the best result.

        Tries CrossRef → OpenAlex → DataCite → PubMed, picks the one with
        the most complete (longest) given names.
        """
        sources = [
            ("CrossRef", api.doi_to_authors),
            ("OpenAlex", api.doi_to_authors_openalex),
            ("DataCite", api.doi_to_authors_datacite),
            ("PubMed", api.doi_to_authors_pubmed),
        ]
        best = []
        best_score = 0
        for name, fetcher in sources:
            try:
                result = fetcher(doi)
            except Exception:
                result = []
            if not result:
                continue
            # Score: total length of given names (fuller = better)
            score = sum(len(g) for _, g in result)
            if score > best_score:
                best = result
                best_score = score
        return best

    def process(self, text: str, context: dict) -> ProcessingResult:
        changes = {"authors": False}
        style = context.get("author_style", "normal")
        refresh = context.get("refresh_authors", False)
        api = context.get("api")
        doi = context.get("doi")
        max_authors = context.get("max_authors", 6)

        if style == "normal":
            has_vauthors = bool(AuthorModule._VAUTHORS_RE.search(text))
            has_last = bool(re.search(_param_re(r"last\d?"), text))

            if has_vauthors and not has_last:
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
            elif has_last and not has_vauthors:
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
            if not AuthorModule._VAUTHORS_RE.search(text):
                new_text = self._lastfirst_to_vauthors(text, max_authors=max_authors)
                if new_text != text:
                    text = new_text
                    changes["authors"] = True

        return ProcessingResult(text=text, changes=changes)
