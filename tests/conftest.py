import pytest

from wikifix.config import ApiConfig, Mode


@pytest.fixture
def api_config():
    return ApiConfig()


@pytest.fixture
def force_mode():
    return Mode.FORCE_REFRESH


@pytest.fixture
def incremental_mode():
    return Mode.INCREMENTAL


@pytest.fixture
def sample_wikitext():
    return """<ref name="Smith2024">{{cite journal |last=Smith |first=John A. |title=Test Article |journal=Test Journal |volume=10 |issue=2 |pages=100-110 |date=2024 |doi=10.1000/xyz123}}</ref>"""


@pytest.fixture
def sample_body():
    return """ |last=Smith |first=John A. |title=Test Article |journal=Test Journal |volume=10 |issue=2 |pages=100-110 |date=2024 |doi=10.1000/xyz123"""


@pytest.fixture
def cleanup_cache(tmp_path):
    from wikifix.cache import ResponseCache

    c = ResponseCache(tmp_path / "test_cache")
    yield c
    c.clear()
