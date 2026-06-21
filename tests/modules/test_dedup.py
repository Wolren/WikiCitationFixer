from wikifix.config import ApiConfig, Mode
from wikifix.modules.dedup import DedupModule
from wikifix.services import ApiClient


def _make_context(overrides=None):
    ctx = {
        "template_type": "cite journal",
        "doi": None,
        "pmid": None,
        "title": "Test",
        "is_duplicate": False,
        "mode": Mode.INCREMENTAL,
        "api": ApiClient(ApiConfig(cache_dir="")),
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


class TestDedupModule:
    def test_detects_duplicate(self):
        mod = DedupModule()
        body = " | doi = 10.1000/dup"
        result = mod.process(body, _make_context({"is_duplicate": True}))
        assert result.changes["dedup"] is True
        assert result.text == body

    def test_no_change_for_unique(self):
        mod = DedupModule()
        body = " | doi = 10.1000/unique"
        result = mod.process(body, _make_context({"is_duplicate": False}))
        assert "dedup" not in result.changes
        assert result.text == body
