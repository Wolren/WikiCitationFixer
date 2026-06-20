# mypy: disable-error-code="attr-defined"
"""NCBI E-utilities mixin: DOI→PMID, PMID→PMC, PubMed author fetch."""

from typing import Any, cast

from wikifix.logger import get_logger
from wikifix.cache import ResponseCache

log = get_logger()


class NcbiMixin:
    """NCBI API methods. Requires self._session, _rate_limit, _cached_get/set, clean_doi."""

    def _ncbi_params(self, **kwargs: str | None) -> dict[str, str | None]:
        params: dict[str, str | None] = dict(kwargs)
        if self.config.ncbi_api_key:
            params["api_key"] = self.config.ncbi_api_key
        return params

    def doi_to_pmid(self, doi: str) -> str | None:
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("ncbi", "doi_to_pmid", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(str, cached)
        self._rate_limit("ncbi", self.config.ncbi_delay)
        params = self._ncbi_params(db="pubmed", term=f"{doi}[DOI]", retmode="json")
        try:
            resp = self._session.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params=params,
                timeout=10,
            )
            if resp.ok:
                ids = resp.json().get("esearchresult", {}).get("idlist", [])
                val = ids[0] if ids else None
                self._cached_set(cache_key, val)
                return cast(str | None, val)
        except Exception as e:
            log.warning("  PMID fetch failed for DOI %s: %s", doi, e)
        return None

    def pmid_to_pmc(self, pmid: str) -> str | None:
        cache_key = ResponseCache.make_key("ncbi", "pmid_to_pmc", pmid)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(str, cached)
        self._rate_limit("ncbi", self.config.ncbi_delay)
        params = self._ncbi_params(ids=pmid, format="json")
        try:
            resp = self._session.get(
                "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                params=params,
                timeout=10,
            )
            if resp.ok:
                pmc = resp.json().get("records", [{}])[0].get("pmcid", "")
                val = pmc.removeprefix("PMC") if pmc else None
                self._cached_set(cache_key, val)
                return cast(str | None, val)
        except Exception as e:
            log.warning("  PMC fetch failed for PMID %s: %s", pmid, e)
        return None

    def doi_to_authors_pubmed(self, doi: str) -> list[tuple[str, str]]:
        pmid = self.doi_to_pmid(doi)
        if not pmid:
            return []
        cache_key = ResponseCache.make_key("ncbi", "authors_pubmed", pmid)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(list[tuple[str, str]], cached)
        self._rate_limit("ncbi", self.config.ncbi_delay)
        try:
            params = self._ncbi_params(db="pubmed", id=pmid, retmode="json")
            resp = self._session.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params=params,
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                authors = data.get("result", {}).get(pmid, {}).get("authors", [])
                result: list[tuple[str, str]] = []
                for a in authors:
                    name = a.get("name", "")
                    parts = name.rsplit(" ", 1)
                    if len(parts) == 2:
                        result.append((parts[0], parts[1]))
                    elif parts:
                        result.append((parts[0], ""))
                self._cached_set(cache_key, result)
                return result
        except Exception as e:
            log.warning("  PubMed author fetch failed for DOI %s: %s", doi, e)
        return []
