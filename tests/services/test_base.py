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


class TestApiClientDiff:
    def test_is_valid_doi_valid(self):
        assert ApiClient.is_valid_doi("10.1000/xyz123") is True
        assert ApiClient.is_valid_doi("10.1038/nature12345") is True
        assert ApiClient.is_valid_doi("10.1234/5678") is True

    def test_is_valid_doi_invalid(self):
        assert ApiClient.is_valid_doi("") is False
        assert ApiClient.is_valid_doi("not-a-doi") is False
        assert ApiClient.is_valid_doi("http://doi.org/10.1000/xyz") is False

    def test_head_url_returns_status(self):
        cfg = ApiConfig(cache_dir="")
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.head("https://example.com", status_code=200)
            assert client.head_url("https://example.com") == 200

    def test_head_url_returns_none_on_error(self):
        cfg = ApiConfig(cache_dir="")
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.head("https://example.com", exc=ConnectionError)
            assert client.head_url("https://example.com") is None

    def test_doi_from_title_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "dt"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works",
                json={"message": {"items": [{"DOI": "10.1000/found_doi"}]}},
            )
            doi = client.doi_from_title("Found Article")
            assert doi == "10.1000/found_doi"

    def test_doi_from_title_no_results(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "dt2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works",
                json={"message": {"items": []}},
            )
            assert client.doi_from_title("Nonexistent") is None

    def test_doi_from_title_cached(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "dtc"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.crossref.org/works",
                json={"message": {"items": [{"DOI": "10.1000/cached_doi"}]}},
            )
            doi1 = client.doi_from_title("Cached")
            doi2 = client.doi_from_title("Cached")
            assert doi1 == doi2
            assert m.call_count == 1  # second hit should be cached


class TestApiClientRateLimit:
    def test_rate_limit_respects_delay(self):
        import time

        cfg = ApiConfig(ncbi_delay=0.05)
        client = ApiClient(cfg)
        client._last_calls["test"] = time.time()
        t0 = time.time()
        client._rate_limit("test", 0.05)
        t1 = time.time()
        assert t1 - t0 >= 0.04

    def test_rate_limit_no_delay_if_enough_time(self):
        import time

        cfg = ApiConfig(ncbi_delay=0.1)
        client = ApiClient(cfg)
        client._last_calls["test"] = 0.0
        t0 = time.time()
        client._rate_limit("test", 0.1)
        t1 = time.time()
        assert t1 - t0 < 0.2

    def test_rate_limit_per_api_independent(self):
        import time

        cfg = ApiConfig()
        client = ApiClient(cfg)
        # api_a "just called" — next call will be delayed
        client._last_calls["api_a"] = time.time()
        # api_b "called long ago" — immediately available
        client._last_calls["api_b"] = 0.0
        t0 = time.time()
        client._rate_limit("api_a", 0.05)
        t1 = time.time()
        t2 = time.time()
        client._rate_limit("api_b", 0.05)
        t3 = time.time()
        assert t1 - t0 >= 0.04  # api_a was delayed
        assert t3 - t2 < 0.02  # api_b NOT delayed by api_a's timestamp


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
