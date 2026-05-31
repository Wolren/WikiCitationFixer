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


class IdEnrichmentModule(CitationModule):
    name = "ids"
    description = "Enrich citations with PMID, PMC, ISSN, S2CID via DOI"

    def process(self, text: str, context: dict) -> ProcessingResult:
        changes = {k: False for k in ("issn", "pmid", "pmc", "s2cid")}
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

        # --- ISSN ---
        if "issn" in wanted:
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
                    print(f"    + {action} ISSN {issn}")

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
                    print(f"    + {action} PMID {pmid}")
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
                    print(f"    + {action} PMC {pmc}")

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
                    print(f"    + {action} S2CID {s2cid}")

        return ProcessingResult(text=text, changes=changes)
