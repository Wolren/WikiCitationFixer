import requests_mock

from wikifix.cache import ResponseCache
from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientSemanticScholar:
    def test_doi_to_s2cid_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ss"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.semanticscholar.org/v1/paper/10.1000/ss_test",
                json={"paperId": "abc123"},
            )
            s2cid = client.doi_to_s2cid("10.1000/ss_test")
            assert s2cid == "abc123"

    def test_doi_to_s2cid_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ss2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.semanticscholar.org/v1/paper/10.1000/missing",
                status_code=404,
            )
            assert client.doi_to_s2cid("10.1000/missing") is None


class TestApiClientSemanticScholar2:
    def test_doi_to_s2cid_cached(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ss_c1"))
        client = ApiClient(cfg)
        key = ResponseCache.make_key("semantic", "s2cid", "10.1000/s2_cached")
        client._cached_set(key, "S2CACHED")
        assert client.doi_to_s2cid("10.1000/s2_cached") == "S2CACHED"

    def test_doi_to_s2cid_exception(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ss_exc"), semantic_scholar_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.semanticscholar.org/v1/paper/10.1000/ss_exc",
                exc=Exception("fail"),
            )
            assert client.doi_to_s2cid("10.1000/ss_exc") is None
