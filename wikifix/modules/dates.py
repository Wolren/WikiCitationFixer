"""
Date normalization module.

Normalizes date format to Wikipedia style while preserving all
available date information (day, month, year).
"""

import re

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult


class DateModule(CitationModule):
    name = "dates"
    description = "Normalize dates to Wikipedia format (preserving day info)"

    MONTHS_SHORT = {
        "jan": "January",
        "feb": "February",
        "mar": "March",
        "apr": "April",
        "may": "May",
        "jun": "June",
        "jul": "July",
        "aug": "August",
        "sep": "September",
        "oct": "October",
        "nov": "November",
        "dec": "December",
    }

    MONTHS_FULL = {
        "january": "January",
        "february": "February",
        "march": "March",
        "april": "April",
        "may": "May",
        "june": "June",
        "july": "July",
        "august": "August",
        "september": "September",
        "october": "October",
        "november": "November",
        "december": "December",
    }

    @staticmethod
    def _normalize_month(m: str) -> str:
        low = m.strip().lower()
        return DateModule.MONTHS_FULL.get(low, DateModule.MONTHS_SHORT.get(low, m))

    def _normalize(self, date: str) -> str:
        if not date:
            return date

        original = date.strip()

        # ISO YYYY-MM-DD → DD Month YYYY
        if m := re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", original):
            y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
            mn = self._normalize_month(
                {
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
                }.get(mo, mo)
            )
            return f"{int(d)} {mn} {y}"

        # ISO YYYY-MM → Month YYYY
        if m := re.match(r"(\d{4})-(\d{1,2})$", original):
            y, mo = m.group(1), m.group(2).zfill(2)
            mn = self._normalize_month(
                {
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
                }.get(mo, mo)
            )
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

    def process(self, text: str, context: dict) -> ProcessingResult:
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
