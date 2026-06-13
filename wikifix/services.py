"""
Shared API clients for external data sources.

Provides rate-limited access to:
    - CrossRef (DOI → metadata, ISSN, authors)
    - NCBI E-utilities  (DOI → PMID, authors)
    - NCBI PMC ID Converter  (PMID → PMC)
    - OpenAlex  (DOI → authors)
    - DataCite  (DOI → authors)
    - Semantic Scholar  (DOI → S2CID)
    - Europe PMC  (DOI/PMID → full metadata)
    - arXiv  (arXiv ID → metadata)
    - Open Library  (ISBN → book metadata)
    - Wayback Machine  (URL → archive snapshot)
"""

import os
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

from wikifix.cache import ResponseCache
from wikifix.config import ApiConfig, Mode
from wikifix.logger import get_logger

log = get_logger()


class ApiClient:
    """Rate-limited API client with optional caching and concurrent fetch support."""

    def __init__(self, config: ApiConfig = ApiConfig(), mode: Mode = Mode.INCREMENTAL):
        """Initialize the API client with rate-limit, cache, concurrency, and mode."""
        self.config = config
        self.mode = mode
        self._last_call = 0.0
        self._lock = threading.Lock()
        self._cache: ResponseCache | None = None
        cd = config.cache_dir
        if cd is None:
            cd = os.path.join(
                os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")), "wikifix"
            )
        if cd:
            self._cache = ResponseCache(cd, config.cache_ttl)
        # cd == "" means cache disabled

    def _rate_limit(self, delay: float):
        """Sleep if needed to respect the per-API rate-limit delay (thread-safe)."""
        with self._lock:
            elapsed = time.time() - self._last_call
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_call = time.time()

    # ---- Caching helpers ----

    def _cached_get(self, key: str) -> Any | None:
        """Return cached value, logging a hit. Skips cache in FORCE_REFRESH mode."""
        if self.mode == Mode.FORCE_REFRESH or not self._cache:
            return None
        val = self._cache.get(key)
        if val is not None:
            log.debug("  [cache HIT] %s", key[:16])
        return val

    def _cached_set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        if self._cache:
            self._cache.set(key, value)

    def clear_cache(self) -> None:
        """Wipe the entire disk cache."""
        if self._cache:
            self._cache.clear()
            log.info("Cache cleared.")

    # ---- Concurrent fetch helper ----

    @staticmethod
    def concurrent_fetch(
        tasks: list[tuple[str, Callable[[], Any]]],
        max_workers: int = 4,
    ) -> dict[str, Any]:
        """Run multiple zero-argument callables concurrently.

        Args:
            tasks:   List of ``(label, callable)`` pairs.
            max_workers: Thread pool size.

        Returns:
            ``{label: result}`` dict. Exceptions are caught and stored as
            ``None`` with a warning logged.
        """
        results: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_to_label = {pool.submit(fn): label for label, fn in tasks}
            for future in as_completed(fut_to_label):
                label = fut_to_label[future]
                try:
                    results[label] = future.result()
                except Exception as exc:
                    log.warning("  concurrent %s failed: %s", label, exc)
                    results[label] = None
        return results

    # ---- DOI helpers ----

    @staticmethod
    def clean_doi(doi: str) -> str:
        """Strip ``https://doi.org/`` prefix from a DOI string."""
        return re.sub(
            r"https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.IGNORECASE
        )

    @staticmethod
    def clean_arxiv(arxiv_id: str) -> str:
        """Strip ``https://arxiv.org/abs/`` prefix from an arXiv ID."""
        return re.sub(
            r"https?://arxiv\.org/abs/", "", arxiv_id.strip(), flags=re.IGNORECASE
        )

    @staticmethod
    def clean_isbn(isbn: str) -> str:
        """Strip non-digit non-X characters from an ISBN."""
        return re.sub(r"[^0-9X]", "", isbn.strip().upper())

    @staticmethod
    def clean_url(url: str) -> str:
        """Ensure a URL has a scheme, defaulting to https."""
        url = url.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    # ---- CrossRef ----

    def fetch_crossref(self, doi: str) -> dict | None:
        """Fetch CrossRef work metadata for a DOI."""
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("crossref", "work", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.crossref_delay)
        try:
            resp = requests.get(
                f"https://api.crossref.org/works/{doi}",
                headers={"User-Agent": self.config.user_agent},
                timeout=10,
            )
            if resp.ok:
                msg = resp.json().get("message")
                self._cached_set(cache_key, msg)
                return msg
        except Exception as e:
            log.warning("  CrossRef fetch failed for DOI %s: %s", doi, e)
        return None

    def doi_to_issn(self, doi: str) -> str | None:
        """Look up ISSN from CrossRef by DOI."""
        msg = self.fetch_crossref(doi)
        if msg:
            issns = msg.get("ISSN", [])
            return issns[0] if issns else None
        return None

    def doi_is_oa(self, doi: str) -> bool:
        """Check if a DOI is open-access via CrossRef license metadata."""
        msg = self.fetch_crossref(doi)
        if not msg:
            return False
        for lic in msg.get("license", []):
            url = lic.get("URL", "")
            if "creativecommons" in url.lower():
                return True
        return False

    def doi_to_authors(self, doi: str) -> list[tuple[str, str]]:
        """Fetch full author names from CrossRef by DOI."""
        msg = self.fetch_crossref(doi)
        if msg:
            authors = msg.get("author", [])
            return [(a["family"], a.get("given", "")) for a in authors if "family" in a]
        return []

    # ---- NCBI E-utilities ----

    def _ncbi_params(self, **kwargs) -> dict[str, str]:
        """Build query params for NCBI, appending API key if configured."""
        params = dict(kwargs)
        if self.config.ncbi_api_key:
            params["api_key"] = self.config.ncbi_api_key
        return params

    def doi_to_pmid(self, doi: str) -> str | None:
        """Look up PubMed ID from NCBI E-utilities by DOI."""
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("ncbi", "doi_to_pmid", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.ncbi_delay)
        params = self._ncbi_params(db="pubmed", term=f"{doi}[DOI]", retmode="json")
        try:
            resp = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params=params,
                timeout=10,
            )
            if resp.ok:
                ids = resp.json().get("esearchresult", {}).get("idlist", [])
                val = ids[0] if ids else None
                self._cached_set(cache_key, val)
                return val
        except Exception as e:
            log.warning("  PMID fetch failed for DOI %s: %s", doi, e)
        return None

    def pmid_to_pmc(self, pmid: str) -> str | None:
        """Look up PMC ID from NCBI ID Converter by PMID."""
        cache_key = ResponseCache.make_key("ncbi", "pmid_to_pmc", pmid)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.ncbi_delay)
        params = self._ncbi_params(ids=pmid, format="json")
        try:
            resp = requests.get(
                "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                params=params,
                timeout=10,
            )
            if resp.ok:
                pmc = resp.json().get("records", [{}])[0].get("pmcid", "")
                val = pmc.removeprefix("PMC") if pmc else None
                self._cached_set(cache_key, val)
                return val
        except Exception as e:
            log.warning("  PMC fetch failed for PMID %s: %s", pmid, e)
        return None

    def doi_to_authors_pubmed(self, doi: str) -> list[tuple[str, str]]:
        """Fetch author names from PubMed as fallback for abbreviated CrossRef names."""
        pmid = self.doi_to_pmid(doi)
        if not pmid:
            return []
        cache_key = ResponseCache.make_key("ncbi", "authors_pubmed", pmid)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.ncbi_delay)
        try:
            params = self._ncbi_params(db="pubmed", id=pmid, retmode="json")
            resp = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params=params,
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                authors = data.get("result", {}).get(pmid, {}).get("authors", [])
                result = []
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

    # ---- Europe PMC ----

    def fetch_europepmc(self, doi: str) -> dict | None:
        """Fetch full metadata from Europe PMC by DOI."""
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("europepmc", "by_doi", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.europepmc_delay)
        try:
            resp = requests.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                params={"query": f"DOI:{doi}", "format": "json", "resultType": "core"},
                timeout=10,
            )
            if resp.ok:
                results = resp.json().get("resultList", {}).get("result", [])
                val = results[0] if results else None
                self._cached_set(cache_key, val)
                return val
        except Exception as e:
            log.warning("  Europe PMC fetch failed for DOI %s: %s", doi, e)
        return None

    def pmid_to_metadata_europepmc(self, pmid: str) -> dict | None:
        """Fetch full metadata from Europe PMC by PMID."""
        cache_key = ResponseCache.make_key("europepmc", "by_pmid", pmid)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.europepmc_delay)
        try:
            resp = requests.get(
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
                return val
        except Exception as e:
            log.warning("  Europe PMC fetch failed for PMID %s: %s", pmid, e)
        return None

    # ---- arXiv ----

    def fetch_arxiv(self, arxiv_id: str) -> dict | None:
        """Fetch metadata from arXiv API by arXiv ID."""
        arxiv_id = self.clean_arxiv(arxiv_id)
        cache_key = ResponseCache.make_key("arxiv", "meta", arxiv_id)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.arxiv_delay)
        import xml.etree.ElementTree as ET

        try:
            resp = requests.get(
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
                result = {
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

    # ---- Open Library ----

    def fetch_openlibrary(self, isbn: str) -> dict | None:
        """Fetch book metadata from Open Library by ISBN.

        Retries up to 3 times on connection errors.
        """
        import time as _time

        isbn = self.clean_isbn(isbn)
        cache_key = ResponseCache.make_key("openlibrary", "book", isbn)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        for attempt in range(3):
            self._rate_limit(self.config.openlibrary_delay)
            try:
                resp = requests.get(
                    "https://openlibrary.org/api/books",
                    params={
                        "bibkeys": f"ISBN:{isbn}",
                        "format": "json",
                        "jscmd": "data",
                    },
                    headers={"User-Agent": self.config.user_agent},
                    timeout=15,
                )
                if not resp.ok:
                    if attempt < 2:
                        _time.sleep(1 * (attempt + 1))
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
                    _time.sleep(1 * (attempt + 1))
                    continue
                log.warning("  Open Library fetch failed for ISBN %s: %s", isbn, e)
        return None

    def check_wayback(self, url: str) -> tuple | None:
        """Check Wayback Machine for an archived snapshot of *url*.

        Returns:
            ``(archive_url, archive_date_str)`` or None.
        """
        self._rate_limit(self.config.wayback_delay)
        url = self.clean_url(url)
        try:
            resp = requests.get(
                "https://archive.org/wayback/available",
                params={"url": url},
                timeout=60,
            )
            if resp.ok:
                data = resp.json()
                snaps = data.get("archived_snapshots", {})
                closest = snaps.get("closest", {})
                if closest.get("available"):
                    archive_url = closest["url"]
                    ts = closest["timestamp"]  # YYYYMMDDHHMMSS
                    date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                    return (archive_url, date_str)
        except Exception as e:
            log.warning("  Wayback Machine check failed for %s: %s", url, e)
        return None

    def save_wayback(self, url: str) -> bool:
        """Request Wayback Machine to create a new snapshot of *url*.

        Returns:
            True if the save request was accepted (2xx status).
        """
        self._rate_limit(self.config.wayback_delay * 5)
        url = self.clean_url(url)
        try:
            resp = requests.get(
                f"https://web.archive.org/save/{url}",
                timeout=60,
                allow_redirects=True,
            )
            if resp.status_code == 429:
                log.warning("    Wayback rate-limited (429), skipping save")
            return resp.ok
        except Exception as e:
            log.warning("  Wayback Machine save failed for %s: %s", url, e)
        return False

    # ---- OpenAlex ----

    def doi_to_authors_openalex(self, doi: str) -> list[tuple[str, str]]:
        """Fetch author names from OpenAlex by DOI."""
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("openalex", "authors", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.openalex_delay)
        try:
            resp = requests.get(
                f"https://api.openalex.org/works/https://doi.org/{doi}",
                headers={"User-Agent": self.config.user_agent},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                authorships = data.get("authorships", [])
                result = []
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

    # ---- DataCite ----

    def doi_to_authors_datacite(self, doi: str) -> list[tuple[str, str]]:
        """Fetch author names from DataCite by DOI."""
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("datacite", "authors", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.datacite_delay)
        try:
            resp = requests.get(
                f"https://api.datacite.org/dois/{doi}",
                headers={"User-Agent": self.config.user_agent},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                attrs = data.get("data", {}).get("attributes", {})
                creators = attrs.get("creators", [])
                result = []
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

    # ---- Semantic Scholar ----

    def doi_to_s2cid(self, doi: str) -> str | None:
        """Look up Semantic Scholar paper ID by DOI."""
        doi = self.clean_doi(doi)
        cache_key = ResponseCache.make_key("semantic", "s2cid", doi)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cached
        self._rate_limit(self.config.semantic_scholar_delay)
        headers = {"User-Agent": self.config.user_agent}
        if self.config.semantic_scholar_api_key:
            headers["x-api-key"] = self.config.semantic_scholar_api_key
        try:
            resp = requests.get(
                f"https://api.semanticscholar.org/v1/paper/{doi}",
                headers=headers,
                timeout=10,
            )
            if resp.ok:
                val = resp.json().get("paperId")
                self._cached_set(cache_key, val)
                return val
        except Exception as e:
            log.warning("  S2CID fetch failed for DOI %s: %s", doi, e)
        return None
