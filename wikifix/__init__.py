"""
wikifix — Universal Wikipedia Citation Fixer
=============================================
A modular, multi-purpose citation enhancement framework.

Features:
- Modular pipeline architecture (enable/disable any fix)
- Multiple cite template support (journal, book, web, news, thesis, ...)
- Citation expansion via DOI/PMID/arXiv/ISBN (CrossRef, Europe PMC, arXiv, Open Library)
- Author style conversion: Vancouver ↔ normal (both directions)
- Author full name enrichment (CrossRef, OpenAlex, DataCite, PubMed)
- Date normalization to Wikipedia style (Month Year)
- ID enrichment: PMID, PMC, ISSN, DOI, S2CID
- Wayback Machine archive-url/archive-date injection for web citations
- Parameter spacing formatting
- Parameter sorting to Wikipedia standard order
- Duplicate citation detection
- Incremental & force-refresh modes

Usage:
    python -m wikifix                     # default pipeline
    python -m wikifix --modules authors,dates,ids,spacing
    python -m wikifix --list-modules
    python -m wikifix --help
"""

from wikifix.pipeline import CitationPipeline
from wikifix.config import Mode, ApiConfig
from wikifix.modules.authors import AuthorModule
from wikifix.modules.dates import DateModule
from wikifix.modules.ids import IdEnrichmentModule
from wikifix.modules.spacing import SpacingModule
from wikifix.modules.dedup import DedupModule
from wikifix.modules.sort import SortModule
from wikifix.modules.expand import ExpandModule
from wikifix.modules.archive import ArchiveModule

__version__ = "3.0.0"
__author__ = "Wolren"
__license__ = "MIT"
