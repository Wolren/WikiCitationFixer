import requests_mock

from wikifix.cache import ResponseCache
from wikifix.config import ApiConfig
from wikifix.services import ApiClient


class TestApiClientArXiv:
    def test_fetch_arxiv_success_with_doi(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "arxiv1"))
        client = ApiClient(cfg)
        xml_body = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2101.00001</id>
    <title>Test Article Title</title>
    <summary>An abstract here.</summary>
    <published>2021-01-01T00:00:00Z</published>
    <author>
      <name>John A. Smith</name>
    </author>
    <arxiv:doi>10.1000/arxiv_doi</arxiv:doi>
  </entry>
</feed>"""
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=2101.00001",
                text=xml_body,
            )
            data = client.fetch_arxiv("2101.00001")
            assert data is not None
            assert data["title"] == "Test Article Title"
            assert data["doi"] == "10.1000/arxiv_doi"
            assert data["date"] == "2021-01-01"

    def test_fetch_arxiv_no_doi(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "arxiv2"))
        client = ApiClient(cfg)
        xml_body = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2101.00002</id>
    <title>No DOI Here</title>
    <summary>Abstract</summary>
    <published>2021-02-01T00:00:00Z</published>
    <author>
      <name>Jane Doe</name>
    </author>
  </entry>
</feed>"""
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=2101.00002",
                text=xml_body,
            )
            data = client.fetch_arxiv("2101.00002")
            assert data is not None
            assert data["doi"] is None

    def test_fetch_arxiv_empty_result(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "arxiv3"))
        client = ApiClient(cfg)
        xml_body = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=9999.99999",
                text=xml_body,
            )
            data = client.fetch_arxiv("9999.99999")
            assert data is None

    def test_fetch_arxiv_caches(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "arxiv4"))
        client = ApiClient(cfg)
        xml_body = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <title>Cached Arxiv</title>
    <summary>Abs</summary>
    <published>2021-03-01T00:00:00Z</published>
    <arxiv:doi>10.1000/cached_arxiv</arxiv:doi>
  </entry>
</feed>"""
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=2101.00003",
                text=xml_body,
            )
            r1 = client.fetch_arxiv("2101.00003")
            assert r1 is not None
        r2 = client.fetch_arxiv("2101.00003")
        assert r2 is not None


class TestApiClientArXiv2:
    def test_fetch_arxiv_cached(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ar_c1"))
        client = ApiClient(cfg)
        key = ResponseCache.make_key("arxiv", "meta", "2101.00001")
        client._cached_set(key, {"title": "Cached arXiv"})
        result = client.fetch_arxiv("2101.00001")
        assert result == {"title": "Cached arXiv"}

    def test_fetch_arxiv_exception(self, tmp_path):
        cfg = ApiConfig(cache_dir=str(tmp_path / "ar_exc"), arxiv_delay=0)
        client = ApiClient(cfg)
        with requests_mock.Mocker() as m:
            m.get(
                "https://export.arxiv.org/api/query?id_list=2101.99999",
                exc=Exception("timeout"),
            )
            assert client.fetch_arxiv("2101.99999") is None
