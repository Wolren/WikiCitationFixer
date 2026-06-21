from wikifix.config import ApiConfig, Mode
from wikifix.field_utils import get_field, has_field, remove_field, set_field
from wikifix.modules.cleanup import CleanupModule
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


class TestCleanupHelpers:
    def test_get_field_found(self):
        assert get_field(" | doi = 10.1000/xyz", "doi") == "10.1000/xyz"

    def test_get_field_missing(self):
        assert get_field(" | title = Foo", "doi") is None

    def test_field_exists_true(self):
        assert has_field(" | doi = 10.1000/xyz", "doi") is True

    def test_field_exists_false(self):
        assert has_field(" | title = Foo", "doi") is False

    def test_remove_field(self):
        result = remove_field(" | doi = 10.1000/xyz | title = Foo", "doi")
        assert "doi" not in result

    def test_fix_isbn_10_valid(self):
        mod = CleanupModule()
        result = mod._fix_isbn("0-306-40615-2")
        assert result == "9780306406157"

    def test_fix_isbn_10_invalid(self):
        mod = CleanupModule()
        result = mod._fix_isbn("0-306-40615-3")
        assert result is None

    def test_fix_isbn_13_valid(self):
        mod = CleanupModule()
        result = mod._fix_isbn("9780306406157")
        assert result == "9780306406157"

    def test_fix_isbn_13_invalid(self):
        mod = CleanupModule()
        result = mod._fix_isbn("9780306406158")
        assert result is None

    def test_fix_isbn_short(self):
        mod = CleanupModule()
        result = mod._fix_isbn("12345")
        assert result is None

    def test_fix_isbn_with_x_check(self):
        mod = CleanupModule()
        result = mod._fix_isbn("080442957X")
        assert result == "9780804429573"

    def test_fix_isbn_10_check_digit_0(self):
        mod = CleanupModule()
        result = mod._fix_isbn("0000000000")
        assert result == "9780000000002"

    def test_fix_isbn_10_invalid_char_in_first9(self):
        mod = CleanupModule()
        result = mod._fix_isbn("0-306-X0615-2")
        assert result is None

    def test_fix_isbn_13_invalid_char_in_first12(self):
        mod = CleanupModule()
        result = mod._fix_isbn("97803X6406157")
        assert result is None

    def test_strip_extra_text_volume_prefix(self):
        mod = CleanupModule()
        assert mod._strip_extra_text("Vol. 10", "volume") == "10"

    def test_strip_extra_text_issue_suffix(self):
        mod = CleanupModule()
        assert mod._strip_extra_text("2 no.", "issue") == "2"

    def test_strip_extra_text_pages_prefix(self):
        mod = CleanupModule()
        assert mod._strip_extra_text("pp. 100-110", "page") == "100-110"

    def test_strip_extra_text_edition_suffix(self):
        mod = CleanupModule()
        assert mod._strip_extra_text("3rd ed.", "edition") == "3rd"

    def test_set_field_replaces_value(self):
        result = set_field(" | volume = Vol. 10", "volume", "10")
        assert "| volume = 10" in result

    def test_set_field_not_found(self):
        result = set_field(" | title = Foo", "volume", "10")
        assert result == " | title = Foo"

    def test_detect_citation_type_journal(self):
        mod = CleanupModule()
        body = " | journal = Test Journal"
        assert mod._detect_citation_type(body) == "cite journal"

    def test_detect_citation_type_news(self):
        mod = CleanupModule()
        body = " | newspaper = Test News"
        assert mod._detect_citation_type(body) == "cite news"

    def test_detect_citation_type_magazine(self):
        mod = CleanupModule()
        body = " | magazine = Test Mag"
        assert mod._detect_citation_type(body) == "cite magazine"

    def test_detect_citation_type_web(self):
        mod = CleanupModule()
        body = " | website = Example.com"
        assert mod._detect_citation_type(body) == "cite web"

    def test_detect_citation_type_book(self):
        mod = CleanupModule()
        body = " | isbn = 9780306406157 | title = Book"
        assert mod._detect_citation_type(body) == "cite book"

    def test_detect_citation_type_thesis(self):
        mod = CleanupModule()
        body = " | degree = PhD"
        assert mod._detect_citation_type(body) == "cite thesis"

    def test_detect_citation_type_thesis_type(self):
        mod = CleanupModule()
        body = " | type = PhD thesis"
        assert mod._detect_citation_type(body) == "cite thesis"

    def test_detect_citation_type_work_fallback(self):
        mod = CleanupModule()
        body = " | work = Something"
        assert mod._detect_citation_type(body) == "cite web"

    def test_detect_citation_type_none(self):
        mod = CleanupModule()
        assert mod._detect_citation_type(" | title = Alone") is None

    def test_detect_citation_type_isbn_with_journal_returns_journal(self):
        mod = CleanupModule()
        body = " | isbn = 9780306406157 | journal = Test"
        assert mod._detect_citation_type(body) == "cite journal"


class TestCleanupModule:
    def test_deprecated_month(self):
        mod = CleanupModule()
        body = " | month = March | year = 2024"
        result = mod.process(body, _make_context())
        assert "month" not in result.text
        assert result.changes["deprecated-param"] is True

    def test_deprecated_coauthors(self):
        mod = CleanupModule()
        body = " | coauthors = Smith, J"
        result = mod.process(body, _make_context())
        assert "coauthors" not in result.text
        assert result.changes["deprecated-param"] is True

    def test_nbsp_fix(self):
        mod = CleanupModule()
        body = " | title = Test\xa0Article"
        result = mod.process(body, _make_context())
        assert "\xa0" not in result.text
        assert result.changes["nbsp-fix"] is True

    def test_empty_title(self):
        mod = CleanupModule()
        body = " | title = "
        result = mod.process(body, _make_context())
        assert "title" not in result.text
        assert result.changes["empty-title"] is True

    def test_placeholder_title(self):
        mod = CleanupModule()
        body = " | title = Untitled"
        result = mod.process(body, _make_context())
        assert result.changes["placeholder-title"] is True

    def test_typo_parameter(self):
        mod = CleanupModule()
        body = " | acces-date = 2024-01-01"
        result = mod.process(body, _make_context())
        assert "acces-date" in result.rename_params
        assert result.rename_params["acces-date"] == "access-date"
        assert result.changes["typo-param"] is True

    def test_isbn_10_to_13(self):
        mod = CleanupModule()
        body = " | isbn = 0-306-40615-2"
        result = mod.process(body, _make_context())
        assert "9780306406157" in result.text
        assert (
            result.changes.get("isbn-normalized") is True
            or result.changes.get("invalid-isbn") is not None
        )

    def test_invalid_url_status(self):
        mod = CleanupModule()
        body = " | url = https://example.com | url-status = invalid-status"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert "url-status" not in result.text
        assert result.changes["invalid-url-status"] is True

    def test_empty_params_removed(self):
        mod = CleanupModule()
        body = " | title = Real | pages = | last = Smith"
        result = mod.process(body, _make_context())
        assert "pages" not in result.text
        assert result.changes["empty-param"] is True

    def test_location_without_publisher(self):
        mod = CleanupModule()
        body = " | location = New York | title = Test"
        result = mod.process(body, _make_context({"template_type": "cite book"}))
        assert result.changes["location-no-publisher"] is True

    def test_orphan_access_date(self):
        mod = CleanupModule()
        body = " | access-date = 2024-01-01"
        result = mod.process(body, _make_context())
        assert "access-date" not in result.text
        assert result.changes["orphan-access-date"] is True

    def test_year_date_conflict(self):
        mod = CleanupModule()
        body = " | date = 2024-03-15 | year = 2024"
        result = mod.process(body, _make_context())
        assert "year" not in result.text
        assert result.changes["year-date-conflict"] is True

    def test_deprecated_day(self):
        mod = CleanupModule()
        body = " | day = 15 | month = March | year = 2024"
        result = mod.process(body, _make_context())
        assert "day" not in result.text
        assert "month" not in result.text
        assert result.changes["deprecated-param"] is True

    def test_none_value_removed(self):
        mod = CleanupModule()
        body = " | title = None | last = Smith"
        result = mod.process(body, _make_context())
        assert "title" not in result.text
        assert result.changes["none-value"] is True

    def test_page_pages_conflict(self):
        mod = CleanupModule()
        body = " | page = 100 | pages = 100-110"
        result = mod.process(body, _make_context())
        assert "pages" not in result.text
        assert result.changes["page-pages-conflict"] is True

    def test_citation_type_detection(self):
        mod = CleanupModule()
        body = " | journal = Test J | title = Foo"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.changes.get("citation-type") is True
        assert result.new_template_type == "cite journal"

    def test_citation_conversion_to_book(self):
        mod = CleanupModule()
        body = " | isbn = 9780306406157 | work = Book Title | place = NY"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.new_template_type == "cite book"
        assert result.rename_params.get("work") == "title"

    def test_extra_text_in_volume(self):
        mod = CleanupModule()
        body = " | volume = Vol. 10"
        result = mod.process(body, _make_context())
        assert "| volume = 10" in result.text
        assert result.changes["extra-text"] is True

    def test_invalid_isbn(self):
        mod = CleanupModule()
        body = " | isbn = 12345"
        result = mod.process(body, _make_context())
        assert result.changes.get("invalid-isbn") is True

    def test_external_link_in_title(self):
        mod = CleanupModule()
        body = " | title = https://example.com"
        result = mod.process(body, _make_context())
        assert result.changes.get("external-link") is True

    def test_work_journal_dedup(self):
        mod = CleanupModule()
        body = " | work = Same Journal | journal = Same Journal"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert "journal" not in result.text
        assert result.changes.get("work-journal-dedup") is True

    def test_orphan_doi_broken_date(self):
        mod = CleanupModule()
        body = " | doi-broken-date = 2024-01-01"
        result = mod.process(body, _make_context())
        assert "doi-broken-date" not in result.text
        assert result.changes["orphan-doi-broken-date"] is True

    def test_periodical_conflict_web_journal(self):
        mod = CleanupModule()
        body = " | journal = Test J | title = Foo"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert "journal" not in result.text
        assert result.changes["periodical-conflict"] is True

    def test_periodical_conflict_journal_work(self):
        mod = CleanupModule()
        body = " | work = Test W | title = Foo"
        result = mod.process(body, _make_context({"template_type": "cite journal"}))
        assert "work" not in result.text
        assert result.changes["periodical-conflict"] is True

    def test_work_with_isbn_removed(self):
        mod = CleanupModule()
        body = " | isbn = 9780306406157 | work = Some Work | title = Book"
        result = mod.process(body, _make_context())
        assert "work" not in result.text
        assert result.changes["work-with-isbn"] is True

    def test_extra_text_in_issue(self):
        mod = CleanupModule()
        body = " | issue = no. 3"
        result = mod.process(body, _make_context())
        assert "| issue = 3" in result.text or result.changes.get("extra-text") is True

    def test_extra_text_in_edition(self):
        mod = CleanupModule()
        body = " | edition = 2nd ed."
        result = mod.process(body, _make_context())
        assert result.changes.get("extra-text") is True

    def test_missing_title_warning(self):
        mod = CleanupModule()
        body = " | url = https://example.com"
        result = mod.process(body, _make_context())
        assert result.changes.get("missing-title") is True

    def test_missing_date_warning(self):
        mod = CleanupModule()
        body = " | title = Test"
        result = mod.process(body, _make_context())
        assert result.changes.get("missing-date") is True

    def test_missing_url_for_cite_web(self):
        mod = CleanupModule()
        body = " | title = Test | date = 2024"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("missing-url") is True

    def test_missing_publisher_for_cite_book(self):
        mod = CleanupModule()
        body = " | title = Book | date = 2024 | isbn = 9780306406157"
        result = mod.process(body, _make_context({"template_type": "cite book"}))
        assert result.changes.get("missing-publisher") is True

    def test_has_title_skips_missing_warning(self):
        mod = CleanupModule()
        body = " | title = Has Title | date = 2024"
        result = mod.process(body, _make_context())
        assert "missing-title" not in result.changes

    def test_citation_to_book_title_becomes_chapter(self):
        mod = CleanupModule()
        body = " | isbn = 9780306406157 | work = Test Work | title = Book Title | url = https://example.com"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.new_template_type == "cite book"
        assert result.rename_params.get("title") == "chapter"
        assert result.rename_params.get("work") == "title"
        assert result.rename_params.get("url") == "chapter-url"

    def test_citation_to_journal_with_place(self):
        mod = CleanupModule()
        body = " | journal = Test J | place = London"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.new_template_type == "cite journal"
        assert result.rename_params.get("place") == "location"

    def test_citation_to_web_with_place(self):
        mod = CleanupModule()
        body = " | work = My Site | place = Paris"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.new_template_type == "cite web"
        assert result.rename_params.get("work") == "website"
        assert result.rename_params.get("place") == "location"

    def test_citation_to_news_with_place(self):
        mod = CleanupModule()
        body = " | newspaper = The Times | place = London"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.new_template_type == "cite news"
        assert result.rename_params.get("place") == "location"

    def test_citation_to_magazine_with_place(self):
        mod = CleanupModule()
        body = " | magazine = The Atlantic | place = NY"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.new_template_type == "cite magazine"
        assert result.rename_params.get("place") == "location"

    def test_citation_to_thesis_with_place(self):
        mod = CleanupModule()
        body = " | degree = PhD | place = Boston"
        result = mod.process(body, _make_context({"template_type": "citation"}))
        assert result.new_template_type == "cite thesis"
        assert result.rename_params.get("place") == "location"

    def test_cite_web_with_newspaper_removed(self):
        mod = CleanupModule()
        body = " | newspaper = The Times | title = Test"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert "newspaper" not in result.text
        assert result.changes["periodical-conflict"] is True

    def test_number_extra_text_stripped(self):
        mod = CleanupModule()
        body = " | number = no. 42"
        result = mod.process(body, _make_context())
        assert "| number = 42" in result.text or "| number=42" in result.text
        assert result.changes["extra-text"] is True
