"""
Configuration, enums, and data models for the wikifix pipeline.
"""

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Mode(Enum):
    """Operating mode for citation processing."""

    INCREMENTAL = auto()
    FORCE_REFRESH = auto()


@dataclass(frozen=True)
class ApiConfig:
    """Rate limiting, API key, and caching configuration for external APIs."""

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
    crossref_email: str = ""
    ncbi_api_key: str = ""
    semantic_scholar_api_key: str = ""
    cache_dir: str = ""
    cache_ttl: int = 604800
    max_workers: int = 4

    @staticmethod
    def from_env(path: str | None = None, **overrides) -> "ApiConfig":
        """Load API config from a .env file, falling back to env vars."""
        if path:
            try:
                import dotenv

                dotenv.load_dotenv(path)
            except Exception:
                pass
        email = os.environ.get("CROSSREF_EMAIL", "")
        ncbi_key = os.environ.get("NCBI_API_KEY", "")
        ss_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
        cache_dir = os.environ.get("WIKIFIX_CACHE_DIR", "")
        ncbi_delay = 0.1 if ncbi_key else 0.34
        ss_delay = 0.1 if ss_key else 0.5
        ua = (
            f"WikiCitationFixer/3.0 (mailto:{email})"
            if email
            else "WikiCitationFixer/3.0"
        )
        kwargs = dict(
            user_agent=ua,
            ncbi_delay=ncbi_delay,
            semantic_scholar_delay=ss_delay,
            crossref_email=email,
            ncbi_api_key=ncbi_key,
            semantic_scholar_api_key=ss_key,
            cache_dir=cache_dir,
        )
        kwargs.update(overrides)
        return ApiConfig(**kwargs)
        return ApiConfig(
            user_agent=ua,
            ncbi_delay=ncbi_delay,
            semantic_scholar_delay=ss_delay,
            crossref_email=email,
            ncbi_api_key=ncbi_key,
            semantic_scholar_api_key=ss_key,
        )


@dataclass
class ProcessingResult:
    """Result from a single module's processing."""

    text: str
    changes: dict[str, bool]
    new_template_type: Optional[str] = None
    rename_params: dict[str, str] = field(default_factory=dict)
    drop_params: set[str] = field(default_factory=set)

    def any_changed(self) -> bool:
        """Check whether any module reported a change."""
        return any(self.changes.values())


@dataclass
class CitationStats:
    """Accumulated statistics across all citations."""

    total: int = 0
    module_stats: dict[str, int] = field(default_factory=dict)
