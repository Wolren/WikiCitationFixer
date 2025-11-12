#!/usr/bin/env python3

"""
WikiPharm Citation Fixer
=========================
A tool for WikiProject Pharmacology to automate citation formatting

Author: Wolren
Created for: WikiProject Pharmacology
License: MIT

Features:
- Authors to Vancouver format (max 2 initials, vauthors field)
- Date to Wikipedia format (Month Year)
- Add/fetch missing IDs: PMID, PMC, ISSN (NCBI, CrossRef APIs)
- Modes: incremental (default), force refresh (fetch all fields)

"""

import re
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Tuple, Dict

import requests

__version__ = "2.0.0"
__author__ = "Wolren"
__license__ = "MIT"


# === Configuration and Enums ===

@dataclass(frozen=True)
class ApiConfig:
    """Configuration for API rate limiting and identification."""
    user_agent: str = "WikiPharmCitationFixer/2.0"
    ncbi_tool: str = "WikiPharmCitationFixer"
    api_delay: float = 0.34  # NCBI: 3/s
    crossref_delay: float = 0.05  # CrossRef: 50/s


class Mode(Enum):
    """Operating modes for citation enhancement."""
    INCREMENTAL = auto()  # Only add missing fields
    FORCE_REFRESH = auto()  # Re-fetch all fields


@dataclass
class Stats:
    """Statistics for citation processing."""
    total: int = 0
    vauthors_converted: int = 0
    dates_fixed: int = 0
    issn_added: int = 0
    pmid_added: int = 0
    pmc_added: int = 0


# === Main Enhancer Class ===

class WikiPharmCitationFixer:
    """Main class for processing and enhancing Wikipedia citations."""

    months = {
        **{str(i).zfill(2): m for i, m in enumerate([
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"], 1)},
        **{str(i): m for i, m in enumerate([
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"], 1)}
    }

    def __init__(self, mode: Mode, config: ApiConfig = ApiConfig()):
        """Initialize the citation fixer.

        Args:
            mode: Operating mode (INCREMENTAL or FORCE_REFRESH)
            config: API configuration settings
        """
        self.mode = mode
        self.config = config
        self.last_api_call = 0.0
        self.citation_pattern = re.compile(
            r'{{Cite journal(.*?)}}(?!})',
            re.DOTALL | re.IGNORECASE
        )

    def _rate_limit(self, delay: float):
        """Enforce rate limiting for API calls."""
        elapsed = time.time() - self.last_api_call
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_api_call = time.time()

    def doi_to_issn(self, doi: str) -> Optional[str]:
        """Retrieve ISSN from DOI using CrossRef API."""
        self._rate_limit(self.config.crossref_delay)
        doi = re.sub(r'https?://(dx\.)?doi\.org/', '', doi.strip(), flags=re.IGNORECASE)
        url = f'https://api.crossref.org/works/{doi}'
        try:
            resp = requests.get(
                url,
                headers={'User-Agent': self.config.user_agent},
                timeout=10
            )
            if resp.ok:
                issns = resp.json().get('message', {}).get('ISSN', [])
                return issns[0] if issns else None
        except Exception as e:
            print(f"  ISSN fetch failed for DOI {doi}: {e}")
        return None

    def doi_to_pmid(self, doi: str) -> Optional[str]:
        """Convert DOI to PMID using NCBI E-utilities API."""
        self._rate_limit(self.config.api_delay)
        doi = re.sub(r'https?://(dx\.)?doi\.org/', '', doi.strip(), flags=re.IGNORECASE)
        params = {
            'db': 'pubmed',
            'term': f'{doi}[DOI]',
            'retmode': 'json',
        }
        try:
            resp = requests.get(
                'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
                params=params,
                timeout=10
            )
            if resp.ok:
                ids = resp.json().get('esearchresult', {}).get('idlist', [])
                return ids[0] if ids else None
        except Exception as e:
            print(f"  PMID fetch failed for DOI {doi}: {e}")
        return None

    def pmid_to_pmc(self, pmid: str) -> Optional[str]:
        """Convert PMID to PMC using NCBI PMC ID Converter API."""
        self._rate_limit(self.config.api_delay)
        params = {
            'ids': pmid,
            'format': 'json'
        }
        try:
            resp = requests.get(
                'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/',
                params=params,
                timeout=10
            )
            if resp.ok:
                pmc = resp.json().get('records', [{}])[0].get('pmcid', '')
                return pmc.removeprefix('PMC') if pmc else None
        except Exception as e:
            print(f"  PMC fetch failed for PMID {pmid}: {e}")
        return None

    def format_date(self, date: str) -> str:
        """Convert date to Wikipedia format (Month Year only)."""
        if not date:
            return date
        if any(m in date for m in self.months.values()):
            date = re.sub(r'\b\d{1,2}\s+([A-Z][a-z]+\s+\d{4})\b', r'\1', date)
            date = re.sub(r'\b([A-Z][a-z]+)\s+\d{1,2},?\s+(\d{4})\b', r'\1 \2', date)
            return date
        if match := re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date):
            year, month, _ = match.groups()
            month_name = self.months.get(month, '')
            return f"{month_name} {year}" if month_name else date
        if match := re.match(r'(\d{4})-(\d{1,2})$', date):
            year, month = match.groups()
            month_name = self.months.get(month, '')
            return f"{month_name} {year}" if month_name else date
        if re.fullmatch(r'\d{4}', date):
            return date
        return date

    def extract_author_pairs(self, ct: str) -> List[Tuple[str, str]]:
        """Extract (last_name, first_name) pairs from citation."""
        if '|vauthors=' in ct:
            return []
        authors = []
        for i in range(1, 13):
            last_key = 'last' if i == 1 else f'last{i}'
            first_key = 'first' if i == 1 else f'first{i}'
            lm = re.search(rf'\|{last_key}=([^\|}}]+)', ct)
            fm = re.search(rf'\|{first_key}=([^\|}}]+)', ct)
            if lm:
                authors.append((lm.group(1).strip(), fm.group(1).strip() if fm else ''))
        return authors

    @staticmethod
    def extract_initials(fname: str) -> str:
        """Extract initials from first name (max 2)."""
        if not fname:
            return ''
        return ''.join(
            part[0].upper()
            for part in re.split(r'[\s\-\.]+', fname.strip())
            if part
        )[:2]

    def format_authors(self, authors: List[Tuple[str, str]]) -> str:
        """Convert authors to Vancouver format."""
        formatted = [
            f"{ln} {self.extract_initials(fn)}" if self.extract_initials(fn) else ln
            for ln, fn in authors[:6]
        ]
        return ', '.join(formatted) + (', et al' if len(authors) > 6 else '')

    @staticmethod
    def format_citation_parameters(text: str) -> str:
        """Format parameters with spaces around = sign."""

        def repl(m):
            param = m.group(1).strip()
            value = m.group(2).strip()
            return f"|{param} = {value}"

        return re.sub(r'\|\s*([^=\|]+?)\s*=\s*([^\|]+?)(?=\s*\||$)', repl, text)

    @staticmethod
    def enforce_pipe_spacing(text: str) -> str:
        """Ensure space before every | parameter separator."""
        match = re.match(r'(\{\{cite journal)(.*?)(\}\})', text, re.IGNORECASE | re.DOTALL)
        if match:
            opening, body, closing = match.groups()
            body = re.sub(r'\s*\|\s*', ' | ', body)
            return f"{opening}{body}{closing}"
        return re.sub(r'\s*\|\s*', ' | ', text)

    def enhance_citation(self, text: str) -> Tuple[str, Dict[str, bool]]:
        """Enhance a single citation with all improvements."""
        changes = {k: False for k in ('vauthors', 'date', 'issn', 'pmid', 'pmc')}

        # Authors
        authors = self.extract_author_pairs(text)
        if authors:
            vl = self.format_authors(authors)
            for i in range(1, 13):
                text = re.sub(rf'\|last{"" if i == 1 else i}=[^\|}}]+', '', text)
                text = re.sub(rf'\|first{"" if i == 1 else i}=[^\|}}]+', '', text)
            text = re.sub(r'\|\s*\|', '|', text).strip()
            text = text.lstrip('|')
            text = f"|vauthors={vl} |{text}" if text else f"|vauthors={vl}"
            changes['vauthors'] = True

        # Date
        if (date_match := re.search(r'\|date=([^\|}}]+)', text)):
            old = date_match.group(1).strip()
            new = self.format_date(old)
            if new != old:
                text = text.replace(f"|date={old}", f"|date={new}")
                changes['date'] = True

        # DOI
        doi_match = re.search(r'\|doi=([^\|}}]+)', text)
        doi = doi_match.group(1).strip() if doi_match else None
        if not doi:
            return self.enforce_pipe_spacing(self.format_citation_parameters(text)), changes

        # ISSN
        has_issn = '|issn=' in text
        if self.mode == Mode.FORCE_REFRESH and has_issn:
            text = re.sub(r'\|issn=[^\|}}]+', '', text)
            has_issn = False
        if not has_issn and (issn := self.doi_to_issn(doi)):
            text += f" |issn={issn}"
            changes['issn'] = True
            action = 'Updated' if self.mode == Mode.FORCE_REFRESH else 'Added'
            print(f"    ✓ {action} ISSN {issn}")

        # PMID
        has_pmid = '|pmid=' in text
        if self.mode == Mode.FORCE_REFRESH and has_pmid:
            text = re.sub(r'\|pmid=[^\|}}]+', '', text)
            has_pmid = False
        if not has_pmid and (pmid := self.doi_to_pmid(doi)):
            text += f" |pmid={pmid}"
            changes['pmid'] = True
            action = 'Updated' if self.mode == Mode.FORCE_REFRESH else 'Added'
            print(f"    ✓ {action} PMID {pmid}")

            # PMC
            has_pmc = '|pmc=' in text
            if self.mode == Mode.FORCE_REFRESH and has_pmc:
                text = re.sub(r'\|pmc=[^\|}}]+', '', text)
                has_pmc = False
            if not has_pmc and (pmc := self.pmid_to_pmc(pmid)):
                text += f" |pmc={pmc}"
                changes['pmc'] = True
                action = 'Updated' if self.mode == Mode.FORCE_REFRESH else 'Added'
                print(f"    ✓ {action} PMC {pmc}")

        text = self.format_citation_parameters(text)
        text = self.enforce_pipe_spacing(text)
        return text, changes

    def process_file(self, input_path: Path, output_path: Path):
        """Process Wikipedia source file with all enhancements."""
        print("=" * 80)
        print(f"WIKIPHARM CITATION FIXER - {self.mode.name.replace('_', ' ')}")
        print("=" * 80)
        print(f"Reading: {input_path}")
        mode_msg = ("⚠ FORCE REFRESH: Will re-fetch all IDs for all citations with DOI"
                    if self.mode == Mode.FORCE_REFRESH
                    else "✓ INCREMENTAL: Adds missing IDs only")
        print(mode_msg)
        print()

        text = input_path.read_text(encoding="utf-8")
        matches = list(self.citation_pattern.finditer(text))
        print(f"Found {len(matches)} {{{{Cite journal}}}} templates\n")

        stats = Stats(total=len(matches))

        for idx, match in enumerate(reversed(matches), 1):
            citation = match.group(1)
            title_match = re.search(r'\|title=([^\|]+)', citation)
            display_title = title_match.group(1)[:50] if title_match else "No title"
            print(f"[{idx}/{len(matches)}] {display_title}...")

            state = {k: f"|{k}=" in citation for k in ('vauthors', 'issn', 'pmid', 'pmc')}
            has_doi = '|doi=' in citation

            # Skip logic
            if self.mode == Mode.INCREMENTAL:
                if all(state.values()):
                    print("  → Already complete")
                    continue
                elif not has_doi:
                    print("  → No DOI, skipping API lookups")
            elif not has_doi:
                print("  → No DOI, skipping API lookups")

            # Enhance
            enhanced, changed = self.enhance_citation(citation)
            stats.vauthors_converted += changed['vauthors']
            stats.dates_fixed += changed['date']
            stats.issn_added += changed['issn']
            stats.pmid_added += changed['pmid']
            stats.pmc_added += changed['pmc']

            text = text[:match.start()] + "{{cite journal" + enhanced + "}}" + text[match.end():]

            if any(changed.values()):
                changes_str = ', '.join(k for k, v in changed.items() if v)
                print(f"  → Enhanced: {changes_str}")

        output_path.write_text(text, encoding="utf-8")

        # Summary
        print("\n" + "=" * 80)
        print("ENHANCEMENT SUMMARY")
        print("=" * 80)
        print(f"Total citations processed: {stats.total}")
        print(f"  ✓ Vancouver format (vauthors, max 2 initials): {stats.vauthors_converted}")
        print(f"  ✓ Date formatting (Month Year only): {stats.dates_fixed}")
        action = 'updated' if self.mode == Mode.FORCE_REFRESH else 'added'
        print(f"  ✓ ISSN {action}: {stats.issn_added}")
        print(f"  ✓ PMID {action}: {stats.pmid_added}")
        print(f"  ✓ PMC {action}: {stats.pmc_added}")
        print(f"\n✓ Output saved to: {output_path}")
        print("=" * 80)


def main():
    """Main entry point for the citation fixer."""
    mode = (Mode.FORCE_REFRESH
            if len(sys.argv) > 1 and sys.argv[1].lower() in {'--force', '-f', 'force', 'refresh', 'all'}
            else Mode.INCREMENTAL)

    print("=" * 80)
    print("WIKIPHARM CITATION FIXER - MODE SELECTION")
    print("=" * 80)
    print(f"Selected: {mode.name.replace('_', ' ')}")
    print("  Will re-fetch all IDs" if mode == Mode.FORCE_REFRESH else "  Only add missing IDs")
    print("  Use '--force' or '-f' for full refresh.\n")

    fixer = WikiPharmCitationFixer(mode=mode)
    infile = Path("paste.txt")
    outfile = Path("paste_corrected.txt")

    try:
        fixer.process_file(infile, outfile)
        print("\n✓✓✓ SUCCESS! ✓✓✓")
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
