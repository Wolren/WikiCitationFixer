"""
Parameter spacing module.

Normalizes whitespace around pipes, equals signs, and parameter
values inside citation templates.
"""

import re

from wikifix.base import CitationModule
from wikifix.config import ProcessingResult
from wikifix.logger import get_logger; log = get_logger()


class SpacingModule(CitationModule):
    """Normalize pipe and equals-sign spacing in parameters."""

    name = "spacing"
    description = "Normalize pipe and equals-sign spacing in parameters"

    @staticmethod
    def _format_equals(text: str) -> str:
        """Ensure ``| param = value`` spacing around each parameter."""

        def repl(m):
            param = m.group(1).strip()
            value = m.group(2).strip()
            return f"|{param} = {value}"

        return re.sub(r"\|\s*([^=\|]+?)\s*=\s*([^\|]+?)(?=\s*\||$)", repl, text)

    @staticmethod
    def _format_pipes(text: str) -> str:
        """Normalise spacing around pipe characters."""
        m = re.match(r"(\{\{cite\s*\w+)(.*?)(\}\})", text, re.IGNORECASE | re.DOTALL)
        if m:
            opening, body, closing = m.groups()
            body = re.sub(r"\s*\|\s*", " | ", body)
            return f"{opening}{body}{closing}"
        return re.sub(r"\s*\|\s*", " | ", text)

    def process(self, text: str, context: dict) -> ProcessingResult:
        """Normalize whitespace around pipes and equals signs."""
        start = text
        text = self._format_equals(text)
        text = self._format_pipes(text)
        return ProcessingResult(text=text, changes={"spacing": text != start})
