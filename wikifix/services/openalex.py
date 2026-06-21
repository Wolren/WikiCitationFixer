# mypy: disable-error-code="attr-defined"
"""OpenAlex API mixin: DOI→authors, DOI→QID."""

from typing import cast

from wikifix.cache import ResponseCache
from wikifix.logger import get_logger

log = get_logger()


class OpenAlexMixin:
    """OpenAlex API methods.

    Requires self._session, _rate_limit, _cached_get/set, clean_doi.
    """

    def doi_to_authors_openalex(self, doi: str) -> list[tuple[str, str]]:
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("openalex", "authors", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(list[tuple[str, str]], cached)
        self._rate_limit("openalex", self.config.openalex_delay)
        try:
            resp = self._session.get(
                f"https://api.openalex.org/works/https://doi.org/{doi}",
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                authorships = data.get("authorships", [])
                result: list[tuple[str, str]] = []
                for a in authorships:
                    author = a.get("author", {})
                    display_name = author.get("display_name", "")
                    if not display_name:
                        continue
                    if ", " in display_name:
                        parts = display_name.split(", ", 1)
                        result.append((parts[0].strip(), parts[1].strip()))
                    else:
                        tokens = display_name.strip().split()
                        if len(tokens) >= 2:
                            result.append((tokens[-1], " ".join(tokens[:-1])))
                        elif tokens:
                            result.append((tokens[0], ""))
                self._cached_set(cache_key, result)
                return result
        except Exception as e:
            log.warning("  OpenAlex fetch failed for DOI %s: %s", doi, e)
        return []

    def doi_to_qid(self, doi: str) -> str | None:
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("openalex", "qid", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(str, cached)
        self._rate_limit("openalex", self.config.openalex_delay)
        try:
            resp = self._session.get(
                f"https://api.openalex.org/works/https://doi.org/{doi}",
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                qid = data.get("ids", {}).get("wikidata", "")
                if qid:
                    qid = cast(str, qid.rstrip("/").split("/")[-1])
                    self._cached_set(cache_key, qid)
                    return qid
        except Exception as e:
            log.warning("  QID fetch failed for DOI %s: %s", doi, e)
        return None
