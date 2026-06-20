from wikifix.config import ApiConfig, Mode
from wikifix.modules.archive import ArchiveModule
from wikifix.modules.authors import AuthorModule
from wikifix.modules.cleanup import CleanupModule
from wikifix.modules.dates import DateModule
from wikifix.modules.dedup import DedupModule
from wikifix.modules.expand import ExpandModule
from wikifix.modules.ids import IdEnrichmentModule
from wikifix.modules.sort import SortModule
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
        "api": ApiClient(ApiConfig(cache_dir="")),
        "author_style": "normal",
        "refresh_authors": False,
        "max_authors": 6,
        "ids_to_fetch": ["issn", "pmid", "pmc", "s2cid"],
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
        assert " | last = " in result.text
        assert result.changes["spacing"] is True

    def test_already_spaced(self):
        mod = SpacingModule()
        body = " | last = Smith | first = John"
        result = mod.process(body, _make_context())
        assert result.changes["spacing"] is False


class TestDateModule:
    def test_normalizes_iso_date(self):
        mod = DateModule()
        body = " | date = 2024-03-15"
        result = mod.process(body, _make_context())
        assert "15 March" in result.text
        assert result.changes["date"] is True

    def test_normalizes_iso_year_month(self):
        mod = DateModule()
        body = " | date = 2024-03"
        result = mod.process(body, _make_context())
        assert "March 2024" in result.text
        assert result.changes["date"] is True

    def test_keeps_bare_year(self):
        mod = DateModule()
        body = " | date = 2024"
        result = mod.process(body, _make_context())
        assert result.changes["date"] is False

    def test_normalizes_month_name(self):
        mod = DateModule()
        body = " | date = March 15, 2024"
        result = mod.process(body, _make_context())
        assert "15 March" in result.text
        assert result.changes["date"] is True


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


class TestExpandModule:
    def test_doi_incremental_skip(self):
        mod = ExpandModule()
        body = " | doi = 10.1000/test | title = Existing | journal = Existing"
        result = mod.process(body, _make_context({"doi": "10.1000/test"}))
        assert result.text == body

    def test_empty_body(self):
        mod = ExpandModule()
        result = mod.process("", _make_context({"title": ""}))
        assert result.text == ""


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
        body = " | last1 = A | first1 = A1 | last2 = B | first2 = B1 | last3 = C | first3 = C1"  # noqa: E501
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


class TestIdEnrichmentModule:
    def test_strips_ids_in_force_mode(self):
        mod = IdEnrichmentModule()
        body = " | doi = 10.1000/test | pmid = 12345678"
        result = mod.process(
            body, _make_context({"doi": "10.1000/test", "mode": Mode.FORCE_REFRESH})
        )
        assert "pmid" not in result.text

    def test_no_doi_no_change(self):
        mod = IdEnrichmentModule()
        body = " | title = Test"
        result = mod.process(body, _make_context({"doi": None}))
        assert result.changes.get("issn") is False


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


class TestArchiveModule:
    def test_no_url_no_change(self):
        mod = ArchiveModule()
        body = " | title = Test"
        result = mod.process(body, _make_context({"template_type": "cite journal"}))
        assert len(result.changes) == 0
        assert result.text == body

    def test_removes_orphan_archive_url(self):
        mod = ArchiveModule()
        body = " | archive-url = https://web.archive.org/web/20240101000000/https://example.com"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("archive-no-url") is True

    def test_deprecated_archive_detected(self):
        mod = ArchiveModule()
        body = " | archive-url = https://webcitation.org/abc123 | url = https://example.com"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("deprecated-archive") is True
