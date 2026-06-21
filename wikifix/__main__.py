"""
CLI entry point for the wikifix universal citation pipeline.

Usage:
    python -m wikifix                         # default pipeline
    python -m wikifix --enrich                # ID enrichment + spacing only
    python -m wikifix --modules authors,dates,ids,spacing
    python -m wikifix --author-style vancouver
    python -m wikifix --ids issn,pmid,pmc,s2cid,qid
    python -m wikifix --force
    python -m wikifix --list-modules
    python -m wikifix --help
"""

import argparse
import sys
import traceback
from pathlib import Path

from wikifix import (
    ApiConfig,
    ArchiveModule,
    AuthorModule,
    CitationPipeline,
    CleanupModule,
    DateModule,
    DedupModule,
    ExpandModule,
    IdEnrichmentModule,
    Mode,
    SortModule,
    SpacingModule,
    __version__,
)
from wikifix.logger import get_logger, setup_logger
from wikifix.modules.sfn import convert_to_sfn as _convert_to_sfn
from wikifix.services import ApiClient

log = get_logger()

MODULE_REGISTRY = {
    "expand": ExpandModule,
    "authors": AuthorModule,
    "dates": DateModule,
    "ids": IdEnrichmentModule,
    "spacing": SpacingModule,
    "sort": SortModule,
    "dedup": DedupModule,
    "archive": ArchiveModule,
    "cleanup": CleanupModule,
}


def _add_pipeline_group(p: argparse.ArgumentParser) -> None:
    """Pipeline control arguments."""
    g = p.add_argument_group("Pipeline Control")
    g.add_argument(
        "--enrich",
        action="store_true",
        help="Full enrichment: sort + cleanup + dedup + refresh authors",
    )
    g.add_argument(
        "--sort",
        action="store_true",
        help="Reorder parameters to Wikipedia standard order (adds sort module)",
    )
    g.add_argument(
        "--cleanup",
        action="store_true",
        help="Fix CS1/CS2 maintenance issues (adds cleanup module)",
    )
    g.add_argument(
        "--dedup",
        action="store_true",
        help="Detect duplicate citations (adds dedup module)",
    )
    g.add_argument(
        "--sfn",
        action="store_true",
        help="Convert inline <ref>{{cite...}}</ref> to {{sfn}} short-footnotes",
    )
    g.add_argument(
        "--modules",
        "-m",
        default="expand,authors,dates,ids,spacing,archive",
        help="Comma-separated list of modules to run (default: all)",
    )
    g.add_argument(
        "--bare",
        action="store_true",
        help="Start with no default modules; add each explicitly",
    )
    g.add_argument(
        "--list-modules",
        action="store_true",
        help="List available modules and exit",
    )
    for name in MODULE_REGISTRY:
        g.add_argument(
            f"--no-{name}",
            action="store_true",
            dest=f"no_{name.replace('-', '_')}",
            help=f"Exclude {name} module from the pipeline",
        )


def _add_author_group(p: argparse.ArgumentParser) -> None:
    """Author and style arguments."""
    g = p.add_argument_group("Author & Style")
    g.add_argument(
        "--author-style",
        choices=["normal", "vancouver"],
        default="normal",
        help='Author output style: "normal" (last/first) or "vancouver" (vauthors)',
    )
    g.add_argument(
        "--refresh-authors",
        action="store_true",
        help="Fetch full author names from CrossRef/PubMed (requires DOI)",
    )
    g.add_argument(
        "--max-authors",
        type=int,
        default=6,
        help="Maximum authors (0 = unlimited, default: 6)",
    )
    g.add_argument(
        "--spacing-style",
        choices=["standard", "compact", "wide"],
        default="standard",
        help="Spacing format: 'standard' (| param = value) or 'compact' (|param=value)",
    )


def _add_id_group(p: argparse.ArgumentParser) -> None:
    """ID enrichment arguments."""
    g = p.add_argument_group("ID Enrichment")
    g.add_argument(
        "--ids",
        default="issn,pmid,pmc,s2cid,qid",
        help="Comma-separated IDs to fetch (default: issn,pmid,pmc,s2cid,qid)",
    )
    g.add_argument(
        "--strip-issn",
        action="store_true",
        help="Remove ISSN when DOI is present (redundant identifier)",
    )


def _add_archive_group(p: argparse.ArgumentParser) -> None:
    """Archive arguments."""
    g = p.add_argument_group("Archive")
    g.add_argument(
        "--force-archive",
        action="store_true",
        help="Archive all citation types (not just cite web/news)",
    )
    g.add_argument(
        "--create-archive",
        action="store_true",
        help="Submit unarchived URLs to Wayback Machine to create new snapshots",
    )


def _add_mode_group(p: argparse.ArgumentParser) -> None:
    """Mode and behavior arguments."""
    g = p.add_argument_group("Mode")
    g.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force-refresh: re-fetch metadata and all identifiers",
    )
    g.add_argument(
        "--ref-names",
        action="store_true",
        help="Auto-generate ref names from first author surname + year",
    )


def _add_io_group(p: argparse.ArgumentParser) -> None:
    """I/O arguments."""
    g = p.add_argument_group("Input / Output")
    g.add_argument(
        "--input",
        "-i",
        default="from.txt",
        help="Input wikitext file (default: from.txt)",
    )
    g.add_argument(
        "--output",
        "-o",
        default="to.txt",
        help="Output file (default: to.txt)",
    )
    g.add_argument(
        "--diff",
        action="store_true",
        help="Print a unified diff of all changes made to the input",
    )


def _add_cache_group(p: argparse.ArgumentParser) -> None:
    """Caching arguments."""
    g = p.add_argument_group("Caching")
    g.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for API response cache",
    )
    g.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable API response caching",
    )
    g.add_argument(
        "--clear-cache",
        action="store_true",
        help="Wipe the API response disk cache and exit",
    )


def _add_misc_group(p: argparse.ArgumentParser) -> None:
    """Miscellaneous arguments."""
    g = p.add_argument_group("Miscellaneous")
    g.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging output",
    )
    g.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all logging output except errors",
    )
    g.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="Number of parallel workers for citation processing (default: 4)",
    )
    g.add_argument(
        "--env",
        "-e",
        default=None,
        help="Path to .env file with API keys for higher rate limits",
    )
    g.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )


def build_argparser() -> argparse.ArgumentParser:
    """Build and populate the CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="python -m wikifix",
        description="Universal Wikipedia Citation Fixer - modular pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m wikifix                         # default pipeline\n"
            "  python -m wikifix --enrich                # sort + cleanup + dedup\n"
            "  python -m wikifix --dedup                 # detect duplicate citations\n"
            "  python -m wikifix --modules spacing       # whitespace only\n"
            "  python -m wikifix --modules authors,sort  # convert + sort authors\n"
            "  python -m wikifix --force --ids issn,pmid\n"
            "  python -m wikifix --force-archive         # archive all template types\n"
            "  python -m wikifix --ref-names             # auto-name unnamed refs\n"
            "  python -m wikifix --no-spacing            # exclude spacing\n"
            "  python -m wikifix --list-modules\n"
        ),
    )
    _add_pipeline_group(p)
    _add_author_group(p)
    _add_id_group(p)
    _add_archive_group(p)
    _add_mode_group(p)
    _add_io_group(p)
    _add_cache_group(p)
    _add_misc_group(p)
    return p


def main() -> None:
    """Entry point: parse CLI args and run the citation pipeline."""
    parser = build_argparser()
    args = parser.parse_args()

    setup_logger(verbose=args.verbose, quiet=args.quiet)

    # --version
    if args.version:
        print(f"WikiCitationFixer v{__version__}")
        sys.exit(0)

    # --list-modules
    if args.list_modules:
        log.info("Available modules:")
        for name, cls in MODULE_REGISTRY.items():
            log.info("  %-12s  %s", name, cls.description)
        sys.exit(0)

    # --clear-cache (bootstrap a minimal ApiClient just to clear)
    if args.clear_cache:
        api_config = ApiConfig.from_env(args.env)
        client = ApiClient(api_config)
        client.clear_cache()
        sys.exit(0)

    # Resolve modules
    extra = []
    if args.bare:
        args.modules = ""  # clear defaults, start from empty
    if args.sort:
        extra.append("sort")
    if args.dedup:
        extra.append("dedup")
    if args.cleanup:
        extra.append("cleanup")
    if args.enrich:
        module_source = f"{args.modules},cleanup,dedup"
        args.refresh_authors = True
        args.ref_names = True
    elif extra:
        module_source = f"{args.modules},{','.join(extra)}"
    else:
        module_source = args.modules
    module_names = [m.strip() for m in module_source.split(",") if m.strip()]
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for n in module_names:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    module_names = deduped

    # Apply --no-MODULE exclusions
    for name in MODULE_REGISTRY:
        attr = f"no_{name.replace('-', '_')}"
        if getattr(args, attr, False):
            module_names = [n for n in module_names if n != name]

    unknown = set(module_names) - set(MODULE_REGISTRY)
    if unknown:
        log.error("ERROR: Unknown module(s): %s", ", ".join(sorted(unknown)))
        log.error("Available: %s", ", ".join(sorted(MODULE_REGISTRY)))
        sys.exit(1)

    modules = [MODULE_REGISTRY[n]() for n in module_names]
    mode = Mode.FORCE_REFRESH if args.force else Mode.INCREMENTAL
    ids_to_fetch = [i.strip() for i in args.ids.split(",") if i.strip()]
    if args.enrich:
        ids_to_fetch = [i for i in ids_to_fetch if i != "issn"]

    overrides = {}
    if args.no_cache:
        overrides["cache_dir"] = ""  # empty string = cache disabled
    elif args.cache_dir:
        overrides["cache_dir"] = args.cache_dir
    if args.workers is not None:
        overrides["max_workers"] = args.workers
    api_config = ApiConfig.from_env(args.env, **overrides)

    pipeline = CitationPipeline(
        modules=modules,
        mode=mode,
        api_config=api_config,
        author_style=args.author_style,
        refresh_authors=args.refresh_authors,
        max_authors=args.max_authors,
        ids_to_fetch=ids_to_fetch,
        force_archive_all=args.force_archive,
        create_archive=args.create_archive,
        ref_names=args.ref_names,
        strip_issn=args.strip_issn,
        spacing_style=args.spacing_style,
        diff=args.diff,
    )

    infile = Path(args.input)
    outfile = Path(args.output)

    if not infile.exists():
        log.error("ERROR: Input file not found: %s", infile)
        sys.exit(1)

    max_size = 500 * 1024 * 1024  # 500 MB
    if infile.stat().st_size > max_size:
        log.error(
            "ERROR: Input file too large (%.1f MB > %d MB limit)",
            infile.stat().st_size / (1024 * 1024),
            max_size // (1024 * 1024),
        )
        sys.exit(1)

    try:
        outfile.parent.mkdir(parents=True, exist_ok=True)
        outfile.touch(exist_ok=True)
    except OSError as e:
        log.error("ERROR: Cannot write to output path %s: %s", outfile, e)
        sys.exit(1)

    try:
        pipeline.process_file(infile, outfile)
        if args.sfn:
            log.info("")
            log.info("Converting inline citations to {{sfn}}...")
            text = outfile.read_text(encoding="utf-8")
            text = _convert_to_sfn(text)
            outfile.write_text(text, encoding="utf-8")
        log.info("")
        log.info("+ Output saved to: %s", outfile)
        if args.diff:
            _show_diff(infile, outfile)
    except FileNotFoundError:
        log.error("ERROR: Could not read %s during processing", infile)
        sys.exit(1)
    except Exception as e:
        log.error("ERROR: %s", e)
        traceback.print_exc()
        sys.exit(1)


def _show_diff(original: Path, modified: Path) -> None:
    """Print a unified diff between original and modified files."""
    import difflib

    try:
        orig_lines = original.read_text(encoding="utf-8").splitlines(keepends=True)
        mod_lines = modified.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as e:
        log.warning("  Cannot compute diff: %s", e)
        return

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=str(original),
        tofile=str(modified),
        lineterm="",
    )
    diff_text = "".join(diff)
    if diff_text.strip():
        print(diff_text)
    else:
        log.info("  No differences found.")


if __name__ == "__main__":
    main()
