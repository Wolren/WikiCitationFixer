"""
Fix modules for the wikifix pipeline.

Each module is a class inheriting from CitationModule that transforms
the body text of a citation template and reports what changed.
"""

from wikifix.modules.authors import AuthorModule
from wikifix.modules.dates import DateModule
from wikifix.modules.ids import IdEnrichmentModule
from wikifix.modules.spacing import SpacingModule

__all__ = ["AuthorModule", "DateModule", "IdEnrichmentModule", "SpacingModule"]
