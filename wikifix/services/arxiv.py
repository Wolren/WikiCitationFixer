"""arXiv API mixin: fetch metadata by arXiv ID."""

import xml.etree.ElementTree as ET
from typing import Any, cast

from wikifix.cache import ResponseCache
from wikifix.logger import get_logger
from wikifix.services.base import _ApiClientCoreProtocol

log = get_logger()


class ArxivMixin:
    """arXiv API methods.

    Requires self._session, _rate_limit, _cached_get/set, clean_arxiv.
    """

    def fetch_arxiv(
        self: _ApiClientCoreProtocol, arxiv_id: str
    ) -> dict[str, Any] | None:
        arxiv_id = self.clean_arxiv(arxiv_id)
        cache_key = ResponseCache.make_key("arxiv", "meta", arxiv_id)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)
        self._rate_limit("arxiv", self.config.arxiv_delay)
        try:
            resp = self._session.get(
                f"https://export.arxiv.org/api/query?id_list={arxiv_id}",
                timeout=15,
            )
            if resp.ok:
                root = ET.fromstring(resp.text)
                ns = {
                    "atom": "http://www.w3.org/2005/Atom",
                    "arxiv": "http://arxiv.org/schemas/atom",
                }
                entry = root.find("atom:entry", ns)
                if entry is None:
                    return None
                title = entry.findtext("atom:title", "", ns).strip()
                summary = entry.findtext("atom:summary", "", ns).strip()
                published = entry.findtext("atom:published", "", ns).strip()
                authors = []
                for a in entry.findall("atom:author", ns):
                    name = a.findtext("atom:name", "", ns).strip()
                    if name:
                        parts = name.rsplit(" ", 1)
                        if len(parts) == 2:
                            authors.append((parts[0], parts[1]))
                        else:
                            authors.append((name, ""))
                doi_el = entry.find("arxiv:doi", ns)
                doi = (
                    doi_el.text.strip() if doi_el is not None and doi_el.text else None
                )
                result: dict[str, Any] = {
                    "title": title,
                    "authors": authors,
                    "date": published[:10] if published else None,
                    "doi": doi,
                    "abstract": summary,
                    "arxiv_id": arxiv_id,
                }
                self._cached_set(cache_key, result)
                return result
        except Exception as e:
            log.warning("  arXiv fetch failed for %s: %s", arxiv_id, e)
        return None
