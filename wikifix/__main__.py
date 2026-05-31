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
    parser = build_argparser()
    args = parser.parse_args()

    # --list-modules
    if args.list_modules:
        print("Available modules:")
        for name, cls in MODULE_REGISTRY.items():
            print(f"  {name:12s}  {cls.description}")
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

    # Apply --no-MODULE exclusions
    for name in MODULE_REGISTRY:
        attr = f"no_{name.replace('-', '_')}"
        if getattr(args, attr, False):
            module_names = [n for n in module_names if n != name]

    unknown = set(module_names) - set(MODULE_REGISTRY)
    if unknown:
        print(f"ERROR: Unknown module(s): {', '.join(sorted(unknown))}")
        print(f"Available: {', '.join(sorted(MODULE_REGISTRY))}")
        sys.exit(1)

    modules = [MODULE_REGISTRY[n]() for n in module_names]
    mode = Mode.FORCE_REFRESH if args.force else Mode.INCREMENTAL
    ids_to_fetch = [i.strip() for i in args.ids.split(",") if i.strip()]

    pipeline = CitationPipeline(
        modules=modules,
        mode=mode,
        author_style=args.author_style,
        refresh_authors=args.refresh_authors,
        max_authors=args.max_authors,
        ids_to_fetch=ids_to_fetch,
        force_archive_all=args.force_archive,
        create_archive=args.create_archive,
        ref_names=args.ref_names,
    )

    infile = Path(args.input)
    outfile = Path(args.output)

    try:
        pipeline.process_file(infile, outfile)
        print(f"\n+ Output saved to: {outfile}")
    except FileNotFoundError:
        print(f"ERROR: Could not find {infile}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
