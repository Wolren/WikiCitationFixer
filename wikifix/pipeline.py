"""
Pipeline orchestrator.

Chains multiple CitationModules together and runs them over every
citation template found in a Wikipedia wikitext source file.
"""

import re
import urllib.parse
from pathlib import Path
from typing import List, Optional, Set

from wikifix.base import CitationModule
from wikifix.config import Mode, ApiConfig, CitationStats
from wikifix.services import ApiClient


_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "with",
    }
)


class CitationPipeline:
    """Runs a sequence of modules over all cite templates in a file."""

    CITATION_RE = re.compile(
        r"{{(?:[Cc]ite\s+\w+|[Cc]itation)"
        r"((?:[^{}]|{{[^{}]*}})*)"
        r"}}",
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
        force_archive_all: bool = False,
        create_archive: bool = False,
        ref_names: bool = False,
    ):
        """Runs a sequence of modules over all cite templates in a file.

        Args:
            modules:
                Ordered list of CitationModule instances to run on each citation.
            mode:
                Mode.INCREMENTAL (default) or Mode.FORCE_REFRESH.
            api_config:
                ApiConfig dataclass holding rate-limit delays.
            author_style:
                "normal" or "vancouver".
            refresh_authors:
                Fetch full given names from APIs.
            max_authors:
                Cap author output (0=unlimited).
            ids_to_fetch:
                Identifiers to enrich (issn, pmid, pmc, s2cid).
            force_archive_all:
                Archive all template types, not just cite web/news.
            create_archive:
                Submit unarchived URLs to Wayback for snapshot creation.
            ref_names:
                Auto-generate ref names from first author surname + year.
        """
        self.modules = modules
        self.mode = mode
        self.api = ApiClient(api_config)
        self.author_style = author_style
        self.refresh_authors = refresh_authors
        self.max_authors = max_authors
        self.ids_to_fetch = ids_to_fetch or ["issn", "pmid", "pmc", "s2cid"]
        self.force_archive_all = force_archive_all
        self.create_archive = create_archive
        self.ref_names = ref_names

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
        ref_renames = {}  # old_name -> new_name
        used_ref_names: Set[str] = set(
            m.group(1) for m in re.finditer(r'<ref\s+name\s*=\s*"([^"]*)"', text)
        )

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
                "force_archive_all": self.force_archive_all,
                "create_archive": self.create_archive,
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

            # Auto-generate ref name from first author surname + year
            if self.ref_names:
                text = self._add_ref_name(
                    text,
                    match.start(),
                    body,
                    template_type,
                    used_ref_names,
                    ref_renames,
                )

            if any(overall_changes.values()):
                changed = ", ".join(k for k, v in overall_changes.items() if v)
                print(f"  -> {changed}")

        # Final pass: apply all ref renames globally (after loop to avoid
        # corrupting match.position offsets).
        # Handle double-quoted, single-quoted, and unquoted name patterns.
        for old_name, new_name in ref_renames.items():
            escaped = re.escape(old_name)
            text = re.sub(
                rf'<ref\s+name\s*=\s*"{escaped}"\s*(/?>|>)',
                lambda m: f'<ref name="{new_name}"{m.group(1)}',
                text,
            )
            text = re.sub(
                rf"<ref\s+name\s*=\s*'{escaped}'\s*(/?>|>)",
                lambda m: f'<ref name="{new_name}"{m.group(1)}',
                text,
            )
            text = re.sub(
                rf"<ref\s+name\s*=\s*{escaped}(\s*/?>|>)",
                lambda m: f'<ref name="{new_name}"{m.group(1)}',
                text,
            )

        output_path.write_text(text, encoding="utf-8")
        self._print_summary(stats)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _first_word(text: str) -> str | None:
        """Return the first non-stopword from *text*, stripping wikilinks."""
        for word in text.split():
            clean = word.strip("[]")
            if clean.lower() not in _STOPWORDS:
                return clean.capitalize()
        return None

    @staticmethod
    def _add_ref_name(
        text: str,
        pos: int,
        body: str,
        template_type: str,
        used_names: Set[str],
        renames: dict,
    ) -> str:
        """Generate a ref name from first author surname + year if missing.

        Populates *renames* with ``{old_name: new_name}`` for deferred
        global short-ref replacement.
        *used_names* tracks every name already assigned to prevent collisions.
        """
        # Find the <ref ...> tag preceding the citation
        prefix = text[:pos]
        ref_m = re.search(r"<ref\s*([^>]*)>\s*$", prefix)
        if not ref_m:
            return text
        attrs = ref_m.group(1)
        name_m = re.search(r'name\s*=\s*"([^"]*)"', attrs, re.IGNORECASE)
        existing_name = name_m.group(1) if name_m else None

        # Extract first author surname
        name = None
        m = re.search(r"\|\s*last\s*=\s*([^|]+)", body)
        if not m:
            m = re.search(r"\|\s*last1\s*=\s*([^|]+)", body)
        if not m:
            m = re.search(r"\|\s*vauthors\s*=\s*([^|,;]+)", body)
        if m:
            raw = m.group(1).strip().rstrip(",").strip()
            name = raw.split()[0]

        # Extract year
        year = None
        ym = re.search(r"\|\s*year\s*=\s*(\d{4})", body)
        if not ym:
            ym = re.search(r"\|\s*date\s*=\s*[^|]*?(\d{4})", body)
        if ym:
            year = ym.group(1)

        # Treat auto-generated names (:0, :1, ...) as unnamed
        if existing_name is not None and not existing_name.startswith(":"):
            if name and year and existing_name == name:
                pass  # upgrade bare-surname name to include year
            else:
                return text  # already has a meaningful name

        if name and year:
            ref_name = f"{name}{year}"
        elif name:
            ref_name = name
        elif template_type.lower().startswith("cite web"):
            # For web citations without author, try work/website/publisher
            ref_name = None
            for field in ("work", "website", "publisher"):
                fm = re.search(rf"\|\s*{field}\s*=\s*([^|]+)", body)
                if fm:
                    ref_name = CitationPipeline._first_word(fm.group(1).strip())
                    if ref_name:
                        break
            if not ref_name:
                # Fall back to domain from URL
                um = re.search(r"\|\s*url\s*=\s*([^|]+)", body)
                if um:
                    domain = urllib.parse.urlparse(um.group(1).strip()).netloc
                    domain = domain.removeprefix("www.").split(".")[0]
                    ref_name = domain.capitalize()
            if not ref_name:
                # Last resort: title
                tm = re.search(r"\|\s*title\s*=\s*([^|]+)", body)
                if tm:
                    ref_name = CitationPipeline._first_word(tm.group(1).strip())
            if not ref_name:
                return text
        else:
            # Fallback: first non-stopword from title
            tm = re.search(r"\|\s*title\s*=\s*([^|]+)", body)
            if tm:
                ref_name = CitationPipeline._first_word(tm.group(1).strip())
                if not ref_name:
                    return text
            else:
                return text

        # Wikipedia rejects ref names that are simple integers
        if ref_name.isdigit():
            ref_name = f"ref-{ref_name}"

        # Deduplicate against all existing ref names in the text
        if ref_name in used_names:
            suffix = 2
            while f"{ref_name}-{suffix}" in used_names:
                suffix += 1
            ref_name = f"{ref_name}-{suffix}"
        used_names.add(ref_name)

        # Insert name into the <ref> tag
        old_ref = ref_m.group(0)
        if existing_name:
            new_ref = old_ref.replace(f'name="{existing_name}"', f'name="{ref_name}"')
        else:
            new_ref = f'<ref name="{ref_name}">'
        text = text[: pos - len(old_ref)] + new_ref + text[pos:]

        # Record rename for deferred global short-ref replacement
        if existing_name and existing_name != ref_name:
            renames[existing_name] = ref_name

        return text

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
        print(
            f"Archive scope:    {'all types' if self.force_archive_all else 'cite web/news'}"
        )
        print(f"Create archive:   {self.create_archive}")
        print(f"Ref names:        {self.ref_names}")
        print()

    def _print_summary(self, stats: CitationStats):
        print("\n" + "=" * 80)
        print("ENHANCEMENT SUMMARY")
        print("=" * 80)
        print(f"Total citations processed: {stats.total}")
        for k, v in sorted(stats.module_stats.items()):
            print(f"  + {k}: {v}")
        print("=" * 80)
