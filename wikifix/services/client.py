"""Assembled ApiClient combining all API mixins."""

from wikifix.services.arxiv import ArxivMixin
from wikifix.services.base import ApiClientCore
from wikifix.services.crossref import CrossRefMixin
from wikifix.services.datacite import DataCiteMixin
from wikifix.services.europe_pmc import EuropePmcMixin
from wikifix.services.ncbi import NcbiMixin
from wikifix.services.openalex import OpenAlexMixin
from wikifix.services.openlibrary import OpenLibraryMixin
from wikifix.services.semantic_scholar import SemanticScholarMixin
from wikifix.services.wayback import WaybackMixin


class ApiClient(
    CrossRefMixin,
    NcbiMixin,
    EuropePmcMixin,
    ArxivMixin,
    OpenLibraryMixin,
    WaybackMixin,
    OpenAlexMixin,
    DataCiteMixin,
    SemanticScholarMixin,
    ApiClientCore,
):
    """Rate-limited API client for all external citation data sources."""
