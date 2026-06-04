# WikiCitationFixer

Modular Wikipedia citation fixer for CS1/CS2 templates (cite journal, cite web, cite book, citation, etc.).

## Quick start

```bash
pip install -r requirements.txt
python -m wikifix -i from.txt -o to.txt
```

Default modules and their purpose:

| Module | Runs by default | What it does |
|--------|:---------:|------|
| expand | yes | Fills missing title, journal, volume, issue, pages, date, publisher from DOI (CrossRef, Europe PMC), arXiv ID, or ISBN (Open Library). |
| authors | yes | Converts between vauthors (Vancouver) and last=/first= (normal) format. Direction: `--author-style normal` or `--author-style vancouver`. |
| dates | yes | Normalizes dates to Wikipedia Month/Year or Day Month/Year format. |
| ids | yes | Adds PMID, PMC, ISSN, S2CID from DOI via CrossRef, NCBI, Semantic Scholar. |
| spacing | yes | Normalizes pipe and equals spacing (`|param = value`). |
| archive | yes | Adds archive-url and archive-date via Wayback Machine (--force-archive extends to all types; --create-archive submits new URLs). Probes URL liveness; detects deprecated archive services (WebCite, Wikiwix). |
| sort | no | Reorders parameters to Wikipedia standard order. |
| cleanup | no | Fixes CS1/CS2 maintenance issues: work/journal dedup, year/date conflict, missing/placeholder titles, location w/o publisher, periodical conflicts, work+ISBN, page/pages conflict, deprecated params (month, coauthors), extra text in vol/issue/page, invalid url-status, orphaned access-date/doi-broken-date, empty values, param typos, external links in values, nbsp in values, None values, ISBN validation. |
| dedup | no | Warns when two citations share the same DOI or PMID. |
| ref-names | no (yes with --enrich) | Auto-generates ref names from first author surname + year for unnamed or :0/:1 refs. |

Select modules explicitly with `--modules`:

```bash
python -m wikifix --modules authors,sort
python -m wikifix --modules expand,dates,spacing
python -m wikifix --modules spacing
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-m, --modules` | expand,authors,dates,ids,spacing,archive | Comma-separated module list |
| `--sort` | off | Reorders parameters to Wikipedia standard order |
| `--cleanup` | off | Fixes CS1/CS2 maintenance issues (work/journal, year/date) |
| `--enrich` | off | Full enrichment: adds cleanup, dedup + enables refresh-authors and ref-names |
| `--dedup` | off | Adds the dedup module |
| `--author-style` | normal | `normal` (vauthors to last/first) or `vancouver` (last/first to vauthors) |
| `--refresh-authors` | off | Fetch full given names from CrossRef, OpenAlex, DataCite, PubMed (requires DOI) |
| `--max-authors` | 6 | Maximum authors before truncating with et al (0 = unlimited) |
| `--ids` | issn,pmid,pmc,s2cid | Which identifiers to fetch |
| `-f, --force` | off | Re-fetch all identifiers even if present |
| `--force-archive` | off | Archive all citation types, not just cite web/news |
| `--create-archive` | off | Submit unarchived URLs to Wayback Machine to create new snapshots |
| `--ref-names` | off | Auto-generate ref names from first author surname + year |
| `--strip-issn` | off | Remove ISSN when DOI is present (redundant identifier) |
| `--bare` | off | Clear default modules; add each explicitly with --modules etc. |
| `--no-MODULE` | off | Exclude a module (e.g. --no-spacing, --no-cleanup) |
| `-i, --input` | from.txt | Input wikitext file |
| `-o, --output` | to.txt | Output file |

## Input and output

```bash
python -m wikifix -i article.txt -o article_fixed.txt
```

The input is a Wikipedia wikitext fragment with CS1 or CS2 templates. The output is the same text with citations modified in place.

## Author names

Default: vauthors initials are used as-is ("Smith JA" becomes last=Smith, first=JA).

With `--refresh-authors`, the tool queries CrossRef, OpenAlex, DataCite, and PubMed for full given names and picks the source with the longest names. Requires a DOI.

## Modes

**Incremental** (default): adds only missing fields. Existing identifiers are preserved.

**Force refresh** (`--force`): removes and re-fetches all identifiers. Use after updating a DOI or to refresh stale data.

## API sources

| Source | Used for | Auth required |
|--------|----------|:-------------:|
| CrossRef | DOI metadata, authors, ISSN | no |
| NCBI E-utilities | DOI to PMID, authors | no |
| NCBI PMC ID Converter | PMID to PMC | no |
| Europe PMC | DOI/PMID full metadata | no |
| OpenAlex | DOI to authors (full names) | no |
| DataCite | DOI to authors (full names) | no |
| Semantic Scholar | DOI to S2CID | no |
| arXiv API | arXiv ID to metadata | no |
| Open Library | ISBN to book metadata | no |
| Wayback Machine | URL to archive snapshot | no |

All API calls are rate-limited with configurable delays. No API keys required.

## Configuration

```python
from wikifix import CitationPipeline, ApiConfig

config = ApiConfig(
    user_agent="MyTool/1.0",
    api_delay=0.34,       # NCBI limit
    crossref_delay=0.05,  # CrossRef limit
)

pipeline = CitationPipeline(
    modules=[...],
    mode=incremental,
    api_config=config,
    author_style="normal",
    refresh_authors=False,
    max_authors=6,
    ids_to_fetch=["issn", "pmid", "pmc", "s2cid"],
)
```

## License

MIT
