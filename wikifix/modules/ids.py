"""
ID enrichment module.

Fetches and adds missing identifiers using external APIs:
    - ISSN via CrossRef
    - PMID via NCBI E-utilities
    - PMC via NCBI PMC ID Converter
    - S2CID via Semantic Scholar

All lookups are gated on an existing DOI.
The set of IDs to attempt is controlled by the ``ids_to_fetch``
context key (default: issn, pmid, pmc, s2cid).
"""

import re
from typing import Set

from wikifix.base import CitationModule
from wikifix.config import Mode, ProcessingResult
from wikifix.logger import get_logger; log = get_logger()


class IdEnrichmentModule(CitationModule):
    """Enrich citations with PMID, PMC, ISSN, S2CID via DOI."""

    name = "ids"
    description = "Enrich citations with PMID, PMC, ISSN, S2CID via DOI"

    def process(self, text: str, context: dict) -> ProcessingResult:
        """Fetch and add missing identifiers (ISSN, PMID, PMC, S2CID) using existing DOI."""
        changes = {k: False for k in ("issn", "pmid", "pmc", "s2cid", "doi-access")}
        api = context.get("api")
        mode: Mode = context.get("mode", Mode.INCREMENTAL)
        wanted: Set[str] = set(
            context.get("ids_to_fetch", ["issn", "pmid", "pmc", "s2cid"])
        )

        if not api:
            return ProcessingResult(text=text, changes=changes)

        # DOI
        doi_m = re.search(r"\|\s*doi\s*=\s*([^\|}]+)", text)
        if not doi_m:
            return ProcessingResult(text=text, changes=changes)
        doi = doi_m.group(1).strip()

        # --- doi-access=free (OA indicator) ---
        # Only for cite journal / citation (cite book/encyclopedia/web don't support it)
        template_type = context.get("template_type", "")
        t = template_type.lower()
        can_use_doi_access = t in ("citation",) or t.startswith("cite journal")
        has_doi_access = bool(re.search(r"\|\s*doi-access\s*=", text))
        if can_use_doi_access and not has_doi_access and api.doi_is_oa(doi):
            text += " |doi-access=free"
            changes["doi-access"] = True
            log.info("    + Added doi-access=free (OA)")

        if "issn" in wanted:
            # Only add ISSN for journal-type templates (cite journal, citation)
            # to avoid linking book/website ISSNs that CrossRef may return
            # for non-journal containers (e.g. book series, reference works).
            template_type = context.get("template_type", "")
            t = template_type.lower()
            can_use_issn = t in ("citation",) or t.startswith("cite journal")
            if not can_use_issn:
                changes.pop("issn", None)
            else:
                has = bool(re.search(r"\|\s*issn\s*=", text))
                if mode == Mode.FORCE_REFRESH and has:
                    text = re.sub(r"\|\s*issn\s*=[^\|}]+", "", text)
                    has = False
                if not has:
                    issn = api.doi_to_issn(doi)
                    if issn:
                        text += f" |issn={issn}"
                        changes["issn"] = True
                        action = "Updated" if mode == Mode.FORCE_REFRESH else "Added"
                        log.info("    + %s ISSN %s", action, issn)

        # --- PMID ---
        pmid = None
        if "pmid" in wanted:
            has = bool(re.search(r"\|\s*pmid\s*=", text))
            if mode == Mode.FORCE_REFRESH and has:
                text = re.sub(r"\|\s*pmid\s*=[^\|}]+", "", text)
                has = False
            if not has:
                pmid = api.doi_to_pmid(doi)
                if pmid:
                    text += f" |pmid={pmid}"
                    changes["pmid"] = True
                    action = "Updated" if mode == Mode.FORCE_REFRESH else "Added"
                    log.info("    + %s PMID %s", action, pmid)
            else:
                m = re.search(r"\|\s*pmid\s*=\s*(\d+)", text)
                if m:
                    pmid = m.group(1)

        # --- PMC (requires PMID) ---
        if "pmc" in wanted and pmid:
            has_pmc = bool(re.search(r"\|\s*pmc\s*=", text))
            if mode == Mode.FORCE_REFRESH and has_pmc:
                text = re.sub(r"\|\s*pmc\s*=[^\|}]+", "", text)
                has_pmc = False
            if not has_pmc:
                pmc = api.pmid_to_pmc(pmid)
                if pmc:
                    text += f" |pmc={pmc}"
                    changes["pmc"] = True
                    action = "Updated" if mode == Mode.FORCE_REFRESH else "Added"
                    log.info("    + %s PMC %s", action, pmc)

        # --- S2CID ---
        if "s2cid" in wanted:
            has = bool(re.search(r"\|\s*s2cid\s*=", text))
            if mode == Mode.FORCE_REFRESH and has:
                text = re.sub(r"\|\s*s2cid\s*=[^\|}]+", "", text)
                has = False
            if not has:
                s2cid = api.doi_to_s2cid(doi)
                if s2cid:
                    text += f" |s2cid={s2cid}"
                    changes["s2cid"] = True
                    action = "Updated" if mode == Mode.FORCE_REFRESH else "Added"
                    log.info("    + %s S2CID %s", action, s2cid)

        return ProcessingResult(text=text, changes=changes)
