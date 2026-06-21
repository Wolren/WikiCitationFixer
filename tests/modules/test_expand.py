import requests_mock

from wikifix.config import ApiConfig, Mode
from wikifix.modules.expand import (
    ExpandModule,
    _add_field,
    _clean_journal,
    _clean_publisher,
    _format_date_from_parts,
    _format_date_string,
    _has_field,
)
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


class TestExpandHelpers:
    def test_has_field_true(self):
        assert _has_field(" | doi = 10.1000/xyz", "doi")

    def test_has_field_false(self):
        assert not _has_field(" | title = Foo", "doi")

    def test_add_field_new(self):
        result = _add_field(" | title = Foo", "doi", "10.1000/xyz")
        assert "doi=10.1000/xyz" in result

    def test_add_field_skip_when_exists(self):
        result = _add_field(" | doi = 10.1000/old", "doi", "10.1000/new")
        assert "10.1000/old" in result

    def test_add_field_force_replace(self):
        result = _add_field(" | doi = 10.1000/old", "doi", "10.1000/new", force=True)
        assert "10.1000/new" in result
        assert "10.1000/old" not in result

    def test_can_use_journal_cite_journal(self):
        assert ExpandModule._can_use_journal("cite journal")

    def test_can_use_journal_citation(self):
        assert ExpandModule._can_use_journal("citation")

    def test_can_use_journal_cite_book(self):
        assert not ExpandModule._can_use_journal("cite book")

    def test_container_field_journal(self):
        assert ExpandModule._container_field("cite journal") == "journal"

    def test_container_field_web(self):
        assert ExpandModule._container_field("cite web") == "website"

    def test_container_field_news(self):
        assert ExpandModule._container_field("cite news") == "newspaper"

    def test_clean_publisher_strips_suffix(self):
        result = _clean_publisher("Springer Publishing")
        assert result == "Springer"

    def test_clean_publisher_strips_parenthetical(self):
        result = _clean_publisher("Springer (Berlin)")
        assert result == "Springer"

    def test_clean_publisher_keeps_press(self):
        result = _clean_publisher("Oxford University Press")
        assert result == "Oxford University Press"

    def test_clean_journal_strips_parenthetical(self):
        result = _clean_journal("Nature (London)")
        assert result == "Nature"

    def test_format_date_from_parts_full(self):
        assert _format_date_from_parts([2024, 3, 15]) == "15 March 2024"

    def test_format_date_from_parts_month_year(self):
        assert _format_date_from_parts([2024, 3]) == "March 2024"

    def test_format_date_from_parts_year_only(self):
        assert _format_date_from_parts([2024]) == "2024"

    def test_format_date_from_parts_empty(self):
        assert _format_date_from_parts([]) == ""

    def test_format_date_string_iso(self):
        assert _format_date_string("2024-03-15") == "15 March 2024"

    def test_format_date_string_year(self):
        assert _format_date_string("2024") == "2024"

    def test_format_date_string_unrecognized(self):
        assert _format_date_string("March 2024") == "March 2024"

    def test_container_field_magazine(self):
        assert ExpandModule._container_field("cite magazine") == "magazine"

    def test_container_field_fallback(self):
        assert ExpandModule._container_field("cite thesis") == "journal"

    def test_extract_field_found(self):
        from wikifix.modules.expand import _extract_field

        assert _extract_field(" | doi = 10.1000/xyz", "doi") == "10.1000/xyz"

    def test_extract_field_missing(self):
        from wikifix.modules.expand import _extract_field

        assert _extract_field(" | title = Foo", "doi") is None


class TestExpandModule:
    def test_doi_incremental_skip(self):
        mod = ExpandModule()
        body = " | doi = 10.1000/test | title = Existing | journal = Existing"
        result = mod.process(body, _make_context({"doi": "10.1000/test"}))
        assert result.text == body

    def test_empty_body(self):
        mod = ExpandModule()
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works",
                json={"message": {"items": []}},
            )
            result = mod.process("", _make_context())
            assert result.text == ""

    def test_expand_from_doi_fills_fields(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_doi1"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/test_doi"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/test_doi",
                json={
                    "message": {
                        "title": ["Test Article"],
                        "container-title": ["Test Journal"],
                        "volume": "10",
                        "issue": "2",
                        "page": "100-110",
                        "published-print": {"date-parts": [[2024, 3, 15]]},
                        "publisher": "Test Press",
                    }
                },
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(
                body, _make_context({"doi": "10.1000/test_doi", "api": api})
            )
            assert "|title=Test Article" in result.text
            assert "|journal=Test Journal" in result.text
            assert "|volume=10" in result.text
            assert "|issue=2" in result.text
            assert "|pages=100-110" in result.text
            assert "|date=15 March 2024" in result.text

    def test_expand_from_doi_skip_existing_fields(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_doi2"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/existing | title = Already | journal = Has It"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/existing",
                json={
                    "message": {
                        "title": ["Different"],
                        "container-title": ["Different Journal"],
                    }
                },
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(
                body, _make_context({"doi": "10.1000/existing", "api": api})
            )
            assert "title = Already" in result.text
            assert "journal = Has It" in result.text

    def test_expand_from_doi_europepmc_supplement(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_doi3"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/epmc_supp"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/epmc_supp",
                json={"message": {"publisher": "CrossRef Pub"}},
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "Europe PMC Title",
                                "journalTitle": "EPMC Journal",
                                "volume": "5",
                                "issue": "1",
                                "pageInfo": "50-60",
                                "firstPublicationDate": "2023-06-01",
                                "source": "MED",
                                "id": "11111111",
                            }
                        ]
                    }
                },
            )
            result = mod.process(
                body, _make_context({"doi": "10.1000/epmc_supp", "api": api})
            )
            assert "|title=Europe PMC Title" in result.text
            assert "|journal=EPMC Journal" in result.text
            assert "|volume=5" in result.text
            assert "|issue=1" in result.text
            assert "|pages=50-60" in result.text
            assert "|date=1 June 2023" in result.text

    def test_expand_from_doi_pmid_pmc_from_epmc(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_doi4"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/epmc_ids"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/epmc_ids",
                json={"message": {"title": ["Test"]}},
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "Test",
                                "source": "MED",
                                "id": "22222222",
                                "pmcid": "PMC3333333",
                            }
                        ]
                    }
                },
            )
            result = mod.process(
                body, _make_context({"doi": "10.1000/epmc_ids", "api": api})
            )
            assert "|pmid=22222222" in result.text
            assert "|pmc=3333333" in result.text

    def test_expand_from_pmid_fills_fields(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_pmid"))
        api = ApiClient(cfg)
        body = " | pmid = 44444444"
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "PMID Article",
                                "journalTitle": "PMID Journal",
                                "volume": "3",
                                "issue": "4",
                                "pageInfo": "200-210",
                                "firstPublicationDate": "2022-11-15",
                            }
                        ]
                    }
                },
            )
            result = mod.process(body, _make_context({"pmid": "44444444", "api": api}))
            assert "|title=PMID Article" in result.text
            assert "|journal=PMID Journal" in result.text
            assert "|volume=3" in result.text
            assert "|issue=4" in result.text
            assert "|pages=200-210" in result.text
            assert "|date=15 November 2022" in result.text

    def test_expand_from_arxiv_with_doi_backfill(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_arxiv"))
        api = ApiClient(cfg)
        body = " | arxiv = 2101.00001"
        xml_body = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <title>Arxiv Article</title>
    <summary>Abstract here</summary>
    <published>2021-06-15T00:00:00Z</published>
    <author><name>John Smith</name></author>
    <arxiv:doi>10.1000/arxiv_doi</arxiv:doi>
  </entry>
</feed>"""
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=2101.00001",
                text=xml_body,
            )
            result = mod.process(body, _make_context({"api": api}))
            assert "|title=Arxiv Article" in result.text
            assert "|date=2021-06-15" in result.text
            assert "|doi=10.1000/arxiv_doi" in result.text

    def test_expand_from_arxiv_no_doi_skips(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_arxiv2"))
        api = ApiClient(cfg)
        body = " | arxiv = 2101.00002"
        xml_body = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <title>No Doi Arxiv</title>
    <summary>Abstract</summary>
    <published>2021-07-01T00:00:00Z</published>
    <author><name>Jane Doe</name></author>
  </entry>
</feed>"""
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=2101.00002",
                text=xml_body,
            )
            result = mod.process(body, _make_context({"api": api}))
            assert "|title=No Doi Arxiv" in result.text
            assert "|doi=" not in result.text

    def test_expand_from_isbn_fills_fields(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_isbn"))
        api = ApiClient(cfg)
        body = " | isbn = 9780306406157"
        with requests_mock.Mocker() as m:
            m.get(
                "https://openlibrary.org/api/books",
                json={
                    "ISBN:9780306406157": {
                        "title": "ISBN Book",
                        "authors": [{"name": "Author Name"}],
                        "publish_date": "2022",
                        "publishers": [{"name": "ISBN Press"}],
                    }
                },
            )
            result = mod.process(body, _make_context({"api": api}))
            assert "|title=ISBN Book" in result.text
            assert "|publisher=ISBN Press" in result.text
            assert "|date=2022" in result.text

    def test_force_refresh_strips_and_refills(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_force"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/force_test | title = Old Title"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/force_test",
                json={
                    "message": {
                        "title": ["New Title"],
                        "container-title": ["New Journal"],
                        "volume": "20",
                        "page": "1-10",
                        "published-print": {"date-parts": [[2025, 1, 1]]},
                    }
                },
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(
                body,
                _make_context(
                    {
                        "doi": "10.1000/force_test",
                        "api": api,
                        "mode": Mode.FORCE_REFRESH,
                    }
                ),
            )
            assert "|title=New Title" in result.text
            assert "Old Title" not in result.text
            assert "|journal=New Journal" in result.text

    def test_no_api_returns_unchanged(self):
        mod = ExpandModule()
        body = " | doi = 10.1000/test"
        result = mod.process(body, _make_context({"doi": "10.1000/test", "api": None}))
        assert result.text == body
        assert result.changes["expand"] is False

    def test_extract_doi_from_url_returns_doi(self):
        mod = ExpandModule()
        body = " | url = https://doi.org/10.1000/from_url"
        doi = mod._extract_doi_from_url(body)
        assert doi == "10.1000/from_url"

    def test_extract_doi_from_url_returns_none_when_doi_exists(self):
        mod = ExpandModule()
        body = " | doi = 10.1000/explicit | url = https://doi.org/10.1000/ignored"
        doi = mod._extract_doi_from_url(body)
        assert doi is None

    def test_extract_doi_from_url_no_url(self):
        mod = ExpandModule()
        body = " | title = Test"
        doi = mod._extract_doi_from_url(body)
        assert doi is None

    def test_expand_from_url_doi_no_explicit_doi(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "eud"))
        api = ApiClient(cfg)
        body = " | url = https://doi.org/10.1000/from_url"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/from_url",
                json={
                    "message": {
                        "title": ["URL DOI"],
                        "container-title": ["URL Journal"],
                        "published-print": {"date-parts": [[2024]]},
                    }
                },
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(body, _make_context({"api": api}))
            assert "title=URL DOI" in result.text
            assert "journal=URL Journal" in result.text

    def test_expand_from_title_via_crossref(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "et"))
        api = ApiClient(cfg)
        body = " | title = Found Article"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works",
                json={"message": {"items": [{"DOI": "10.1000/title_match"}]}},
            )
            m.get(
                "https://api.crossref.org/works/10.1000/title_match",
                json={
                    "message": {
                        "title": ["Found Article"],
                        "container-title": ["Found Journal"],
                        "published-print": {"date-parts": [[2024]]},
                    }
                },
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(body, _make_context({"api": api}))
            assert "Found Article" in result.text
            assert "journal=Found Journal" in result.text
            assert "date=2024" in result.text

    def test_expand_from_title_no_match(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "etnm"))
        api = ApiClient(cfg)
        body = " | title = Nonexistent"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works",
                json={"message": {"items": []}},
            )
            result = mod.process(body, _make_context({"api": api}))
            assert result.text == body

    def test_extract_doi_from_url_non_doi_url(self):
        mod = ExpandModule()
        body = " | url = https://example.com/article"
        doi = mod._extract_doi_from_url(body)
        assert doi is None

    def test_doi_refill_cite_book_publisher(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_cbook"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/cite_book | isbn = 9999999999999"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/cite_book",
                json={
                    "message": {
                        "title": ["Book Title"],
                        "publisher": "Book Publisher Inc",
                    }
                },
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(
                body,
                _make_context(
                    {
                        "doi": "10.1000/cite_book",
                        "api": api,
                        "template_type": "cite book",
                    }
                ),
            )
            assert "|publisher=Book Publisher" in result.text
            assert "|title=Book Title" in result.text

    def test_doi_expand_page_and_pages_both_exist(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_pp"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/pp | page = 1 | pages = 2-3"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/pp",
                json={"message": {"page": "4-5"}},
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(body, _make_context({"doi": "10.1000/pp", "api": api}))
            assert "page = 1" in result.text
            assert "pages = 2-3" in result.text

    def test_doi_expand_article_number_exists(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_an"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/an | article-number = E123"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/an",
                json={"message": {"page": "100-110"}},
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            result = mod.process(body, _make_context({"doi": "10.1000/an", "api": api}))
            assert "article-number = E123" in result.text

    def test_pmid_epmc_no_result_unchanged(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_pmidnr"))
        api = ApiClient(cfg)
        body = " | pmid = 99999999"
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                status_code=404,
            )
            result = mod.process(body, _make_context({"pmid": "99999999", "api": api}))
            assert "pmid = 99999999" in result.text
            assert result.changes["expand"] is False

    def test_arxiv_no_result_unchanged(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_arxivnr"))
        api = ApiClient(cfg)
        body = " | arxiv = 9999.99999"
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=9999.99999",
                status_code=404,
            )
            result = mod.process(body, _make_context({"api": api}))
            assert "arxiv = 9999.99999" in result.text
            assert result.changes["expand"] is False

    def test_isbn_no_result_unchanged(self, tmp_path):
        mod = ExpandModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "exp_isbnnr"))
        api = ApiClient(cfg)
        body = " | isbn = 9780000000000"
        with requests_mock.Mocker() as m:
            m.get(
                "https://openlibrary.org/api/books",
                json={},
            )
            result = mod.process(body, _make_context({"api": api}))
            assert "isbn = 9780000000000" in result.text
            assert result.changes["expand"] is False
