"""
Wayback Machine archive module.

By default only archives ``cite web`` and ``cite news`` templates.
Pass ``force_archive_all=True`` in context (or ``--force-archive`` on CLI)
to archive any template type with a URL.

Also detects deprecated archive services (WebCite, Wikiwix, …) in
existing ``|archive-url=`` values and validates archive parameter
consistency.
"""

import re

from wikifix.base import CitationModule
from wikifix.config import Mode, ProcessingResult
from wikifix.logger import get_logger; log = get_logger()

_WEB_TYPES = {"cite web", "cite news"}

# Deprecated archive services that should be replaced with Wayback Machine
_DEPRECATED_ARCHIVES = re.compile(
    r"https?://(www\.)?"
    r"(webcitation\.org|"
    r"archive\.wikiwix\.com|"
    r"archive\.is|"
    r"archive\.today|"
    r"archive\.fo|"
    r"archivecaslytosk\.onion|"
    r"freezepage\.com|"
    r"cachedview\.nl|"
    r"web\.cite\.org)",
    re.IGNORECASE,
)


class ArchiveModule(CitationModule):
    """Add archive-url/archive-date from Wayback Machine."""

    name = "archive"
    description = "Add archive-url/archive-date from Wayback Machine"

    def process(self, text: str, context: dict) -> ProcessingResult:
        """Add or validate archive-url/archive-date from Wayback Machine."""
        start = text
        template_type = context.get("template_type", "")
        api = context.get("api")
        mode: Mode = context.get("mode", Mode.INCREMENTAL)
        force_all = context.get("force_archive_all", False)
        create_archive = context.get("create_archive", False)
        changes = {}

        # --- Validate existing archive parameters ---
        url_val = self._get_field(text, "url")
        archive_url_val = self._get_field(text, "archive-url")
        archive_date_val = self._get_field(text, "archive-date")
        status_val = self._get_field(text, "url-status")

        # archive-url requires url
        if archive_url_val is not None and url_val is None:
            text = self._remove_field(text, "archive-url")
            text = self._remove_field(text, "archive-date")
            text = self._remove_field(text, "url-status")
            changes["archive-no-url"] = True

        # archive-date requires archive-url
        if archive_date_val is not None and archive_url_val is None:
            text = self._remove_field(text, "archive-date")
            changes["archive-date-no-url"] = True

        # url-status requires archive-url (or url for bot: unknown)
        if status_val is not None and archive_url_val is None:
            if status_val.strip().lower() == "bot: unknown":
                if url_val is None:
                    text = self._remove_field(text, "url-status")
                    changes["orphan-url-status"] = True
            else:
                text = self._remove_field(text, "url-status")
                changes["orphan-url-status"] = True

        # --- Detect deprecated archive services ---
        if archive_url_val and _DEPRECATED_ARCHIVES.search(archive_url_val):
            changes["deprecated-archive"] = True

        # --- Validate Wayback Machine timestamp ---
        if archive_url_val and "web.archive.org" in archive_url_val:
            wm = re.search(r"/web/(\d{14})/", archive_url_val)
            if wm and archive_date_val:
                ts = wm.group(1)
                wb_date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                wb_date = wb_date.lstrip("0") if wb_date.startswith("0") else wb_date
                if wb_date != archive_date_val.strip():
                    changes["archive-date-mismatch"] = True

        # --- Add new archive from Wayback Machine ---
        if not api:
            return ProcessingResult(text=text, changes=changes)

        url_m = re.search(r"\|\s*url\s*=\s*([^\|}]+)", text)
        if not url_m:
            return ProcessingResult(text=text, changes=changes)
        url = url_m.group(1).strip()

        # Check Wayback Machine
        result = api.check_wayback(url)

        # Optionally create a new snapshot if none exists
        if not result and create_archive:
            log.info(
                "    + No existing snapshot, submitting to Wayback for archiving..."
            )
            if api.save_wayback(url):
                result = api.check_wayback(url)
                if result:
                    log.info("    + Snapshot created successfully")
                else:
                    log.info("    + Save submitted but snapshot not yet available")
            else:
                log.warning("    + Wayback save request failed")

        # Restrict to web/news types by default (unless --force-archive)
        if not force_all and template_type not in _WEB_TYPES:
            return ProcessingResult(text=text, changes=changes)

        if not result:
            return ProcessingResult(text=text, changes=changes)

        # Skip if archive-url already exists (incremental mode)
        if mode == Mode.INCREMENTAL and re.search(r"\|\s*archive-url\s*=", text):
            return ProcessingResult(text=text, changes=changes)

        # Check Wayback Machine (plus optional snapshot creation)
        result = api.check_wayback(url)

        # Optionally create a new snapshot if none exists
        if not result and create_archive:
            log.info(
                "    + No existing snapshot, submitting to Wayback for archiving..."
            )
            if api.save_wayback(url):
                result = api.check_wayback(url)
                if result:
                    log.info("    + Snapshot created successfully")
                else:
                    log.info("    + Save submitted but snapshot not yet available")
            else:
                log.warning("    + Wayback save request failed")

        if not result:
            return ProcessingResult(text=text, changes=changes)

        archive_url, archive_date = result

        # Remove existing archive params in force mode
        if mode == Mode.FORCE_REFRESH:
            text = re.sub(r"\|\s*archive-url\s*=[^\|}]+", "", text)
            text = re.sub(r"\|\s*archive-date\s*=[^\|}]+", "", text)
            text = re.sub(r"\|\s*url-status\s*=[^\|}]+", "", text)

        # Probe original URL to determine url-status
        # Only definitive 404/410 treated as dead; 403/429/timeout/etc. are unreliable
        url_status = "live"
        try:
            import requests

            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code in (404, 410):
                url_status = "dead"
        except Exception:
            pass

        text = (
            text
            + f" | archive-url = {archive_url} | archive-date = {archive_date} | url-status = {url_status}"
        )
        action = "Replaced" if mode == Mode.FORCE_REFRESH else "Added"
        log.info(
            "    + %s archive (from Wayback Machine, status=%s)", action, url_status
        )
        changes["archive"] = True

        return ProcessingResult(text=text, changes=changes)

    @staticmethod
    def _get_field(text: str, field: str) -> str | None:
        """Extract the value of a parameter from the citation body."""
        m = re.search(rf"\|\s*{re.escape(field)}\s*=\s*([^|]+)", text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _remove_field(text: str, field: str) -> str:
        """Remove a parameter and its value from the citation body."""
        return re.sub(rf"\|\s*{re.escape(field)}\s*=[^|]+", "", text, count=1)
