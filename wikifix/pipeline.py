"""
Pipeline orchestrator.

Chains multiple CitationModules together and runs them over every
citation template found in a Wikipedia wikitext source file.
"""

from __future__ import annotations

import re
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wikifix.base import CitationModule
from wikifix.config import ApiConfig, CitationStats, Mode
from wikifix.logger import get_logger
from wikifix.services import ApiClient

log = get_logger()


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


@dataclass
class _ProcessResult:
    """Intermediate result from processing a single citation match."""

    body: str
    template_type: str
    changes: dict[str, bool]
    renames: dict[str, str]
    drops: set[str]
    idx: int
    title: str
    ref_name: str | None = None


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
        modules: list[CitationModule],
        mode: Mode = Mode.INCREMENTAL,
        api_config: ApiConfig = ApiConfig(),
        author_style: str = "normal",
        refresh_authors: bool = False,
        max_authors: int = 6,
        ids_to_fetch: list[str] | None = None,
        force_archive_all: bool = False,
        create_archive: bool = False,
        ref_names: bool = False,
        strip_issn: bool = False,
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
            strip_issn:
                Remove ISSN when DOI is present.
        """
        self.modules = modules
        self.mode = mode
        self.api = ApiClient(api_config, mode)
        self.author_style = author_style
        self.refresh_authors = refresh_authors
        self.max_authors = max_authors
        self.ids_to_fetch = ids_to_fetch or ["issn", "pmid", "pmc", "s2cid"]
        self.force_archive_all = force_archive_all
        self.create_archive = create_archive
        self.ref_names = ref_names
        self.strip_issn = strip_issn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_file(self, input_path: Path, output_path: Path):
        """Read wikitext, process all citations, write result."""
        self._print_header()

        text = input_path.read_text(encoding="utf-8")
        matches = list(self.CITATION_RE.finditer(text))
        log.info("Found %d citation templates", len(matches))

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
        ref_renames: dict[str, str] = {}
        used_ref_names: set[str] = set(
            m.group(1) for m in re.finditer(r'<ref\s+name\s*=\s*"([^"]*)"', text)
        )

        # Parallel processing
        sorted_matches = list(enumerate(reversed(matches)))
        results: list[_ProcessResult | None] = [None] * len(matches)
        stats_lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=self.api.config.max_workers) as pool:
            fut_map: dict[Any, dict[str, Any]] = {}
            for sorted_idx, match in sorted_matches:
                title = self._extract_title(match.group(1))
                log.info("  Queuing [%d/%d] %s...", sorted_idx + 1, len(matches), title)
                fut = pool.submit(self._process_one, match, first_seen)
                fut_map[fut] = {"idx": sorted_idx, "title": title}

            for future in as_completed(fut_map):
                info = fut_map[future]
                sorted_idx = info["idx"]
                title = info["title"]
                try:
                    result = future.result(timeout=120)
                except TimeoutError:
                    log.warning(
                        "  Citation timed out [%d/%d] %s",
                        sorted_idx + 1,
                        len(matches),
                        title,
                    )
                    result = None
                except Exception as exc:
                    log.warning(
                        "  Citation failed [%d/%d] %s: %s",
                        sorted_idx + 1,
                        len(matches),
                        title,
                        exc,
                    )
                    result = None
                results[sorted_idx] = result
                if result is None:
                    log.warning(
                        "  No result for [%d/%d] %s",
                        sorted_idx + 1,
                        len(matches),
                        title,
                    )
                    continue
                # Accumulate stats under lock
                with stats_lock:
                    for k, v in result.changes.items():
                        stats.module_stats[k] = stats.module_stats.get(k, 0) + (
                            1 if v else 0
                        )

        # Sequential patch-back (reverse order preserves offsets)
        for sorted_idx, match in sorted_matches:
            result = results[sorted_idx]
            if result is None:
                continue
            body = result.body
            # Apply deferred param renames and drops
            if result.renames:
                body = self._apply_renames(body, result.renames)
            if result.drops:
                body = self._apply_drops(body, result.drops)
            # Strip ISSN when DOI present
            if self.strip_issn and re.search(r"\|\s*doi\s*=", body):
                body = re.sub(r"\|\s*issn\s*=[^\|}]+", "", body)
            # Patch back into source
            text = (
                text[: match.start()]
                + "{{"
                + self._canonical_type(result.template_type)
                + body
                + "}}"
                + text[match.end() :]
            )
            if any(result.changes.values()):
                changed = ", ".join(k for k, v in result.changes.items() if v)
                log.info("  -> %s", changed)

        # Ref names added sequentially (uses shared used_ref_names)
        if self.ref_names:
            for sorted_idx, match in sorted_matches:
                result = results[sorted_idx]
                if result is None:
                    continue
                text = self._add_ref_name(
                    text,
                    match.start(),
                    result.body,
                    result.template_type,
                    used_ref_names,
                    ref_renames,
                    existing=result.ref_name,
                )

        # Final pass: apply all ref renames globally
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

    def _process_one(self, match: re.Match, first_seen: dict) -> _ProcessResult | None:
        """Run all modules on a single citation match (thread-safe)."""
        try:
            body = match.group(1)
            template_type = self._detect_type(match.group(0))
            title = self._extract_title(body)
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
                "strip_issn": self.strip_issn,
            }
            overall_changes: dict[str, bool] = {}
            all_renames: dict[str, str] = {}
            all_drops: set[str] = set()
            for mod in self.modules:
                result = mod.process(body, context)
                body = result.text
                if result.new_template_type:
                    template_type = result.new_template_type
                if result.rename_params:
                    all_renames.update(result.rename_params)
                if result.drop_params:
                    all_drops.update(result.drop_params)
                overall_changes.update(result.changes)

            # Extract ref name from the original input text
            _orig_prefix = match.string[: match.start()]
            _ref_m = re.search(r"<ref\s*([^>]*)>\s*$", _orig_prefix)
            _ref_name = None
            if _ref_m:
                _nm = re.search(r'name\s*=\s*"([^"]*)"', _ref_m.group(1), re.IGNORECASE)
                _ref_name = _nm.group(1) if _nm else None

            log.info("[done] %s", title)
            return _ProcessResult(
                body=body,
                template_type=template_type,
                changes=overall_changes,
                renames=all_renames,
                drops=all_drops,
                idx=match.start(),
                title=title,
                ref_name=_ref_name,
            )
        except Exception as e:
            log.error("  ERROR processing citation: %s", e)
            return None

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
    def _apply_renames(body: str, renames: dict[str, str]) -> str:
        """Rename parameters in a citation body dict.

        Handles the case where both old and new names exist by using
        a three-way swap (old→interim, new→old, interim→new) so no
        data is lost.
        """
        for old, new in renames.items():
            if old == new:
                continue
            old_re = re.compile(rf"\|\s*{re.escape(old)}\s*=\s*([^|]*)")
            if not old_re.search(body):
                continue
            new_re = re.compile(rf"\|\s*{re.escape(new)}\s*=\s*([^|]*)")
            if new_re.search(body):
                interim = f"__{old}_to_{new}__"
                body = old_re.sub(lambda m: f"| {interim} = {m.group(1).strip()}", body)
                body = new_re.sub(lambda m: f"| {old} = {m.group(1).strip()}", body)
                body = re.compile(rf"\|\s*{re.escape(interim)}\s*=\s*([^|]*)").sub(
                    lambda m: f"| {new} = {m.group(1).strip()}", body
                )
            else:
                body = old_re.sub(lambda m: f"| {new} = {m.group(1).strip()}", body)
        return body

    @staticmethod
    def _apply_drops(body: str, drop: set[str]) -> str:
        """Remove parameters from a citation body."""
        for param in drop:
            body = re.sub(rf"\|\s*{re.escape(param)}\s*=\s*[^|]+", "", body)
        # Clean up double pipes from removal
        body = re.sub(r"\|\s*\|", "|", body)
        return body

    @staticmethod
    def _add_ref_name(
        text: str,
        pos: int,
        body: str,
        template_type: str,
        used_names: set[str],
        renames: dict,
        existing: str | None = None,
    ) -> str:
        """Generate a ref name from first author surname + year if missing.

        Populates *renames* with ``{old_name: new_name}`` for deferred
        global short-ref replacement.
        *used_names* tracks every name already assigned to prevent collisions.
        *existing* is the current ref name (or None to auto-detect from text).
        """
        # Determine the ref tag content and existing name
        ref_tag = f'<ref name="{existing}">' if existing else None
        if ref_tag is None:
            prefix = text[:pos]
            ref_m = re.search(r"<ref\s*([^>]*)>\s*$", prefix)
            if not ref_m:
                return text
            attrs = ref_m.group(1).strip()
            name_m = re.search(r'name\s*=\s*"([^"]*)"', attrs, re.IGNORECASE)
            existing = name_m.group(1) if name_m else None
            ref_tag = ref_m.group(0)
        existing_name = existing

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

        if ref_name is None:
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
        if existing_name:
            text = text.replace(f'name="{existing_name}"', f'name="{ref_name}"', 1)
        else:
            text = text[: pos - len(ref_tag)] + f'<ref name="{ref_name}">' + text[pos:]

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
        """Extract the |title= value for display in progress output."""
        m = re.search(r"\|\s*title\s*=\s*([^\|]+)", body)
        return m.group(1).strip()[:60] if m else "(no title)"

    @staticmethod
    def _extract_doi(body: str) -> str | None:
        """Extract the |doi= value from a citation body."""
        m = re.search(r"\|\s*doi\s*=\s*([^\|}]+)", body)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_pmid(body: str) -> str | None:
        """Extract the |pmid= value from a citation body."""
        m = re.search(r"\|\s*pmid\s*=\s*(\d+)", body)
        return m.group(1).strip() if m else None

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def _print_header(self):
        """Print a banner with pipeline configuration before processing."""
        mode_label = self.mode.name.replace("_", " ")
        log.info("=" * 80)
        log.info("WIKIFIX CITATION PIPELINE -- %s", mode_label)
        log.info("=" * 80)
        modules_str = ", ".join(m.name for m in self.modules)
        log.info("Active modules: %s", modules_str)
        log.info("Author style:     %s", self.author_style)
        ma = self.max_authors if self.max_authors > 0 else "unlimited"
        log.info("Max authors:      %s", ma)
        log.info("Refresh authors:  %s", self.refresh_authors)
        ids = ", ".join(self.ids_to_fetch)
        log.info("IDs to fetch:     %s", ids)
        log.info(
            "Archive scope:    %s",
            "all types" if self.force_archive_all else "cite web/news",
        )
        log.info("Create archive:   %s", self.create_archive)
        log.info("Ref names:        %s", self.ref_names)
        log.info("Strip ISSN:       %s", self.strip_issn)
        log.info("")

    def _print_summary(self, stats: CitationStats):
        """Print per-module change counts after processing all citations."""
        log.info("")
        log.info("=" * 80)
        log.info("ENHANCEMENT SUMMARY")
        log.info("=" * 80)
        log.info("Total citations processed: %d", stats.total)
        for k, v in sorted(stats.module_stats.items()):
            log.info("  + %s: %d", k, v)
        log.info("=" * 80)
