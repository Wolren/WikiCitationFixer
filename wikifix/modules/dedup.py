"""
Duplicate citation detection module.

Uses the pre-computed ``is_duplicate`` flag from the pipeline context
to report citations that share a DOI or PMID with an earlier citation.
"""

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult


class DedupModule(CitationModule):
    name = "dedup"
    description = "Detect duplicate citations by DOI/PMID"

    def process(self, text: str, context: dict) -> ProcessingResult:
        is_dup = context.get("is_duplicate", False)
        if not is_dup:
            return ProcessingResult(text=text, changes={})

        doi = context.get("doi")
        pmid = context.get("pmid")
        title = context.get("title", "")
        key = doi or pmid or ""
        label = f"  ({key})" if key else ""
        print(f"    ** DUPLICATE{label}: {title[:60]}")
        return ProcessingResult(text=text, changes={"dedup": True})
