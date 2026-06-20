import requests as req
import requests_mock

from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientWayback:
    def test_check_wayback_found(self, tmp_path):
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


class TestApiClientWayback2:
    def test_save_wayback_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "wb_s1"), wayback_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get("https://web.archive.org/save/https://example.com", status_code=200)
            assert client.save_wayback("https://example.com") is True

    def test_save_wayback_rate_limited(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "wb_rl"), wayback_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get("https://web.archive.org/save/https://example.com", status_code=429)
            assert client.save_wayback("https://example.com") is False

    def test_save_wayback_exception(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "wb_exc"), wayback_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://web.archive.org/save/https://example.com",
                exc=Exception("fail"),
            )
            assert client.save_wayback("https://example.com") is False
