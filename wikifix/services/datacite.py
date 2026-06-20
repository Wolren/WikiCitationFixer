# mypy: disable-error-code="attr-defined"
"""DataCite API mixin: DOI→authors."""

from typing import Any, cast

from wikifix.logger import get_logger
from wikifix.cache import ResponseCache

log = get_logger()


class DataCiteMixin:
    """DataCite API methods. Requires self._session, _rate_limit, _cached_get/set, clean_doi."""

    def doi_to_authors_datacite(self, doi: str) -> list[tuple[str, str]]:
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("datacite", "authors", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(list[tuple[str, str]], cached)
        self._rate_limit("datacite", self.config.datacite_delay)
        try:
            resp = self._session.get(
                f"https://api.datacite.org/dois/{doi}",
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                attrs = data.get("data", {}).get("attributes", {})
                creators = attrs.get("creators", [])
                result: list[tuple[str, str]] = []
                for c in creators:
                    family = c.get("familyName", "")
                    given = c.get("givenName", "")
                    if family:
                        result.append((family, given))
                    elif c.get("name"):
                        name = c["name"]
                        if ", " in name:
                            parts = name.split(", ", 1)
                            result.append((parts[0].strip(), parts[1].strip()))
                        else:
                            result.append((name, ""))
                self._cached_set(cache_key, result)
                return result
        except Exception as e:
            log.warning("  DataCite fetch failed for DOI %s: %s", doi, e)
        return []
