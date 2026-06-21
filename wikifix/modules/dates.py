"""
Date normalization module.

Normalizes date format to Wikipedia style while preserving all
available date information (day, month, year).
"""

import re
from typing import Any

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult
from wikifix.logger import get_logger

log = get_logger()


class DateModule(CitationModule):
    """Normalize dates to Wikipedia format."""

    name = "dates"
    description = "Normalize dates to Wikipedia format (preserving day info)"

    _MONTH = {
        "jan": "January",
        "january": "January",
        "feb": "February",
        "february": "February",
        "mar": "March",
        "march": "March",
        "apr": "April",
        "april": "April",
        "may": "May",
        "jun": "June",
        "june": "June",
        "jul": "July",
        "july": "July",
        "aug": "August",
        "august": "August",
        "sep": "September",
        "september": "September",
        "oct": "October",
        "october": "October",
        "nov": "November",
        "november": "November",
        "dec": "December",
        "december": "December",
    }

    _NUM_TO_MONTH = {
        "01": "January",
        "02": "February",
        "03": "March",
        "04": "April",
        "05": "May",
        "06": "June",
        "07": "July",
        "08": "August",
        "09": "September",
        "10": "October",
        "11": "November",
        "12": "December",
    }

    @staticmethod
    def _normalize_month(m: str) -> str:
        """Normalize a month name to title-case (e.g. ``jan`` → ``January``)."""
        low = m.strip().lower()
        return DateModule._MONTH.get(low, m)

    def _normalize(self, date: str) -> str:
        """Convert a date string to Wikipedia format (DD Month YYYY)."""
        if not date:
            return date

        original = date.strip()

        # ISO YYYY-MM-DD → DD Month YYYY
        if m := re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", original):
            y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
            mn = self._NUM_TO_MONTH.get(mo, mo)
            return f"{int(d)} {mn} {y}"

        # ISO YYYY-MM → Month YYYY
        if m := re.match(r"(\d{4})-(\d{1,2})$", original):
            y, mo = m.group(1), m.group(2).zfill(2)
            mn = self._NUM_TO_MONTH.get(mo, mo)
            return f"{mn} {y}"

        # "Month DD, YYYY" or "Month DD YYYY" → "DD Month YYYY"
        if m := re.match(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})$", original, re.IGNORECASE):
            mn = self._normalize_month(m.group(1))
            return f"{int(m.group(2))} {mn} {m.group(3)}"

        # "DD Month YYYY" — already Wikipedia format, just normalize month name
        if m := re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})$", original, re.IGNORECASE):
            mn = self._normalize_month(m.group(2))
            return f"{int(m.group(1))} {mn} {m.group(3)}"

        # "Month YYYY" — already Wikipedia format
        if m := re.match(r"(\w+)\s+(\d{4})$", original, re.IGNORECASE):
            mn = self._normalize_month(m.group(1))
            if mn != m.group(1):
                return f"{mn} {m.group(2)}"
            return original

        # Bare year
        if re.fullmatch(r"\d{4}", original):
            return original

        return original

    def process(self, text: str, context: dict[str, Any]) -> ProcessingResult:
        """Normalize the |date= value to Wikipedia format."""
        changes = {"date": False}
        m = re.search(r"\|\s*date\s*=\s*([^\|}]+)", text)
        if not m:
            return ProcessingResult(text=text, changes=changes)

        old = m.group(1).strip()
        new = self._normalize(old)
        if new != old:
            text = text[: m.start(1)] + new + text[m.end(1) :]
            changes["date"] = True

        return ProcessingResult(text=text, changes=changes)
