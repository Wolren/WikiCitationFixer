from wikifix.config import Mode
from wikifix.modules.dates import DateModule
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


class TestDateModule:
    def test_normalizes_iso_date(self):
        mod = DateModule()
        body = " | date = 2024-03-15"
        result = mod.process(body, _make_context())
        assert "15 March 2024" in result.text

    def test_normalizes_month_dd_yyyy(self):
        mod = DateModule()
        body = " | date = March 15, 2024"
        result = mod.process(body, _make_context())
        assert "15 March 2024" in result.text

    def test_normalizes_dd_month_yyyy(self):
        mod = DateModule()
        body = " | date = 15 March 2024"
        result = mod.process(body, _make_context())
        assert "15 March 2024" in result.text

    def test_normalizes_month_year(self):
        mod = DateModule()
        body = " | date = March 2024"
        result = mod.process(body, _make_context())
        assert "March 2024" in result.text

    def test_normalizes_bare_year(self):
        mod = DateModule()
        body = " | date = 2024"
        result = mod.process(body, _make_context())
        assert "2024" in result.text

    def test_already_normalized_no_change(self):
        mod = DateModule()
        body = " | date = 15 March 2024"
        result = mod.process(body, _make_context())
        assert result.changes.get("date") is False

    def test_no_date_field(self):
        mod = DateModule()
        body = " | title = Test"
        result = mod.process(body, _make_context())
        assert result.changes.get("date") is False

    def test_normalize_abbrev_month(self):
        mod = DateModule()
        body = " | date = 15 Mar 2024"
        result = mod.process(body, _make_context())
        assert "15 March 2024" in result.text

    def test_empty_date_no_change(self):
        mod = DateModule()
        body = " | date = "
        result = mod.process(body, _make_context())
        assert result.changes.get("date") is False

    def test_iso_year_month(self):
        mod = DateModule()
        body = " | date = 2024-03"
        result = mod.process(body, _make_context())
        assert "March 2024" in result.text

    def test_month_year_normalizes_month(self):
        mod = DateModule()
        body = " | date = Mar 2024"
        result = mod.process(body, _make_context())
        assert "March 2024" in result.text

    def test_unrecognized_date_format(self):
        mod = DateModule()
        body = " | date = some date"
        result = mod.process(body, _make_context())
        assert "some date" in result.text
        assert result.changes.get("date") is False
