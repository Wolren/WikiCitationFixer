# mypy: disable-error-code="attr-defined"
"""Open Library API mixin: fetch book metadata by ISBN."""

import time
from typing import Any, cast

from wikifix.logger import get_logger
from wikifix.cache import ResponseCache

log = get_logger()


class OpenLibraryMixin:
    """Open Library API methods. Requires self._session, _rate_limit, _cached_get/set, clean_isbn."""

    def fetch_openlibrary(self, isbn: str) -> dict[str, Any] | None:
        isbn = self.clean_isbn(isbn)
        cache_key = ResponseCache.make_key("openlibrary", "book", isbn)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)
        for attempt in range(3):
            self._rate_limit("openlibrary", self.config.openlibrary_delay)
            try:
                resp = self._session.get(
                    "https://openlibrary.org/api/books",
                    params={
                        "bibkeys": f"ISBN:{isbn}",
                        "format": "json",
                        "jscmd": "data",
                    },
                    timeout=15,
                )
                if not resp.ok:
                    if attempt < 2:
                        time.sleep(1 * (attempt + 1))
                        continue
                    return None
                data = resp.json()
                key = f"ISBN:{isbn}"
                if key not in data:
                    return None
                book = data[key]
                title = book.get("title", "")
                authors = []
                for a in book.get("authors", []):
                    name = a.get("name", "")
                    if name:
                        parts = name.rsplit(" ", 1)
                        if len(parts) == 2:
                            authors.append((parts[0], parts[1]))
                        else:
                            authors.append((name, ""))
                publish_date = book.get("publish_date", "")
                publishers = book.get("publishers", [])
                publisher = publishers[0].get("name", "") if publishers else ""
                result = {
                    "title": title,
                    "authors": authors,
                    "date": publish_date,
                    "publisher": publisher,
                    "isbn": isbn,
                }
                self._cached_set(cache_key, result)
                return result
            except Exception as e:
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                    continue
                log.warning("  Open Library fetch failed for ISBN %s: %s", isbn, e)
        return None
