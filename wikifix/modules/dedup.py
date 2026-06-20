"""
Duplicate citation detection module.

Uses the pre-computed ``is_duplicate`` flag from the pipeline context
to report citations that share a DOI or PMID with an earlier citation.
"""

from typing import Any

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult
from wikifix.logger import get_logger

log = get_logger()


class DedupModule(CitationModule):
    """Detect duplicate citations by DOI/PMID."""

    name = "dedup"
    description = "Detect duplicate citations by DOI/PMID"

    def process(self, text: str, context: dict[str, Any]) -> ProcessingResult:
        """Flag duplicate citations that share a DOI or PMID with an earlier entry."""
        is_dup = context.get("is_duplicate", False)
        if not is_dup:
            return ProcessingResult(text=text, changes={})

        doi = context.get("doi")
        pmid = context.get("pmid")
        title = context.get("title", "")
        key = doi or pmid or ""
        label = f"  ({key})" if key else ""
        log.info("    ** DUPLICATE%s: %s", label, title[:60])
        return ProcessingResult(text=text, changes={"dedup": True})
