# mypy: disable-error-code="attr-defined"
"""Semantic Scholar API mixin: DOI→S2CID."""

from typing import cast

from wikifix.logger import get_logger
from wikifix.cache import ResponseCache

log = get_logger()


class SemanticScholarMixin:
    """Semantic Scholar API methods. Requires self._session, _rate_limit, _cached_get/set, clean_doi."""

    def doi_to_s2cid(self, doi: str) -> str | None:
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("semantic", "s2cid", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(str, cached)
        self._rate_limit("semantic_scholar", self.config.semantic_scholar_delay)
        headers = {}
        if self.config.semantic_scholar_api_key:
            headers["x-api-key"] = self.config.semantic_scholar_api_key
        try:
            resp = self._session.get(
                f"https://api.semanticscholar.org/v1/paper/{doi}",
                headers=headers or None,
                timeout=10,
            )
            if resp.ok:
                val = resp.json().get("paperId")
                self._cached_set(cache_key, val)
                return cast(str | None, val)
        except Exception as e:
            log.warning("  S2CID fetch failed for DOI %s: %s", doi, e)
        return None
