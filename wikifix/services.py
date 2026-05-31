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

import re
import time
from typing import Optional

import requests

from wikifix.config import ApiConfig


class ApiClient:
    """Rate-limited API client aggregating CrossRef, NCBI, and Semantic Scholar."""

    def __init__(self, config: ApiConfig = ApiConfig()):
        self.config = config
        self._last_call = 0.0

    def _rate_limit(self, delay: float):
        elapsed = time.time() - self._last_call
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_call = time.time()

    # ---- DOI helpers ----

    @staticmethod
    def clean_doi(doi: str) -> str:
        return re.sub(
            r"https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.IGNORECASE
        )

    @staticmethod
    def clean_arxiv(arxiv_id: str) -> str:
        return re.sub(
            r"https?://arxiv\.org/abs/", "", arxiv_id.strip(), flags=re.IGNORECASE
        )

    @staticmethod
    def clean_isbn(isbn: str) -> str:
        return re.sub(r"[^0-9X]", "", isbn.strip().upper())

    @staticmethod
    def clean_url(url: str) -> str:
        url = url.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    # ---- CrossRef ----

    def fetch_crossref(self, doi: str) -> Optional[dict]:
        """Fetch CrossRef work metadata for a DOI."""
        self._rate_limit(self.config.crossref_delay)
        doi = self.clean_doi(doi)
        try:
            resp = requests.get(
                f"https://api.crossref.org/works/{doi}",
                headers={"User-Agent": self.config.user_agent},
                timeout=10,
            )
            if resp.ok:
                return resp.json().get("message")
        except Exception as e:
            print(f"  CrossRef fetch failed for DOI {doi}: {e}")
        return None

    def doi_to_issn(self, doi: str) -> Optional[str]:
        msg = self.fetch_crossref(doi)
        if msg:
            issns = msg.get("ISSN", [])
            return issns[0] if issns else None
        return None

    def doi_to_authors(self, doi: str) -> list:
        """Fetch full author names from CrossRef. Returns [(family, given), ...]."""
        msg = self.fetch_crossref(doi)
        if msg:
            authors = msg.get("author", [])
            return [(a["family"], a.get("given", "")) for a in authors if "family" in a]
        return []

    # ---- NCBI E-utilities ----

    def doi_to_pmid(self, doi: str) -> Optional[str]:
        self._rate_limit(self.config.ncbi_delay)
        doi = self.clean_doi(doi)
        params = {"db": "pubmed", "term": f"{doi}[DOI]", "retmode": "json"}
        try:
            resp = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params=params,
                timeout=10,
            )
            if resp.ok:
                ids = resp.json().get("esearchresult", {}).get("idlist", [])
                return ids[0] if ids else None
        except Exception as e:
            print(f"  PMID fetch failed for DOI {doi}: {e}")
        return None

    def pmid_to_pmc(self, pmid: str) -> Optional[str]:
        self._rate_limit(self.config.ncbi_delay)
        params = {"ids": pmid, "format": "json"}
        try:
            resp = requests.get(
                "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                params=params,
                timeout=10,
            )
            if resp.ok:
                pmc = resp.json().get("records", [{}])[0].get("pmcid", "")
                return pmc.removeprefix("PMC") if pmc else None
        except Exception as e:
            print(f"  PMC fetch failed for PMID {pmid}: {e}")
        return None

    def doi_to_authors_pubmed(self, doi: str) -> list:
        """Fetch author names from PubMed (fallback when CrossRef returns only initials)."""
        pmid = self.doi_to_pmid(doi)
        if not pmid:
            return []
        self._rate_limit(self.config.ncbi_delay)
        try:
            resp = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params={"db": "pubmed", "id": pmid, "retmode": "json"},
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
                return result
        except Exception as e:
            print(f"  PubMed author fetch failed for DOI {doi}: {e}")
        return []

    # ---- Europe PMC ----

    def fetch_europepmc(self, doi: str) -> Optional[dict]:
        """Fetch full metadata from Europe PMC by DOI."""
        self._rate_limit(self.config.europepmc_delay)
        doi = self.clean_doi(doi)
        try:
            resp = requests.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                params={"query": f"DOI:{doi}", "format": "json", "resultType": "core"},
                timeout=10,
            )
            if resp.ok:
                results = resp.json().get("resultList", {}).get("result", [])
                if results:
                    return results[0]
        except Exception as e:
            print(f"  Europe PMC fetch failed for DOI {doi}: {e}")
        return None

    def pmid_to_metadata_europepmc(self, pmid: str) -> Optional[dict]:
        """Fetch full metadata from Europe PMC by PMID."""
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
                if results:
                    return results[0]
        except Exception as e:
            print(f"  Europe PMC fetch failed for PMID {pmid}: {e}")
        return None

    # ---- arXiv ----

    def fetch_arxiv(self, arxiv_id: str) -> Optional[dict]:
        """Fetch metadata from arXiv API by arXiv ID."""
        self._rate_limit(self.config.arxiv_delay)
        arxiv_id = self.clean_arxiv(arxiv_id)
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
                doi = doi_el.text.strip() if doi_el is not None else None
                return {
                    "title": title,
                    "authors": authors,
                    "date": published[:10] if published else None,
                    "doi": doi,
                    "abstract": summary,
                    "arxiv_id": arxiv_id,
                }
        except Exception as e:
            print(f"  arXiv fetch failed for {arxiv_id}: {e}")
        return None

    # ---- Open Library ----

    def fetch_openlibrary(self, isbn: str) -> Optional[dict]:
        """Fetch book metadata from Open Library by ISBN.

        Retries up to 3 times on connection errors.
        """
        import time as _time

        isbn = self.clean_isbn(isbn)
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
                return {
                    "title": title,
                    "authors": authors,
                    "date": publish_date,
                    "publisher": publisher,
                    "isbn": isbn,
                }
            except Exception as e:
                if attempt < 2:
                    _time.sleep(1 * (attempt + 1))
                    continue
                print(f"  Open Library fetch failed for ISBN {isbn}: {e}")
        return None

    def check_wayback(self, url: str) -> Optional[tuple]:
        """Check Wayback Machine for an archived snapshot of *url*.

        Returns (archive_url, archive_date_str) or None.
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
                    ts = closest["timestamp"]
                    date_str = ts[:10]  # YYYY-MM-DD
                    return (archive_url, date_str)
        except Exception as e:
            print(f"  Wayback Machine check failed for {url}: {e}")
        return None

    # ---- OpenAlex ----

    def doi_to_authors_openalex(self, doi: str) -> list:
        """Fetch author names from OpenAlex."""
        self._rate_limit(self.config.openalex_delay)
        doi = self.clean_doi(doi)
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
                    # Parse "Smith, John A." → (Smith, John A.)
                    # Or "John A. Smith" → (Smith, John A.)
                    if ", " in display_name:
                        parts = display_name.split(", ", 1)
                        result.append((parts[0].strip(), parts[1].strip()))
                    else:
                        tokens = display_name.strip().split()
                        if len(tokens) >= 2:
                            result.append((tokens[-1], " ".join(tokens[:-1])))
                        elif tokens:
                            result.append((tokens[0], ""))
                return result
        except Exception as e:
            print(f"  OpenAlex fetch failed for DOI {doi}: {e}")
        return []

    # ---- DataCite ----

    def doi_to_authors_datacite(self, doi: str) -> list:
        """Fetch author names from DataCite."""
        self._rate_limit(self.config.datacite_delay)
        doi = self.clean_doi(doi)
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
                        # Fallback: parse "Smith, John" format
                        name = c["name"]
                        if ", " in name:
                            parts = name.split(", ", 1)
                            result.append((parts[0].strip(), parts[1].strip()))
                        else:
                            result.append((name, ""))
                return result
        except Exception as e:
            print(f"  DataCite fetch failed for DOI {doi}: {e}")
        return []

    # ---- Semantic Scholar ----

    def doi_to_s2cid(self, doi: str) -> Optional[str]:
        self._rate_limit(self.config.semantic_scholar_delay)
        doi = self.clean_doi(doi)
        try:
            resp = requests.get(
                f"https://api.semanticscholar.org/v1/paper/{doi}",
                headers={"User-Agent": self.config.user_agent},
                timeout=10,
            )
            if resp.ok:
                return resp.json().get("paperId")
        except Exception as e:
            print(f"  S2CID fetch failed for DOI {doi}: {e}")
        return None
