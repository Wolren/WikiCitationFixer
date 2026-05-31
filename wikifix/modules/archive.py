"""
Wayback Machine archive module.

For ``cite web`` templates, checks the Wayback Machine for an archived
snapshot of the URL and adds ``|archive-url=`` and ``|archive-date=``
parameters if missing.
"""

import re

from wikifix.base import CitationModule
from wikifix.config import Mode, ProcessingResult


_WEB_TYPES = {"cite web", "cite news"}


class ArchiveModule(CitationModule):
    name = "archive"
    description = "Add archive-url/archive-date from Wayback Machine"

    def process(self, text: str, context: dict) -> ProcessingResult:
        start = text
        template_type = context.get("template_type", "")
        if template_type not in _WEB_TYPES:
            return ProcessingResult(text=text, changes={"archive": False})

        api = context.get("api")
        if not api:
            return ProcessingResult(text=text, changes={"archive": False})

        mode: Mode = context.get("mode", Mode.INCREMENTAL)

        # Extract URL
        url_m = re.search(r"\|\s*url\s*=\s*([^\|}]+)", text)
        if not url_m:
            return ProcessingResult(text=text, changes={"archive": False})
        url = url_m.group(1).strip()

        # Skip if archive-url already exists
        if mode == Mode.INCREMENTAL and re.search(r"\|\s*archive-url\s*=", text):
            return ProcessingResult(text=text, changes={"archive": False})

        # Check Wayback Machine
        result = api.check_wayback(url)
        if not result:
            return ProcessingResult(text=text, changes={"archive": False})

        archive_url, archive_date = result

        # Remove existing archive params in force mode
        if mode == Mode.FORCE_REFRESH:
            text = re.sub(r"\|\s*archive-url\s*=[^\|}]+", "", text)
            text = re.sub(r"\|\s*archive-date\s*=[^\|}]+", "", text)
            text = re.sub(r"\|\s*url-status\s*=[^\|}]+", "", text)

        text = (
            text
            + f" |archive-url={archive_url} |archive-date={archive_date} |url-status=live"
        )
        print(f"    + Archived: {archive_date}")
        return ProcessingResult(text=text, changes={"archive": True})
