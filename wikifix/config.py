"""
Configuration, enums, and data models for the wikifix pipeline.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Mode(Enum):
    """Operating mode for citation processing."""

    INCREMENTAL = auto()
    FORCE_REFRESH = auto()


@dataclass(frozen=True)
class ApiConfig:
    """Rate limiting and identification for external APIs."""

    user_agent: str = "WikiCitationFixer/3.0"
    ncbi_tool: str = "WikiCitationFixer"
    ncbi_delay: float = 0.34
    crossref_delay: float = 0.05
    semantic_scholar_delay: float = 0.5
    openalex_delay: float = 0.1
    datacite_delay: float = 0.1
    europepmc_delay: float = 0.1
    arxiv_delay: float = 0.1
    openlibrary_delay: float = 0.2
    wayback_delay: float = 0.1


@dataclass
class ProcessingResult:
    """Result from a single module's processing."""

    text: str
    changes: dict[str, bool]
    new_template_type: Optional[str] = None
    rename_params: dict[str, str] = field(default_factory=dict)
    drop_params: set[str] = field(default_factory=set)

    def any_changed(self) -> bool:
        return any(self.changes.values())


@dataclass
class CitationStats:
    """Accumulated statistics across all citations."""

    total: int = 0
    module_stats: dict[str, int] = field(default_factory=dict)
