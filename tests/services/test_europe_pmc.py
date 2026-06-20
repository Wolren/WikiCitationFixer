import requests_mock

from wikifix.cache import ResponseCache
from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientEuropePMC:
    def test_fetch_europepmc_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "epmc1"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "EPMC Title",
                                "journalTitle": "EPMC Journal",
                                "volume": "10",
                                "issue": "2",
                                "pageInfo": "100-110",
                                "firstPublicationDate": "2024-03-15",
                                "source": "MED",
                                "id": "12345678",
                            }
                        ]
                    }
                },
            )
            data = client.fetch_europepmc("10.1000/epmc_test")
            assert data is not None
            assert data["title"] == "EPMC Title"

    def test_fetch_europepmc_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "epmc2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            assert client.fetch_europepmc("10.1000/epmc_missing") is None

    def test_pmid_to_metadata_europepmc_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "epmc3"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "PMID Result",
                                "journalTitle": "PMID Journal",
                                "volume": "5",
                                "firstPublicationDate": "2023-01-01",
                                "source": "MED",
                                "id": "87654321",
                            }
                        ]
                    }
                },
            )
            data = client.pmid_to_metadata_europepmc("87654321")
            assert data is not None
            assert data["title"] == "PMID Result"

    def test_pmid_to_metadata_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "epmc4"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            assert client.pmid_to_metadata_europepmc("00000000") is None


class TestApiClientEuropePMC2:
    def test_fetch_europepmc_cached(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ep_c1"))
        client = ApiClient(cfg)
        key = ResponseCache.make_key("europepmc", "by_doi", "10.1000/ep_cached")
        client._cached_set(key, {"title": "Cached Title"})
        result = client.fetch_europepmc("10.1000/ep_cached")
        assert result == {"title": "Cached Title"}

    def test_pmid_to_metadata_europepmc_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ep_nf"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                json={"resultList": {"result": []}},
            )
            assert client.pmid_to_metadata_europepmc("00000000") is None

    def test_fetch_europepmc_exception(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ep_exc"), europepmc_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/api/search",
                exc=Exception("network error"),
            )
            assert client.fetch_europepmc("10.1000/ep_exc") is None
