from unittest.mock import patch

import pytest
import requests_mock

from wikifix.config import ApiConfig, Mode
from wikifix.modules.sort import SortModule, _parse_param_name
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


class TestSortModule:
    def test_sorts_parameters(self):
        mod = SortModule()
        body = " | title = X | last = Smith | doi = 10.1000/xyz | date = 2024"
        result = mod.process(body, _make_context())
        text = result.text
        assert text.index("last") < text.index("doi")
        assert result.changes["sort"] is True

    def test_empty_body(self):
        mod = SortModule()
        result = mod.process("", _make_context())
        assert result.text == ""
        assert "sort" not in result.changes

    def test_sort_maintains_content(self):
        mod = SortModule()
        body = " | title = My Paper | last = Smith | date = 2024 | doi = 10.1000/test"
        result = mod.process(body, _make_context())
        for val in ("Smith", "My Paper", "2024", "10.1000/test"):
            assert val in result.text

    def test_known_parameters_ordered(self):
        assert SortModule.name == "sort"

    def test_parse_param_name_numbered(self):
        base, num = _parse_param_name("last5")
        assert base == "last"
        assert num == 5

    def test_parse_param_name_plain(self):
        base, num = _parse_param_name("title")
        assert base == "title"
        assert num == 0

    def test_parse_params_no_match_breaks(self):
        params = SortModule._parse_params("no pipe")
        assert params == []

    def test_parse_params_nested_curly(self):
        body = " | title = {{template|param}} | last = Smith"
        params = SortModule._parse_params(body)
        assert len(params) == 2
        assert params[0][2] == "title"
        assert params[1][2] == "last"

    def test_parse_params_wiki_links(self):
        body = " | title = [[Wiki link|label]] | last = Smith"
        params = SortModule._parse_params(body)
        assert len(params) == 2
        assert params[0][2] == "title"
        assert params[1][2] == "last"
