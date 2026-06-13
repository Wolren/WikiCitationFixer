import requests_mock

from wikifix.config import ApiConfig, Mode
from wikifix.services import ApiClient


class TestApiClientStatic:
    def test_clean_doi(self):
        assert ApiClient.clean_doi("10.1000/xyz123") == "10.1000/xyz123"
        assert ApiClient.clean_doi("https://doi.org/10.1000/xyz") == "10.1000/xyz"
        assert ApiClient.clean_doi("https://dx.doi.org/10.1000/xyz") == "10.1000/xyz"
        assert ApiClient.clean_doi(" 10.1000/xyz ") == "10.1000/xyz"

    def test_clean_arxiv(self):
        assert ApiClient.clean_arxiv("2101.00001") == "2101.00001"
        assert ApiClient.clean_arxiv("https://arxiv.org/abs/2101.00001") == "2101.00001"

    def test_clean_isbn(self):
        assert ApiClient.clean_isbn("978-0-306-40615-7") == "9780306406157"
        assert ApiClient.clean_isbn("0-306-40615-2") == "0306406152"
        assert ApiClient.clean_isbn("ISBN: 9780306406157") == "9780306406157"

    def test_clean_url(self):
        assert ApiClient.clean_url("example.com") == "https://example.com"
        assert ApiClient.clean_url("https://example.com/") == "https://example.com"
        assert ApiClient.clean_url("http://example.com") == "http://example.com"


class TestApiClientRateLimit:
    def test_rate_limit_respects_delay(self):
        import time

        cfg = ApiConfig(ncbi_delay=0.05)
        client = ApiClient(cfg)
        client._last_call = time.time()
        t0 = time.time()
        client._rate_limit(0.05)
        t1 = time.time()
        assert t1 - t0 >= 0.04

    def test_rate_limit_no_delay_if_enough_time(self):
        import time

        cfg = ApiConfig(ncbi_delay=0.1)
        client = ApiClient(cfg)
        client._last_call = 0
        t0 = time.time()
        client._rate_limit(0.1)
        t1 = time.time()
        assert t1 - t0 < 0.2


class TestApiClientCache:
    def test_cached_get_returns_none_for_miss(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cache_test"))
        client = ApiClient(cfg)
        assert client._cached_get("missing_key") is None

    def test_cached_set_then_get(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cache_test2"))
        client = ApiClient(cfg)
        key = "test_key"
        client._cached_set(key, {"data": 42})
        assert client._cached_get(key) == {"data": 42}

    def test_get_skipped_in_force_mode(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cache_test3"))
        client = ApiClient(cfg, mode=Mode.FORCE_REFRESH)
        client._cached_set("some_key", "cached")
        assert client._cached_get("some_key") is None

    def test_no_cache_when_cache_dir_empty(self):
        cfg = ApiConfig(cache_dir="")
        client = ApiClient(cfg)
        client._cached_set("key", "val")
        assert client._cached_get("key") is None

    def test_clear_cache(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "cache_test4"))
        client = ApiClient(cfg)
        client._cached_set("k", "v")
        assert client._cached_get("k") == "v"
        client.clear_cache()
        assert client._cached_get("k") is None


class TestApiClientConcurrent:
    def test_concurrent_fetch_all_succeed(self):
        def fn_a():
            return "a_result"

        def fn_b():
            return "b_result"

        results = ApiClient.concurrent_fetch([("A", fn_a), ("B", fn_b)])
        assert results == {"A": "a_result", "B": "b_result"}

    def test_concurrent_fetch_one_fails(self):
        def fn_ok():
            return "ok"

        def fn_fail():
            raise ValueError("boom")

        results = ApiClient.concurrent_fetch([("ok", fn_ok), ("fail", fn_fail)])
        assert results["ok"] == "ok"
        assert results["fail"] is None

    def test_concurrent_fetch_empty(self):
        results = ApiClient.concurrent_fetch([])
        assert results == {}


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


class TestApiClientWayback:
    def test_check_wayback_found(self, tmp_path):
        import requests as req

        cfg = ApiConfig(cache_dir=str(tmp_path / "wb"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                req.Request(
                    "GET",
                    "https://archive.org/wayback/available",
                    params={"url": "https://example.com"},
                )
                .prepare()
                .url,
                json={
                    "archived_snapshots": {
                        "closest": {
                            "available": True,
                            "url": "https://web.archive.org/web/20240101000000/https://example.com",
                            "timestamp": "20240101000000",
                        }
                    }
                },
            )
            result = client.check_wayback("https://example.com")
            assert result is not None
            url, ts = result
            assert ts == "2024-01-01"

    def test_check_wayback_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "wb2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://archive.org/wayback/available",
                json={"archived_snapshots": {}},
            )
            assert client.check_wayback("https://example.com") is None

    def test_save_wayback_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "wb3"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get("https://web.archive.org/save/https://example.com", status_code=200)
            assert client.save_wayback("https://example.com") is True

    def test_save_wayback_rate_limited(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "wb4"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get("https://web.archive.org/save/https://example.com", status_code=429)
            assert client.save_wayback("https://example.com") is False
