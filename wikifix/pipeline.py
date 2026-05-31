"""
Pipeline orchestrator.

Chains multiple CitationModules together and runs them over every
citation template found in a Wikipedia wikitext source file.
"""

import re
from pathlib import Path
from typing import List, Optional

from wikifix.base import CitationModule
from wikifix.config import Mode, ApiConfig, CitationStats
from wikifix.services import ApiClient


class CitationPipeline:
    """Runs a sequence of modules over all cite templates in a file."""

    CITATION_RE = re.compile(
        r"{{(?:[Cc]ite\s+\w+|[Cc]itation)(.*?)}}(?!})",
        re.DOTALL,
    )

    def __init__(
        self,
        modules: List[CitationModule],
        mode: Mode = Mode.INCREMENTAL,
        api_config: ApiConfig = ApiConfig(),
        author_style: str = "normal",
        refresh_authors: bool = False,
        max_authors: int = 6,
        ids_to_fetch: Optional[List[str]] = None,
    ):
        """Runs a sequence of modules over all cite templates in a file.

        Args:
            modules:
                Ordered list of CitationModule instances to run on each citation.
                Default order when invoked via CLI: expand, authors, dates, ids,
                spacing, archive.
            mode:
                Mode.INCREMENTAL (default) - only adds missing fields.
                Mode.FORCE_REFRESH - removes and re-fetches all identifiers.
            api_config:
                ApiConfig dataclass holding rate-limit delays (api_delay,
                crossref_delay, etc.) and the User-Agent string for all HTTP
                requests to CrossRef, NCBI, Semantic Scholar, etc.
            author_style:
                "normal" (default) - converts |vauthors= into numbered
                |last=/|first= pairs.
                "vancouver" - collapses |last=/|first= into a single
                |vauthors= field.
            refresh_authors:
                False (default) - keeps parsed initials from vauthors.
                True - fetches full given names from CrossRef, OpenAlex,
                DataCite, and PubMed. Requires a DOI in the citation.
            max_authors:
                6 (default) - caps author output at N entries, appending
                "et al" if truncated. 0 means unlimited.
            ids_to_fetch:
                List of identifiers to enrich when a DOI is present.
                Default: ["issn", "pmid", "pmc", "s2cid"].
        """
        self.modules = modules
        self.mode = mode
        self.api = ApiClient(api_config)
        self.author_style = author_style
        self.refresh_authors = refresh_authors
        self.max_authors = max_authors
        self.ids_to_fetch = ids_to_fetch or ["issn", "pmid", "pmc", "s2cid"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_file(self, input_path: Path, output_path: Path):
        """Read wikitext, process all citations, write result."""
        self._print_header()

        text = input_path.read_text(encoding="utf-8")
        matches = list(self.CITATION_RE.finditer(text))
        print(f"Found {len(matches)} citation templates\n")

        # Pre-scan identifiers for duplicate detection
        first_seen = {}
        for m in matches:
            body = m.group(1)
            doi = self._extract_doi(body)
            pmid = self._extract_pmid(body)
            key = doi or pmid
            if key and key not in first_seen:
                first_seen[key] = m.start()

        stats = CitationStats(total=len(matches))

        for idx, match in enumerate(reversed(matches), 1):
            body = match.group(1)
            template_type = self._detect_type(match.group(0))
            title = self._extract_title(body)

            print(f"[{idx}/{len(matches)}] {title}...")

            # Build context
            doi = self._extract_doi(body)
            pmid = self._extract_pmid(body)
            is_dup = False
            if doi:
                is_dup = match.start() != first_seen.get(doi)
            elif pmid and not is_dup:
                is_dup = match.start() != first_seen.get(pmid)
            context = {
                "template_type": template_type,
                "doi": doi,
                "pmid": pmid,
                "title": title,
                "is_duplicate": is_dup,
                "mode": self.mode,
                "api": self.api,
                "author_style": self.author_style,
                "refresh_authors": self.refresh_authors,
                "max_authors": self.max_authors,
                "ids_to_fetch": self.ids_to_fetch,
            }

            # Run module pipeline
            overall_changes = {}
            for mod in self.modules:
                result = mod.process(body, context)
                body = result.text
                overall_changes.update(result.changes)

            # Accumulate stats
            for k, v in overall_changes.items():
                stats.module_stats[k] = stats.module_stats.get(k, 0) + (1 if v else 0)

            # Patch back into source
            text = (
                text[: match.start()]
                + "{{"
                + self._canonical_type(template_type)
                + body
                + "}}"
                + text[match.end() :]
            )

            if any(overall_changes.values()):
                changed = ", ".join(k for k, v in overall_changes.items() if v)
                print(f"  -> {changed}")

        output_path.write_text(text, encoding="utf-8")
        self._print_summary(stats)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_type(full_match: str) -> str:
        """Normalise the template name (cite journal, cite book, citation, …)."""
        m = re.match(r"\{\{(citation|cite\s*\w+)", full_match, re.IGNORECASE)
        return m.group(1).strip().lower() if m else "citation"

    @staticmethod
    def _canonical_type(t: str) -> str:
        """Return lowercase cite type for consistent output."""
        if t.startswith("cite "):
            return t
        return t

    @staticmethod
    def _extract_title(body: str) -> str:
        m = re.search(r"\|\s*title\s*=\s*([^\|]+)", body)
        return m.group(1).strip()[:60] if m else "(no title)"

    @staticmethod
    def _extract_doi(body: str) -> Optional[str]:
        m = re.search(r"\|\s*doi\s*=\s*([^\|}]+)", body)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_pmid(body: str) -> Optional[str]:
        m = re.search(r"\|\s*pmid\s*=\s*(\d+)", body)
        return m.group(1).strip() if m else None

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def _print_header(self):
        mode_label = self.mode.name.replace("_", " ")
        print("=" * 80)
        print(f"WIKIFIX CITATION PIPELINE -- {mode_label}")
        print("=" * 80)
        modules_str = ", ".join(m.name for m in self.modules)
        print(f"Active modules: {modules_str}")
        print(f"Author style:     {self.author_style}")
        ma = self.max_authors if self.max_authors > 0 else "unlimited"
        print(f"Max authors:      {ma}")
        print(f"Refresh authors:  {self.refresh_authors}")
        ids = ", ".join(self.ids_to_fetch)
        print(f"IDs to fetch:     {ids}")
        print()

    def _print_summary(self, stats: CitationStats):
        print("\n" + "=" * 80)
        print("ENHANCEMENT SUMMARY")
        print("=" * 80)
        print(f"Total citations processed: {stats.total}")
        for k, v in sorted(stats.module_stats.items()):
            print(f"  + {k}: {v}")
        print("=" * 80)
