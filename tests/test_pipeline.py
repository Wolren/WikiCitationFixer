from unittest.mock import patch

from wikifix.config import Mode
from wikifix.modules.cleanup import CleanupModule
from wikifix.modules.dates import DateModule
from wikifix.modules.spacing import SpacingModule
from wikifix.pipeline import CitationPipeline


class TestCitationRegex:
    def test_finds_simple_citation(self):
        text = "Some text {{cite journal |title=Test}} more text"
        matches = list(CitationPipeline.CITATION_RE.finditer(text))
        assert len(matches) == 1
        assert "title=Test" in matches[0].group(1)

    def test_finds_nested_braces(self):
        text = "{{cite web |title={{Test}} }}"
        matches = list(CitationPipeline.CITATION_RE.finditer(text))
        assert len(matches) == 1

    def test_finds_citation_template(self):
        text = "{{citation |title=Test}}"
        matches = list(CitationPipeline.CITATION_RE.finditer(text))
        assert len(matches) == 1
        assert "title=Test" in matches[0].group(1)

    def test_multiple_citations(self):
        text = "{{cite journal |a=1}}{{cite journal |b=2}}"
        matches = list(CitationPipeline.CITATION_RE.finditer(text))
        assert len(matches) == 2

    def test_no_citations(self):
        text = "Just some text"
        matches = list(CitationPipeline.CITATION_RE.finditer(text))
        assert len(matches) == 0

    def test_non_citation_no_match(self):
        text = "{{not a cite template}}"
        matches = list(CitationPipeline.CITATION_RE.finditer(text))
        assert len(matches) == 0


class TestPipelineHelpers:
    def test_first_word_normal(self):
        assert CitationPipeline._first_word("The Quick Brown Fox") == "Quick"

    def test_first_word_skips_stopwords(self):
        assert CitationPipeline._first_word("a an the The Quick Fox") == "Quick"

    def test_first_word_all_stopwords(self):
        assert CitationPipeline._first_word("a an the") is None

    def test_first_word_strips_wikilinks(self):
        assert CitationPipeline._first_word("[[The Quick]] Fox") == "Quick"

    def test_extract_title(self):
        pipeline = CitationPipeline(modules=[])
        assert (
            pipeline._extract_title(" | title = Test Article | last = Smith")
            == "Test Article"
        )
        assert pipeline._extract_title(" | title = ") == ""
        assert pipeline._extract_title("") == "(no title)"

    def test_extract_doi(self):
        pipeline = CitationPipeline(modules=[])
        assert pipeline._extract_doi(" | doi = 10.1000/xyz123") == "10.1000/xyz123"
        assert pipeline._extract_doi(" | doi = ") == ""
        assert pipeline._extract_doi("") is None

    def test_extract_pmid(self):
        pipeline = CitationPipeline(modules=[])
        val = pipeline._extract_pmid(" | pmid = 12345678")
        assert val == "12345678"
        assert pipeline._extract_pmid(" | pmid = ") is None


class TestPipelineDetectType:
    def test_detect_journal(self):
        pipeline = CitationPipeline(modules=[])
        assert pipeline._detect_type("{{cite journal ...}}") == "cite journal"
        assert pipeline._detect_type("{{Cite journal ...}}") == "cite journal"

    def test_detect_web(self):
        pipeline = CitationPipeline(modules=[])
        assert pipeline._detect_type("{{cite web ...}}") == "cite web"

    def test_detect_citation(self):
        pipeline = CitationPipeline(modules=[])
        assert pipeline._detect_type("{{citation ...}}") == "citation"


class TestPipelineApplyRenames:
    def test_simple_rename(self):
        body = " | old_param = value"
        result = CitationPipeline._apply_renames(body, {"old_param": "new_param"})
        assert "| new_param = value" in result
        assert "old_param" not in result

    def test_rename_swap_values(self):
        body = " | a = 1 | b = 2"
        result = CitationPipeline._apply_renames(body, {"a": "b"})
        assert "a" not in result.split("|")[0]
        assert "b = 1" in result or "b = 2" in result

    def test_no_renames(self):
        body = " | title = Test"
        result = CitationPipeline._apply_renames(body, {})
        assert result == body

    def test_rename_old_equals_new_skipped(self):
        body = " | title = Test"
        result = CitationPipeline._apply_renames(body, {"title": "title"})
        assert "title" in result

    def test_rename_no_match_skipped(self):
        body = " | title = Test"
        result = CitationPipeline._apply_renames(body, {"nonexistent": "newname"})
        assert result == body

    def test_rename_with_both_params_swap(self):
        body = " | a = 1 | b = 2"
        result = CitationPipeline._apply_renames(body, {"a": "b"})
        assert "b = 1" in result


class TestPipelineApplyDrops:
    def test_drop_parameter(self):
        body = " | title = Test | bad_param = value"
        result = CitationPipeline._apply_drops(body, {"bad_param"})
        assert "bad_param" not in result

    def test_drop_multiple(self):
        body = " | a = 1 | b = 2 | c = 3"
        result = CitationPipeline._apply_drops(body, {"a", "c"})
        assert "a" not in result
        assert "c" not in result
        assert "b = 2" in result

    def test_no_drops(self):
        body = " | title = Test"
        result = CitationPipeline._apply_drops(body, set())
        assert result == body


class TestPipelineRefNames:
    def _make_pipeline(self, **kwargs):
        return CitationPipeline(
            modules=[],
            ref_names=True,
            **kwargs,
        )

    def test_adds_name_to_no_name_ref(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |last=Smith |year=2024 |title=Test}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |year=2024 |title=Test",
            "cite journal",
            set(),
            {},
        )
        assert 'name="Smith2024"' in result

    def test_upgrades_bare_surname_name(self):
        pipeline = self._make_pipeline()
        text = '<ref name="Smith">{{cite journal |last=Smith |year=2024 |title=Test}}</ref>'  # noqa: E501
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |year=2024 |title=Test",
            "cite journal",
            set(),
            {},
        )
        assert 'name="Smith2024"' in result

    def test_skips_meaningful_name(self):
        pipeline = self._make_pipeline()
        text = '<ref name="Jones2023">{{cite journal |last=Smith |year=2024 |title=Test}}</ref>'  # noqa: E501
        renames = {}
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |year=2024 |title=Test",
            "cite journal",
            set(),
            renames,
        )
        assert result == text
        assert renames == {}

    def test_renames_auto_generated(self):
        pipeline = self._make_pipeline()
        text = (
            '<ref name=":0">{{cite journal |last=Smith |year=2024 |title=Test}}</ref>'
        )
        renames = {}
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |year=2024 |title=Test",
            "cite journal",
            set(),
            renames,
        )
        assert 'name="Smith2024"' in result

    def test_falls_back_to_website_domain(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite web |url=https://www.example.com/article |title=My Page}}</ref>"  # noqa: E501
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |url=https://www.example.com/article |title=My Page",
            "cite web",
            set(),
            {},
        )
        assert 'name="Example"' in result

    def test_avoids_duplicate_names(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |last=Smith |year=2024 |title=Test}}</ref>"
        used = {"Smith2024"}
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |year=2024 |title=Test",
            "cite journal",
            used,
            {},
        )
        assert 'name="Smith2024-2"' in result

    def test_prepends_ref_for_numeric_names(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |last=123 |year=2024 |title=Test}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=123 |year=2024 |title=Test",
            "cite journal",
            set(),
            {},
        )
        assert 'name="ref-1232024"' in result

    def test_no_ref_tag_no_change(self):
        pipeline = self._make_pipeline()
        text = "Just text {{cite journal |last=Smith |year=2024 |title=Test}}"
        result = pipeline._add_ref_name(
            text, 10, " |last=Smith |year=2024 |title=Test", "cite journal", set(), {}
        )
        assert result == text

    def test_name_without_year(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |last=Smith |title=Test}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |title=Test",
            "cite journal",
            set(),
            {},
        )
        assert 'name="Smith"' in result

    def test_web_falls_back_to_work(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite web |work=Example Site |title=Test}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |work=Example Site |title=Test",
            "cite web",
            set(),
            {},
        )
        assert 'name="Example"' in result

    def test_web_falls_back_to_website(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite web |website=My Site |title=Test}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |website=My Site |title=Test",
            "cite web",
            set(),
            {},
        )
        assert 'name="My"' in result

    def test_web_falls_back_to_publisher(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite web |publisher=Acme Corp |title=Test}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |publisher=Acme Corp |title=Test",
            "cite web",
            set(),
            {},
        )
        assert 'name="Acme"' in result

    def test_web_falls_back_to_title(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite web |title=The Article}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |title=The Article",
            "cite web",
            set(),
            {},
        )
        assert 'name="Article"' in result

    def test_web_no_url_no_work_no_title_returns_unchanged(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite web |other=foo}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |other=foo",
            "cite web",
            set(),
            {},
        )
        assert result == text

    def test_non_web_falls_back_to_title(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |title=My Article}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |title=My Article",
            "cite journal",
            set(),
            {},
        )
        assert 'name="My"' in result

    def test_non_web_no_title_returns_unchanged(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |other=foo}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |other=foo",
            "cite journal",
            set(),
            {},
        )
        assert result == text

    def test_vauthors_fallback(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |vauthors=Jones A}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |vauthors=Jones A",
            "cite journal",
            set(),
            {},
        )
        assert 'name="Jones"' in result

    def test_multiple_duplicate_suffix(self):
        pipeline = self._make_pipeline()
        text = "<ref>{{cite journal |last=Smith |year=2024 |title=Test}}</ref>"
        used = {"Smith2024", "Smith2024-2"}
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |year=2024 |title=Test",
            "cite journal",
            used,
            {},
        )
        assert 'name="Smith2024-3"' in result

    def test_renames_global_single_quote(self):
        pipeline = self._make_pipeline()
        text = "<ref name='Smith'>{{cite journal |last=Smith |year=2024 |title=Test}}</ref>"
        result = pipeline._add_ref_name(
            text,
            text.index("{{cite"),
            " |last=Smith |year=2024 |title=Test",
            "cite journal",
            set(),
            {},
        )
        assert 'name="Smith2024"' in result


class TestPipelineProcessFile:
    def test_empty_input_creates_empty_output(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("", encoding="utf-8")
        pipeline = CitationPipeline(modules=[])
        pipeline.process_file(inp, out)
        assert out.read_text(encoding="utf-8") == ""

    def test_no_citations_preserves_text(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("Hello world", encoding="utf-8")
        pipeline = CitationPipeline(modules=[])
        pipeline.process_file(inp, out)
        assert out.read_text(encoding="utf-8") == "Hello world"

    def test_spacing_module_applied(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |last=Smith|title=Test|doi=10.1000/xyz}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[SpacingModule()])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "| title = " in result

    def test_date_module_normalizes(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |date=2024-03-15}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[DateModule()])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "March" in result

    def test_multiple_citations_preserved(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |a=1}}{{cite journal |b=2}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "a=1" in result
        assert "b=2" in result

    def test_ref_names_generated_in_process_file(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "<ref>{{cite journal |last=Smith |year=2024 |title=Test}}</ref>",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[], ref_names=True)
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert 'name="Smith2024"' in result

    def test_force_mode_passed_to_modules(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |doi=10.1000/test}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[], mode=Mode.FORCE_REFRESH)
        pipeline.process_file(inp, out)
        assert pipeline.mode == Mode.FORCE_REFRESH

    def test_skip_processing_on_error(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |title=Test}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[])
        pipeline.process_file(inp, out)
        assert out.read_text(encoding="utf-8") == "{{cite journal |title=Test}}"

    def test_ref_name_avoids_collisions_in_process_file(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "<ref>{{cite journal |last=Smith |year=2024 |title=A}}</ref> "
            "<ref>{{cite journal |last=Smith |year=2024 |title=B}}</ref>",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[], ref_names=True)
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert 'name="Smith2024"' in result
        assert 'name="Smith2024-2"' in result


class TestPipelineSequence:
    def test_full_pipeline_with_spacing_and_dates(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |last=Smith|title=Test|date=2024-03-15}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[SpacingModule(), DateModule()])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "| last = Smith" in result
        assert "15 March" in result

    def test_mixed_citation_types(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |date=2024-03-15}}{{cite web |date=2024-04-20}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[DateModule()])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "March" in result
        assert "April" in result

    def test_cleanup_module_converts_citation_to_book(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{citation |isbn=9780306406157 |title=My Book}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[CleanupModule()])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "cite book" in result

    def test_cleanup_module_converts_citation_to_journal(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{citation |journal=Some Journal |title=Article}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[CleanupModule()])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "cite journal" in result

    def test_strip_issn_removes_issn_when_doi_present(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |doi=10.1000/test |issn=1234-5678 |title=Test}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[], strip_issn=True)
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "issn" not in result
        assert "doi" in result

    def test_global_ref_renames_single_quote(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "<ref name='old_name'>{{cite journal |last=Smith |year=2024 |title=Test}}</ref>",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[], ref_names=True)
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert 'name="Smith2024"' in result
        assert "old_name" not in result

    def test_global_ref_renames_bare_surname(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            '<ref name="Smith">{{cite journal |last=Smith |year=2024 |title=Test}}</ref>',
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[], ref_names=True)
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert 'name="Smith2024"' in result

    def test_cleanup_module_triggers_renames(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{citation |isbn=9780306406157 |work=Pub |title=My Book}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[CleanupModule()])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "cite book" in result

    def test_ref_name_no_author_no_year(self, tmp_path):
        pipeline = CitationPipeline(modules=[], ref_names=True)
        text = "{{citation |title=Test}}"
        result = pipeline._add_ref_name(text, 0, " |title=Test", "citation", set(), {})
        assert result == text

    def test_canonical_type_fallthrough(self):
        pipeline = CitationPipeline(modules=[])
        assert pipeline._canonical_type("citation") == "citation"

    def test_pmid_duplicate_detection(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "{{cite journal |pmid=12345678 |title=First}}{{cite journal |pmid=12345678 |title=Second}}",
            encoding="utf-8",
        )
        pipeline = CitationPipeline(modules=[])
        pipeline.process_file(inp, out)
        result = out.read_text(encoding="utf-8")
        assert "pmid=12345678" in result

    def test_ref_name_non_web_no_title(self):
        pipeline = CitationPipeline(modules=[], ref_names=True)
        text = "<ref>{{cite journal |title=}}</ref>"
        result = pipeline._add_ref_name(
            text, text.index("{{cite"), " |title=", "cite journal", set(), {}
        )
        assert result == text

    def test_ref_name_non_web_all_stopwords_in_title(self):
        pipeline = CitationPipeline(modules=[], ref_names=True)
        text = "<ref>{{cite journal |title=The A An}}</ref>"
        result = pipeline._add_ref_name(
            text, text.index("{{cite"), " |title=The A An", "cite journal", set(), {}
        )
        assert result == text

    def test_ref_name_no_ref_tag(self):
        pipeline = CitationPipeline(modules=[], ref_names=True)
        text = "no ref tag here"
        result = pipeline._add_ref_name(
            text, 0, " |last=Smith |year=2024", "cite journal", set(), {}
        )
        assert result == text
