import requests_mock

from wikifix.cache import ResponseCache
from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientOpenAlex:
    def test_doi_to_qid_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "oa_qid"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/qid_test",
                json={"ids": {"wikidata": "https://www.wikidata.org/wiki/Q12345"}},
            )
            qid = client.doi_to_qid("10.1000/qid_test")
            assert qid == "Q12345"

    def test_doi_to_qid_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "oa_qid2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/no_qid",
                json={"ids": {}},
            )
            assert client.doi_to_qid("10.1000/no_qid") is None

    def test_doi_to_qid_caches(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "oa_qid3"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/qid_cached",
                json={"ids": {"wikidata": "https://www.wikidata.org/wiki/Q999"}},
            )
            r1 = client.doi_to_qid("10.1000/qid_cached")
            assert r1 == "Q999"
        r2 = client.doi_to_qid("10.1000/qid_cached")
        assert r2 == "Q999"

    def test_doi_to_authors_openalex(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "oa_auth"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/oa_auth",
                json={
                    "authorships": [
                        {"author": {"display_name": "Smith, John A."}},
                        {"author": {"display_name": "Jane Doe"}},
                    ]
                },
            )
            authors = client.doi_to_authors_openalex("10.1000/oa_auth")
            assert authors == [("Smith", "John A."), ("Doe", "Jane")]

    def test_doi_to_authors_openalex_empty(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "oa_auth2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/oa_empty",
                json={"authorships": []},
            )
            assert client.doi_to_authors_openalex("10.1000/oa_empty") == []


class TestApiClientOpenAlex2:
    def test_doi_to_authors_openalex_single_token(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "oa_1t"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/single",
                json={"authorships": [{"author": {"display_name": "SoloName"}}]},
            )
            result = client.doi_to_authors_openalex("10.1000/single")
            assert result == [("SoloName", "")]

    def test_doi_to_authors_openalex_exception(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "oa_exc"), openalex_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/oa_exc",
                exc=Exception("fail"),
            )
            assert client.doi_to_authors_openalex("10.1000/oa_exc") == []


class TestApiClientQID2:
    def test_doi_to_qid_cached(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "qid_c1"))
        client = ApiClient(cfg)
        key = ResponseCache.make_key("openalex", "qid", "10.1000/qid_cached")
        client._cached_set(key, "Q99999")
        assert client.doi_to_qid("10.1000/qid_cached") == "Q99999"

    def test_doi_to_qid_not_ok(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "qid_nok"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.openalex.org/works/https://doi.org/10.1000/bad_qid",
                status_code=404,
            )
            assert client.doi_to_qid("10.1000/bad_qid") is None
