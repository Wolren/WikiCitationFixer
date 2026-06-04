"""
CLI entry point for the wikifix universal citation pipeline.

Usage:
    python -m wikifix                         # default pipeline
    python -m wikifix --enrich                # ID enrichment + spacing only
    python -m wikifix --modules authors,dates,ids,spacing
    python -m wikifix --author-style vancouver
    python -m wikifix --ids issn,pmid,pmc,s2cid
    python -m wikifix --force
    python -m wikifix --list-modules
    python -m wikifix --help
"""

import sys
import argparse
from pathlib import Path

from wikifix import (
    CitationPipeline,
    Mode,
    ApiConfig,
    AuthorModule,
    DateModule,
    IdEnrichmentModule,
    SpacingModule,
    SortModule,
    DedupModule,
    CleanupModule,
    ExpandModule,
    ArchiveModule,
)
from wikifix.logger import get_logger, setup_logger

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


def build_argparser() -> argparse.ArgumentParser:
    """Build and populate the CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="python -m wikifix",
        description="Universal Wikipedia Citation Fixer - modular pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m wikifix                         # default: expand + format + archive\n"
            "  python -m wikifix --enrich                # sort + cleanup + dedup + refresh authors\n"
            "  python -m wikifix --dedup                 # detect duplicate citations\n"
            "  python -m wikifix --modules spacing       # whitespace only\n"
            "  python -m wikifix --modules authors,sort  # convert + sort authors\n"
            "  python -m wikifix --force --ids issn,pmid\n"
            "  python -m wikifix --force-archive         # archive all template types\n"
            "  python -m wikifix --ref-names             # auto-name unnamed refs\n"
            "  python -m wikifix --no-spacing            # exclude spacing from defaults\n"
            "  python -m wikifix --list-modules\n"
        ),
    )
    p.add_argument(
        "--enrich",
        action="store_true",
        help="Full enrichment: sort + cleanup + dedup + refresh authors",
    )
    p.add_argument(
        "--sort",
        action="store_true",
        help="Reorder parameters to Wikipedia standard order (adds sort module)",
    )
    p.add_argument(
        "--cleanup",
        action="store_true",
        help="Fix CS1/CS2 maintenance issues (adds cleanup module)",
    )
    p.add_argument(
        "--dedup",
        action="store_true",
        help="Detect duplicate citations (adds dedup module)",
    )
    p.add_argument(
        "--modules",
        "-m",
        default="expand,authors,dates,ids,spacing,archive",
        help="Comma-separated list of modules to run (default: all)",
    )
    p.add_argument(
        "--author-style",
        choices=["normal", "vancouver"],
        default="normal",
        help='Author output style: "normal" (last/first) or "vancouver" (vauthors)',
    )
    p.add_argument(
        "--ids",
        default="issn,pmid,pmc,s2cid",
        help="Comma-separated IDs to fetch (default: issn,pmid,pmc,s2cid)",
    )
    p.add_argument(
        "--refresh-authors",
        action="store_true",
        help="Fetch full author names from CrossRef/PubMed (requires DOI)",
    )
    p.add_argument(
        "--strip-issn",
        action="store_true",
        help="Remove ISSN when DOI is present (redundant identifier)",
    )
    p.add_argument(
        "--max-authors",
        type=int,
        default=6,
        help="Maximum authors to output (0 = unlimited, default: 6, Wikipedia convention)",
    )
    p.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force-refresh: re-fetch metadata and all identifiers",
    )
    p.add_argument(
        "--force-archive",
        action="store_true",
        help="Archive all citation types (not just cite web/news)",
    )
    p.add_argument(
        "--create-archive",
        action="store_true",
        help="Submit unarchived URLs to Wayback Machine to create new snapshots",
    )
    p.add_argument(
        "--input",
        "-i",
        default="from.txt",
        help="Input wikitext file (default: from.txt)",
    )
    p.add_argument(
        "--output",
        "-o",
        default="to.txt",
        help="Output file (default: to.txt)",
    )
    p.add_argument(
        "--list-modules",
        action="store_true",
        help="List available modules and exit",
    )
    p.add_argument(
        "--ref-names",
        action="store_true",
        help="Auto-generate ref names from first author surname + year",
    )
    p.add_argument(
        "--bare",
        action="store_true",
        help="Start with no default modules; explicitly add each with --modules, --sort, etc.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging output",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all logging output except errors",
    )
    p.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for API response cache",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable API response caching",
    )
    p.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="Number of parallel workers for citation processing (default: 4)",
    )
    p.add_argument(
        "--env",
        "-e",
        default=None,
        help="Path to .env file with API keys for higher rate limits (NCBI_API_KEY, SEMANTIC_SCHOLAR_API_KEY, CROSSREF_EMAIL)",
    )
    # Dynamic --no-MODULE flags for all registered modules
    for name in MODULE_REGISTRY:
        p.add_argument(
            f"--no-{name}",
            action="store_true",
            dest=f"no_{name.replace('-', '_')}",
            help=f"Exclude {name} module from the pipeline",
        )
    return p


def main():
    """Entry point: parse CLI args and run the citation pipeline."""
    parser = build_argparser()
    args = parser.parse_args()

    setup_logger(verbose=args.verbose, quiet=args.quiet)

    # --list-modules
    if args.list_modules:
        log.info("Available modules:")
        for name, cls in MODULE_REGISTRY.items():
            log.info("  %-12s  %s", name, cls.description)
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
    seen = set()
    module_names = [n for n in module_names if n not in seen and not seen.add(n)]

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

    cache_dir = None if args.no_cache else (args.cache_dir or ".wikifix_cache")
    overrides = {"cache_dir": cache_dir}
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
    )

    infile = Path(args.input)
    outfile = Path(args.output)

    try:
        pipeline.process_file(infile, outfile)
        log.info("")
        log.info("+ Output saved to: %s", outfile)
    except FileNotFoundError:
        log.error("ERROR: Could not find %s", infile)
        sys.exit(1)
    except Exception as e:
        log.error("ERROR: %s", e)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
