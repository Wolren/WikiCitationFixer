# mypy: disable-error-code="attr-defined"
"""CrossRef API mixin: DOI metadata, ISSN, OA check, authors, title search."""

from typing import Any, cast

from wikifix.logger import get_logger
from wikifix.cache import ResponseCache

log = get_logger()


class CrossRefMixin:
    """CrossRef API methods. Requires self._session, _rate_limit, _cached_get/set, clean_doi."""

    def fetch_crossref(self, doi: str) -> dict[str, Any] | None:
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("crossref", "work", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)
        self._rate_limit("crossref", self.config.crossref_delay)
        try:
            resp = self._session.get(
                f"https://api.crossref.org/works/{doi}", timeout=10
            )
            if resp.ok:
                msg = resp.json().get("message")
                self._cached_set(cache_key, msg)
                return cast(dict[str, Any], msg)
        except Exception as e:
            log.warning("  CrossRef fetch failed for DOI %s: %s", doi, e)
        return None

    def doi_to_issn(self, doi: str) -> str | None:
        msg = self.fetch_crossref(doi)
        if msg:
            issns = msg.get("ISSN", [])
            return issns[0] if issns else None
        return None

    def doi_is_oa(self, doi: str) -> bool:
        msg = self.fetch_crossref(doi)
        if not msg:
            return False
        for lic in msg.get("license", []):
            url = lic.get("URL", "")
            if "creativecommons" in url.lower():
                return True
        return False

    def doi_to_authors(self, doi: str) -> list[tuple[str, str]]:
        msg = self.fetch_crossref(doi)
        if msg:
            authors = msg.get("author", [])
            return [(a["family"], a.get("given", "")) for a in authors if "family" in a]
        return []

    def doi_from_title(self, title: str) -> str | None:
        cache_key = ResponseCache.make_key(
            "crossref", "title_search", title.strip().lower()
        )
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(str, cached)
        self._rate_limit("crossref", self.config.crossref_delay)
        try:
            resp = self._session.get(
                "https://api.crossref.org/works",
                params={"query.title": title, "rows": 1},
                timeout=10,
            )
            if resp.ok:
                items = resp.json().get("message", {}).get("items", [])
                if items:
                    doi = items[0].get("DOI")
                    self._cached_set(cache_key, doi)
                    return cast(str | None, doi)
        except Exception as e:
            log.warning("  Title search failed for %s: %s", title, e)
        return None
