import requests_mock

from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientNCBI:
    def test_doi_to_pmid_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ncbi"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                json={"esearchresult": {"idlist": ["12345678"]}},
            )
            pmid = client.doi_to_pmid("10.1000/pmid_test")
            assert pmid == "12345678"

    def test_doi_to_pmid_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ncbi2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                json={"esearchresult": {"idlist": []}},
            )
            assert client.doi_to_pmid("10.1000/no_pmid") is None

    def test_pmid_to_pmc_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ncbi3"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                json={"records": [{"pmcid": "PMC1234567"}]},
            )
            pmc = client.pmid_to_pmc("12345678")
            assert pmc == "1234567"

    def test_doi_to_pmid_with_api_key(self, tmp_path):
        cfg = ApiConfig(
            cache_dir=str(tmp_path / "ncbi_key"),
            ncbi_api_key="testkey123",
            ncbi_delay=0.01,
        )
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                json={"esearchresult": {"idlist": ["99999999"]}},
            )
            pmid = client.doi_to_pmid("10.1000/pmid_key_test")
            assert pmid == "99999999"

    def test_pmid_to_pmc_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ncbi4"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                json={"records": [{"pmcid": ""}]},
            )
            assert client.pmid_to_pmc("00000000") is None


class TestApiClientAuthorsPubmed:
    def test_doi_to_authors_pubmed_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ap1"), ncbi_delay=0.01)
        client = ApiClient(cfg)
        doi = "10.1000/pubmed_auth"
        pmid = "55555555"
        with requests_mock.Mocker() as m:
            m.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                json={"esearchresult": {"idlist": [pmid]}},
            )
            m.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                json={
                    "result": {
                        pmid: {"authors": [{"name": "Smith John"}, {"name": "Doe"}]}
                    }
                },
            )
            result = client.doi_to_authors_pubmed(doi)
            assert result == [("Smith", "John"), ("Doe", "")]

    def test_doi_to_authors_pubmed_no_pmid(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ap2"), ncbi_delay=0.01)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                json={"esearchresult": {"idlist": []}},
            )
            assert client.doi_to_authors_pubmed("10.1000/no_pmid") == []
