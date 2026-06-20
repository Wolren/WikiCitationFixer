import requests_mock

from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientOpenLibrary:
    def test_fetch_openlibrary_success(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ol1"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://openlibrary.org/api/books",
                json={
                    "ISBN:9780306406157": {
                        "title": "OL Book Title",
                        "authors": [{"name": "John Smith"}],
                        "publish_date": "2024",
                        "publishers": [{"name": "OL Press"}],
                    }
                },
            )
            data = client.fetch_openlibrary("9780306406157")
            assert data is not None
            assert data["title"] == "OL Book Title"
            assert data["publisher"] == "OL Press"

    def test_fetch_openlibrary_not_found(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ol2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://openlibrary.org/api/books",
                json={},
            )
            assert client.fetch_openlibrary("9780000000000") is None

    def test_fetch_openlibrary_retry_then_fail(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ol3"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://openlibrary.org/api/books",
                status_code=503,
            )
            assert client.fetch_openlibrary("9780000000001") is None
