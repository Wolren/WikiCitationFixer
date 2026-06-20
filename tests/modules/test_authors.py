import pytest
import requests_mock

from wikifix.config import ApiConfig, Mode
from wikifix.modules.authors import AuthorModule
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


class TestAuthorModule:
    def test_vauthors_to_last_first_normal(self):
        mod = AuthorModule()
        body = " | vauthors = Smith JA"
        result = mod.process(body, _make_context({"author_style": "normal"}))
        assert "|last=Smith" in result.text
        assert "|first=JA" in result.text
        assert "vauthors" not in result.text
        assert result.changes["authors"] is True

    def test_last_first_to_vauthors_vancouver(self):
        mod = AuthorModule()
        body = " | last = Smith | first = John A."
        result = mod.process(body, _make_context({"author_style": "vancouver"}))
        assert "|vauthors=Smith JA" in result.text
        assert result.changes["authors"] is True

    def test_max_authors_truncation(self):
        mod = AuthorModule()
        body = " | last1 = A | first1 = A1 | last2 = B | first2 = B1 | last3 = C | first3 = C1"
        result = mod.process(
            body, _make_context({"author_style": "vancouver", "max_authors": 2})
        )
        assert "et al" in result.text
        assert result.changes["authors"] is True

    def test_no_change_if_already_normal(self):
        mod = AuthorModule()
        body = " | last = Smith | first = John"
        result = mod.process(body, _make_context({"author_style": "normal"}))
        assert result.changes["authors"] is False

    def test_no_author_conversion_if_already_vancouver(self):
        mod = AuthorModule()
        body = " | vauthors = Smith JA"
        result = mod.process(body, _make_context({"author_style": "vancouver"}))
        assert "vauthors = Smith JA" in result.text

    def test_extract_initials(self):
        mod = AuthorModule()
        assert mod.extract_initials("John A.") == "JA"
        assert mod.extract_initials("John Arthur") == "JA"
        assert mod.extract_initials("Smith") == "S"
        assert mod.extract_initials("") == ""
        assert mod.extract_initials("J. K.") == "JK"
