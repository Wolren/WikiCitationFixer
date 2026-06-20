import requests_mock

from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientDataCite:
    def test_doi_to_authors_datacite(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "dc1"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.datacite.org/dois/10.1000/dc_test",
                json={
                    "data": {
                        "attributes": {
                            "creators": [
                                {"familyName": "Smith", "givenName": "John"},
                                {"familyName": "Doe", "givenName": "Jane"},
                            ]
                        }
                    }
                },
            )
            authors = client.doi_to_authors_datacite("10.1000/dc_test")
            assert authors == [("Smith", "John"), ("Doe", "Jane")]

    def test_doi_to_authors_datacite_creator_name(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "dc2"))
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.datacite.org/dois/10.1000/dc_name",
                json={
                    "data": {
                        "attributes": {
                            "creators": [
                                {"name": "Brown, Sarah"},
                                {"name": "The Team"},
                            ]
                        }
                    }
                },
            )
            authors = client.doi_to_authors_datacite("10.1000/dc_name")
            assert authors == [("Brown", "Sarah"), ("The Team", "")]


class TestApiClientDataCite2:
    def test_doi_to_authors_datacite_exception(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "dc_exc"), datacite_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get("https://api.datacite.org/dois/10.1000/dc_exc", exc=Exception("fail"))
            assert client.doi_to_authors_datacite("10.1000/dc_exc") == []
