"""
Base class for all citation fix modules.
"""

from typing import Any

from wikifix.config import ProcessingResult


class CitationModule:
    """Base class for a modular citation fix.

    Subclasses override ``process()`` to transform the body text of a
    citation template and report which changes were made.
    """

    name: str = ""
    description: str = ""

    def process(self, text: str, context: dict[str, Any]) -> ProcessingResult:
        """Apply the module's transformations.

        Args:
            text: The body of a citation template (everything between
                  ``{{cite ...`` and ``}}``).
            context: Shared context dict that may contain:
                - template_type: str  (journal, book, web, …)
                - doi: str | None
                - mode: Mode
                - api: ApiClient
                - raw_citation: str  (the full match text)

        Returns:
            ProcessingResult with the (possibly modified) text and a
            dict mapping change keys to booleans.
        """
        raise NotImplementedError
