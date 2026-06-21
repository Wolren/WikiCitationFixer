from unittest.mock import patch

import requests_mock

from wikifix.config import ApiConfig, Mode
from wikifix.modules.ids import IdEnrichmentModule
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

    def test_qid_added_from_doi(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_qid1"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/qid_test"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/qid_test",
                json={"ids": {"wikidata": "https://www.wikidata.org/wiki/Q99999"}},
            )
            result = mod.process(
                body,
                _make_context({"doi": "10.1000/qid_test", "api": api}),
            )
            assert "|qid=Q99999" in result.text
            assert result.changes["qid"] is True

    def test_qid_already_present_skipped(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_qid2"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/has_qid | qid = Q111"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/has_qid",
                json={"ids": {"wikidata": "https://www.wikidata.org/wiki/Q222"}},
            )
            result = mod.process(
                body,
                _make_context({"doi": "10.1000/has_qid", "api": api}),
            )
            assert "qid = Q111" in result.text
            assert "Q222" not in result.text
            assert result.changes["qid"] is False

    def test_qid_not_wanted_skipped(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_qid3"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/xyz_not_wanted"
        result = mod.process(
            body,
            _make_context(
                {
                    "doi": "10.1000/xyz_not_wanted",
                    "api": api,
                    "ids_to_fetch": ["issn", "pmid"],
                }
            ),
        )
        assert "|qid=" not in result.text

    def test_qid_force_refresh_replaces(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_qid4"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/qid_force | qid = QOLD"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/qid_force",
                json={"ids": {"wikidata": "https://www.wikidata.org/wiki/QNEW"}},
            )
            result = mod.process(
                body,
                _make_context(
                    {
                        "doi": "10.1000/qid_force",
                        "api": api,
                        "mode": Mode.FORCE_REFRESH,
                    }
                ),
            )
            assert "|qid=QNEW" in result.text
            assert "QOLD" not in result.text
            assert result.changes["qid"] is True

    def test_no_api_early_return(self):
        mod = IdEnrichmentModule()
        body = " | doi = 10.1000/test"
        result = mod.process(body, {"template_type": "cite journal"})
        assert all(v is False for v in result.changes.values())

    def test_doi_access_added_when_oa(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_oa"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/oa_test"
        with patch.object(api, "doi_is_oa", return_value=True):
            result = mod.process(
                body, _make_context({"doi": "10.1000/oa_test", "api": api})
            )
            assert "|doi-access=free" in result.text
            assert result.changes["doi-access"] is True

    def test_issn_not_for_web_template(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_issn1"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/web"
        result = mod.process(
            body,
            _make_context(
                {"doi": "10.1000/web", "api": api, "template_type": "cite web"}
            ),
        )
        assert "issn" not in result.changes

    def test_issn_fetched_and_added(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_issn2"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/issn_test"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/issn_test",
                json={"message": {"ISSN": ["1234-5678"]}},
            )
            result = mod.process(
                body, _make_context({"doi": "10.1000/issn_test", "api": api})
            )
            assert "|issn=1234-5678" in result.text
            assert result.changes["issn"] is True

    def test_issn_force_refresh_strips_and_adds(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_issn3"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/issn_force | issn = 9999-9999"
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/issn_force",
                json={"message": {"ISSN": ["1234-5678"]}},
            )
            result = mod.process(
                body,
                _make_context(
                    {
                        "doi": "10.1000/issn_force",
                        "api": api,
                        "mode": Mode.FORCE_REFRESH,
                    }
                ),
            )
            assert "9999-9999" not in result.text
            assert "|issn=1234-5678" in result.text
            assert result.changes["issn"] is True

    def test_pmid_fetched_and_added(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_pmid1"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/pmid_test"
        with requests_mock.Mocker() as m:
            m.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=10.1000%2Fpmid_test%5BDOI%5D&retmode=json",
                json={"esearchresult": {"idlist": ["12345678"]}},
            )
            result = mod.process(
                body, _make_context({"doi": "10.1000/pmid_test", "api": api})
            )
            assert "|pmid=12345678" in result.text
            assert result.changes["pmid"] is True

    def test_pmid_already_present_extracted(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_pmid2"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/has_pmid | pmid = 87654321"
        with patch.object(api, "doi_to_pmid", return_value=None):
            result = mod.process(
                body, _make_context({"doi": "10.1000/has_pmid", "api": api})
            )
            assert "pmid = 87654321" in result.text
            assert result.changes["pmid"] is False

    def test_pmid_force_refresh_strips(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_pmid3"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/pmid_force | pmid = 11111111"
        with patch.object(api, "doi_to_pmid", return_value="22222222"):
            result = mod.process(
                body,
                _make_context(
                    {
                        "doi": "10.1000/pmid_force",
                        "api": api,
                        "mode": Mode.FORCE_REFRESH,
                    }
                ),
            )
            assert "11111111" not in result.text
            assert "|pmid=22222222" in result.text
            assert result.changes["pmid"] is True

    def test_pmc_fetched_after_pmid(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_pmc1"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/pmc_test | pmid = 55555555"
        with patch.object(api, "pmid_to_pmc", return_value="PMC666666"):
            result = mod.process(
                body, _make_context({"doi": "10.1000/pmc_test", "api": api})
            )
            assert "|pmc=PMC666666" in result.text
            assert result.changes["pmc"] is True

    def test_pmc_force_refresh_strips(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_pmc2"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/pmc_force | pmid = 77777777 | pmc = 111111"
        with (
            patch.object(api, "doi_to_pmid", return_value="77777777"),
            patch.object(api, "pmid_to_pmc", return_value="222222"),
        ):
            result = mod.process(
                body,
                _make_context(
                    {"doi": "10.1000/pmc_force", "api": api, "mode": Mode.FORCE_REFRESH}
                ),
            )
            assert "111111" not in result.text
            assert "|pmc=222222" in result.text
            assert result.changes["pmc"] is True

    def test_s2cid_fetched_and_added(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_s2cid1"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/s2cid_test"
        with patch.object(api, "doi_to_s2cid", return_value="S2CID12345"):
            result = mod.process(
                body, _make_context({"doi": "10.1000/s2cid_test", "api": api})
            )
            assert "|s2cid=S2CID12345" in result.text
            assert result.changes["s2cid"] is True

    def test_s2cid_force_refresh_strips(self, tmp_path):
        mod = IdEnrichmentModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "ids_s2cid2"))
        api = ApiClient(cfg)
        body = " | doi = 10.1000/s2cid_force | s2cid = OLD"
        with patch.object(api, "doi_to_s2cid", return_value="NEW"):
            result = mod.process(
                body,
                _make_context(
                    {
                        "doi": "10.1000/s2cid_force",
                        "api": api,
                        "mode": Mode.FORCE_REFRESH,
                    }
                ),
            )
            assert "OLD" not in result.text
            assert "|s2cid=NEW" in result.text
            assert result.changes["s2cid"] is True
