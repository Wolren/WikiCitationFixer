import requests_mock

from wikifix.cache import ResponseCache
from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientCrossRef:
    def test_fetch_crossref_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_test"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/xyz123",
                json={"message": {"title": "Test", "author": []}},
            )
            result = client.fetch_crossref("10.1000/xyz123")
            assert result == {"title": "Test", "author": []}

    def test_fetch_crossref_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_test2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/missing",
                status_code=404,
            )
            assert client.fetch_crossref("10.1000/missing") is None

    def test_fetch_crossref_caches(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_test3"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/cached",
                json={"message": {"title": "First"}},
            )
            r1 = client.fetch_crossref("10.1000/cached")
            assert r1 == {"title": "First"}
        # Second call without mock should serve from cache
        r2 = client.fetch_crossref("10.1000/cached")
        assert r2 == {"title": "First"}

    def test_doi_to_issn(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_issn"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/issn_test",
                json={"message": {"ISSN": ["1234-5678"]}},
            )
            assert client.doi_to_issn("10.1000/issn_test") == "1234-5678"

    def test_doi_is_oa_true(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_oa"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/oa_test",
                json={
                    "message": {
                        "license": [{"URL": "http://creativecommons.org/by/4.0/"}]
                    }
                },
            )
            assert client.doi_is_oa("10.1000/oa_test") is True

    def test_doi_is_oa_false(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_oa2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/no_oa",
                json={"message": {"license": []}},
            )
            assert client.doi_is_oa("10.1000/no_oa") is False

    def test_doi_to_authors(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_auth"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/with_authors",
                json={"message": {"author": [{"family": "Smith", "given": "John A."}]}},
            )
            authors = client.doi_to_authors("10.1000/with_authors")
            assert authors == [("Smith", "John A.")]

    def test_doi_to_authors_no_authors(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_na"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/no_auth",
                json={"message": {}},
            )
            assert client.doi_to_authors("10.1000/no_auth") == []


class TestApiClientCrossRef2:
    def test_doi_to_issn_cached_hit(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_c1"))
        client = ApiClient(cfg)
        key = ResponseCache.make_key("crossref", "work", "10.1000/cached_issn")
        client._cached_set(key, {"ISSN": ["9999-8888"]})
        assert client.doi_to_issn("10.1000/cached_issn") == "9999-8888"

    def test_doi_is_oa_no_license(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_oa1"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works/10.1000/no_license",
                json={"message": {}},
            )
            assert client.doi_is_oa("10.1000/no_license") is False

    def test_fetch_crossref_not_ok(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cr_notok"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get("https://api.crossref.org/works/10.1000/bad", status_code=404)
            assert client.fetch_crossref("10.1000/bad") is None
