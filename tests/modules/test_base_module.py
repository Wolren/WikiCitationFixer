import pytest

from wikifix.base import CitationModule


class TestBaseModule:
    def test_raises_not_implemented(self):
        mod = CitationModule()
        with pytest.raises(NotImplementedError):
            mod.process("body", {})
