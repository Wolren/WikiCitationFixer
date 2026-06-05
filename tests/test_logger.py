import logging

import pytest

from wikifix.logger import get_logger, setup_logger


@pytest.fixture(autouse=True)
def _reset_logger():
    logger = logging.getLogger("wikifix")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)


class TestLogger:
    def test_setup_default_level(self):
        setup_logger(verbose=False, quiet=False)
        logger = get_logger()
        assert logger.level == logging.INFO

    def test_setup_verbose(self):
        setup_logger(verbose=True, quiet=False)
        logger = get_logger()
        assert logger.level == logging.DEBUG

    def test_setup_quiet(self):
        setup_logger(verbose=False, quiet=True)
        logger = get_logger()
        assert logger.level == logging.WARNING

    def test_get_logger_same_instance(self):
        setup_logger()
        l1 = get_logger()
        l2 = get_logger()
        assert l1 is l2
        assert l1.name == "wikifix"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("WIKIFIX_LOG_LEVEL", "ERROR")
        setup_logger(verbose=False, quiet=False)
        logger = get_logger()
        assert logger.level == logging.ERROR

    def test_env_override_bad_value(self, monkeypatch):
        monkeypatch.setenv("WIKIFIX_LOG_LEVEL", "BLAH")
        setup_logger(verbose=False, quiet=False)
        logger = get_logger()
        assert logger.level == logging.INFO

    def test_verbose_qiet_ordering(self):
        setup_logger(verbose=True, quiet=True)
        logger = get_logger()
        assert logger.level == logging.WARNING

    def test_verbose_format_includes_timestamp(self):
        setup_logger(verbose=True)
        logger = get_logger()
        handler = logger.handlers[0]
        fmt = handler.formatter
        assert "%(asctime)s" in fmt._fmt
        assert "%(levelname)" in fmt._fmt

    def test_default_format_no_timestamp(self):
        setup_logger(verbose=False, quiet=False)
        logger = get_logger()
        handler = logger.handlers[0]
        fmt = handler.formatter
        assert "%(message)s" in fmt._fmt
