"""
Fix modules for the wikifix pipeline.

Each module is a class inheriting from CitationModule that transforms
the body text of a citation template and reports what changed.
"""

from wikifix.modules.archive import ArchiveModule
from wikifix.modules.authors import AuthorModule
from wikifix.modules.cleanup import CleanupModule
from wikifix.modules.dates import DateModule
from wikifix.modules.dedup import DedupModule
from wikifix.modules.expand import ExpandModule
from wikifix.modules.ids import IdEnrichmentModule
from wikifix.modules.sort import SortModule
from wikifix.modules.spacing import SpacingModule

__all__ = [
    "ArchiveModule",
    "AuthorModule",
    "CleanupModule",
    "DateModule",
    "DedupModule",
    "ExpandModule",
    "IdEnrichmentModule",
    "SortModule",
    "SpacingModule",
]
