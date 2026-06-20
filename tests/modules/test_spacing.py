from wikifix.config import Mode
from wikifix.modules.spacing import SpacingModule
from wikifix.services import ApiClient


def _make_context(overrides=None):
    ctx = {
        "template_type": "cite journal",
        "doi": None,
        "pmid": None,
        "title": "Test",
        "is_duplicate": False,
        "mode": Mode.INCREMENTAL,
        "api": ApiClient(),
        "author_style": "normal",
        "refresh_authors": False,
        "max_authors": 6,
        "ids_to_fetch": ["issn", "pmid", "pmc", "s2cid", "qid"],
        "force_archive_all": False,
        "create_archive": False,
        "strip_issn": False,
    }
    if overrides:
        ctx.update(overrides)
    return ctx


class TestSpacingModule:
    def test_normalizes_spacing(self):
        mod = SpacingModule()
        body = " |last=Smith|first=John A.|title=Test Article"
        result = mod.process(body, _make_context())
        assert "| last = " in result.text
        assert "| first = " in result.text
        assert "| title = " in result.text

    def test_already_normalized_no_change(self):
        mod = SpacingModule()
        body = " | last = Smith | first = John A."
        result = mod.process(body, _make_context())
        assert result.changes.get("spacing") is False

    def test_spacing_changed_flag(self):
        mod = SpacingModule()
        body = " |last=Smith"
        result = mod.process(body, _make_context())
        assert result.changes.get("spacing") is True

    def test_empty_body(self):
        mod = SpacingModule()
        result = mod.process("", _make_context())
        assert result.text == ""

    def test_format_equals_leading_pipe(self):
        mod = SpacingModule()
        result = mod._format_equals(" |last=Smith|title=Test")
        assert "|last = " in result

    def test_format_equals_trailing_pipe(self):
        mod = SpacingModule()
        result = mod._format_equals("| last=Smith |")
        assert "|last = " in result

    def test_format_pipes_basic(self):
        mod = SpacingModule()
        result = mod._format_pipes("{{cite journal|last=Smith|title=Test}}")
        assert result == "{{cite journal | last=Smith | title=Test}}"

    def test_format_pipes_full_template(self):
        mod = SpacingModule()
        result = mod._format_pipes(
            "{{cite journal|last=Smith|title=Test|doi=10.1000/xyz}}"
        )
        assert "{{cite journal |" in result

    def test_format_pipes_no_pipe(self):
        mod = SpacingModule()
        result = mod._format_pipes("plain text")
        assert result == "plain text"
