from wikifix.modules.sfn import convert_to_sfn


class TestConvertToSfn:
    def test_simple_conversion(self):
        text = (
            "Some text.<ref>{{cite book | last=Smith | first=John"
            " | title=Book | date=2024}}</ref>{{Reference page|page=42}}"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|Smith|2024|p=42}}" in result
        assert "{{cite book" in result
        assert "==Sources==" in result

    def test_page_range_uses_pp(self):
        text = (
            "Text.<ref>{{cite journal | last=Doe | first=J"
            " | title=Paper | date=2023}}</ref>{{Reference page|pages=100-110}}"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|Doe|2023|pp=100-110}}" in result

    def test_skipped_without_reference_page(self):
        text = (
            "Some text.<ref>{{cite book | last=Smith | first=John"
            " | title=Book | date=2024 | page=42}}</ref>"
        )
        result = convert_to_sfn(text)
        assert "{{sfn" not in result
        assert "{{cite book" in result
        assert "==Sources==" not in result

    def test_named_ref_converts_def_and_reuse(self):
        text = (
            '<ref name="foo">{{cite book | last=Brown | first=B'
            " | title=T | date=2022}}</ref>{{Reference page|page=5}}"
            ' Used again.<ref name="foo" />'
        )
        result = convert_to_sfn(text)
        # Definition becomes {{sfn}} with page
        assert "{{sfn|Brown|2022|p=5}}" in result
        # Reuse becomes {{sfn}} without page
        assert result.count("{{sfn|Brown|2022") == 2
        # Source section keeps the full citation (that's expected)
        assert "<ref" not in result  # all ref tags removed

    def test_reuse_with_own_reference_page(self):
        text = (
            '<ref name="bar">{{cite book | last=White | first=W'
            " | title=T | date=2021}}</ref>"
            ' Some text.<ref name="bar" />{{Reference page|page=10}}'
        )
        result = convert_to_sfn(text)
        # Reuse with Reference page becomes {{sfn}} with page
        assert "{{sfn|White|2021|p=10}}" in result
        # Definition without Reference page becomes {{sfn}} without page
        assert "{{sfn|White|2021}}" in result
        assert result.count("{{sfn|White|2021") == 2

    def test_reflist_not_touched(self):
        text = (
            "Body.<ref>{{cite book | last=A | first=B"
            " | title=T | date=2021}}</ref>{{Reference page|page=5}}"
            "\n\n==References==\n{{reflist}}"
        )
        result = convert_to_sfn(text)
        assert "{{reflist}}" in result
        assert "==Sources==" in result

    def test_no_author_skipped(self):
        text = "<ref>{{cite web | title=No Author | date=2020}}</ref>{{Reference page|page=42}}"  # noqa: E501
        result = convert_to_sfn(text)
        assert "{{cite web" in result
        assert "{{sfn" not in result

    def test_no_year_skipped(self):
        text = "<ref>{{cite book | last=A | first=B | title=T}}</ref>{{Reference page|page=42}}"  # noqa: E501
        result = convert_to_sfn(text)
        assert "{{cite book" in result
        assert "{{sfn" not in result

    def test_sources_deduplicated(self):
        text = (
            "<ref>{{cite book | last=Same | first=X"
            " | title=T1 | date=2020}}</ref>{{Reference page|page=5}}\n"
            "<ref>{{cite book | last=Same | first=Y"
            " | title=T2 | date=2020}}</ref>{{Reference page|page=10}}"
        )
        result = convert_to_sfn(text)
        assert result.count("{{sfn|Same|2020|p=") == 2
        assert result.count("==Sources==") == 1
        assert result.count("* {{cite book") == 1  # deduplicated
        assert "T1" in result  # first body kept

    def test_vancouver_vauthors(self):
        text = "<ref>{{citation | vauthors = Rappoport A | title=T | date=2024}}</ref>{{Reference page|page=42}}"  # noqa: E501
        result = convert_to_sfn(text)
        assert "{{sfn|Rappoport|2024|p=42}}" in result

    def test_multi_author_up_to_four(self):
        text = (
            "<ref>{{cite book | last1=A | first1=1"
            " | last2=B | first2=2 | last3=C | first3=3"
            " | title=T | date=2020}}</ref>{{Reference page|page=1}}"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|A|B|C|2020" in result

    def test_duplicate_author_year_converted(self):
        """Cite without Reference page but same author+year as converted cite."""
        text = (
            "<ref>{{cite book | last=Z | first=Z"
            " | title=T1 | date=2019}}</ref>{{Reference page|page=5}}\n"
            "<ref>{{cite book | last=Z | first=Z"
            " | title=T2 | date=2019}}</ref>"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|Z|2019|p=5}}" in result
        assert "{{sfn|Z|2019}}" in result  # duplicate without page
        assert "<ref" not in result  # all ref tags removed

    def test_no_change_for_inline_without_ref(self):
        text = "{{cite book | last=A | title=T}}"
        result = convert_to_sfn(text)
        assert "{{sfn" not in result
        assert "==Sources==" not in result

    def test_nested_template(self):
        text = (
            '<ref name="Bricker2024">{{cite thesis'
            " | last = Bricker | first = Nat L."
            " | title = Mental health"
            " | date = May 2024"
            " | degree = PhD | publisher = Palo Alto University"
            " | url = https://www.proquest.com/docview/3108481641"
            " | isbn = 979-8-3844-3281-4"
            " | id = {{ProQuest | 3108481641}}"
            " | archive-url = http://web.archive.org/web/20241001210926/https://www.proquest.com/docview/3108481641"
            " | archive-date = 2024-10-01"
            "}}</ref>{{Reference page|page=174}}"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|Bricker|2024|p=174}}" in result
        assert "{{cite thesis" in result  # in sources

    def test_reference_page_with_single_p(self):
        text = (
            "Text.<ref>{{cite journal | last=Doe | first=J"
            " | title=Paper | date=2023}}</ref>{{Reference page|p=42}}"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|Doe|2023|p=42}}" in result

    def test_reference_page_with_short_pp(self):
        text = (
            "Text.<ref>{{cite journal | last=Doe | first=J"
            " | title=Paper | date=2023}}</ref>{{Reference page|pp=100-110}}"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|Doe|2023|pp=100-110}}" in result

    def test_multi_word_surname(self):
        text = (
            "Text.<ref>{{cite book | last = De Groot | first = J. J. M."
            " | title = The Religious System of China"
            " | date = 1901"
            " | publisher = Brill"
            " | page = 171"
            " | url = https://archive.org/details/religioussystemo0002jjmd/page/n7/mode/2up"
            "}}</ref>{{Reference page|pages=164, 171}}"
        )
        result = convert_to_sfn(text)
        assert "{{sfn|De Groot|1901" in result

    def test_sources_inserted_before_references(self):
        text = (
            "Body text.<ref>{{cite book | last=A | first=B"
            " | title=T | date=2020}}</ref>{{Reference page|page=10}}"
            "\n\n==References==\n{{reflist}}"
        )
        result = convert_to_sfn(text)
        assert "==Sources==\n* {{cite book" in result
        ref_pos = result.find("==References==")
        src_pos = result.find("==Sources==")
        assert src_pos < ref_pos
