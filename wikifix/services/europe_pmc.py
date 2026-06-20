# mypy: disable-error-code="attr-defined"
"""Europe PMC API mixin: DOI→metadata, PMID→metadata."""

from typing import Any, cast

from wikifix.logger import get_logger
from wikifix.cache import ResponseCache

log = get_logger()


class EuropePmcMixin:
    """Europe PMC API methods. Requires self._session, _rate_limit, _cached_get/set, clean_doi."""

    def fetch_europepmc(self, doi: str) -> dict[str, Any] | None:
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("europepmc", "by_doi", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)
        self._rate_limit("europepmc", self.config.europepmc_delay)
        try:
            resp = self._session.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                params={"query": f"DOI:{doi}", "format": "json", "resultType": "core"},
                timeout=10,
            )
            if resp.ok:
                results = resp.json().get("resultList", {}).get("result", [])
                val = results[0] if results else None
                self._cached_set(cache_key, val)
                return cast(dict[str, Any] | None, val)
        except Exception as e:
            log.warning("  Europe PMC fetch failed for DOI %s: %s", doi, e)
        return None

    def pmid_to_metadata_europepmc(self, pmid: str) -> dict[str, Any] | None:
        cache_key = ResponseCache.make_key("europepmc", "by_pmid", pmid)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)
        self._rate_limit("europepmc", self.config.europepmc_delay)
        try:
            resp = self._session.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                params={
                    "query": f"EXT_ID:{pmid}",
                    "format": "json",
                    "resultType": "core",
                },
                timeout=10,
            )
            if resp.ok:
                results = resp.json().get("resultList", {}).get("result", [])
                val = results[0] if results else None
                self._cached_set(cache_key, val)
                return cast(dict[str, Any] | None, val)
        except Exception as e:
            log.warning("  Europe PMC fetch failed for PMID %s: %s", pmid, e)
        return None
