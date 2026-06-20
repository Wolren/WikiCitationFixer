from unittest.mock import patch

import pytest
import requests_mock

from wikifix.config import ApiConfig, Mode
from wikifix.modules.archive import ArchiveModule
from wikifix.services import ApiClient


def _make_context(overrides=None):
    ctx = {
        "template_type": "cite journal",
        "doi": None,
        "pmid": None,
        "title": "Test",
        "is_duplicate": False,
        "mode": Mode.INCREMENTAL,
        "api": ApiClient(ApiConfig(cache_dir="")),
        "author_style": "normal",
        "refresh_authors": False,
        "max_authors": 6,
        "ids_to_fetch": ["issn", "pmid", "pmc", "s2cid", "qid"],
        "force_archive_all": False,
        "create_archive": False,
        "strip_issn": False,
    }
    if overrides:
        ctx.update(overrides)
    return ctx


class TestArchiveModule:
    def test_no_url_no_change(self):
        mod = ArchiveModule()
        body = " | title = Test"
        result = mod.process(body, _make_context({"template_type": "cite journal"}))
        assert len(result.changes) == 0
        assert result.text == body

    def test_removes_orphan_archive_url(self):
        mod = ArchiveModule()
        body = " | archive-url = https://web.archive.org/web/20240101000000/https://example.com"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("archive-no-url") is True

    def test_deprecated_archive_detected(self):
        mod = ArchiveModule()
        body = " | archive-url = https://webcitation.org/abc123 | url = https://example.com"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("deprecated-archive") is True

    def test_archive_date_without_archive_url_removed(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch_date"))
        api = ApiClient(cfg)
        body = " | archive-date = 2024-01-01 | url = https://example.com"
        with patch.object(api, "check_wayback", return_value=None):
            result = mod.process(
                body, _make_context({"template_type": "cite web", "api": api})
            )
            assert result.changes.get("archive-date-no-url") is True
            assert "archive-date" not in result.text

    def test_url_status_bot_unknown_valid_with_url(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch_bot"))
        api = ApiClient(cfg)
        body = " | url-status = bot: unknown | url = https://example.com"
        with patch.object(api, "check_wayback", return_value=None):
            result = mod.process(
                body, _make_context({"template_type": "cite web", "api": api})
            )
            assert "url-status = bot: unknown" in result.text
            assert result.changes.get("orphan-url-status") is None

    def test_url_status_bot_unknown_no_url_no_archive_removed(self):
        mod = ArchiveModule()
        body = " | url-status = bot: unknown "
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("orphan-url-status") is True

    def test_url_status_non_bot_without_archive_url_removed(self):
        mod = ArchiveModule()
        body = " | url-status = dead"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("orphan-url-status") is True

    def test_wayback_timestamp_mismatch(self):
        mod = ArchiveModule()
        body = " | archive-url = https://web.archive.org/web/20240101000000/https://example.com | archive-date = 2023-01-01 | url = https://example.com"
        result = mod.process(body, _make_context({"template_type": "cite web"}))
        assert result.changes.get("archive-date-mismatch") is True

    def test_no_api_early_return_after_validation(self):
        mod = ArchiveModule()
        body = " | url = https://example.com"
        result = mod.process(body, {"template_type": "cite web"})
        assert "archive-url" not in result.text

    def test_not_web_type_skips_wayback(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch1"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with patch.object(
            api,
            "check_wayback",
            return_value=(
                "https://web.archive.org/web/20240101000000/example",
                "2024-01-01",
            ),
        ):
            result = mod.process(
                body, _make_context({"template_type": "cite journal", "api": api})
            )
            assert result.changes.get("archive") is None

    def test_no_result_from_wayback_skipped(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch2"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with patch.object(api, "check_wayback", return_value=None):
            result = mod.process(
                body, _make_context({"template_type": "cite web", "api": api})
            )
            assert result.changes.get("archive") is None

    def test_wayback_found_adds_archive(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch3"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with (
            patch.object(
                api,
                "check_wayback",
                return_value=(
                    "https://web.archive.org/web/20240101000000/example",
                    "2024-01-01",
                ),
            ),
            patch.object(api, "head_url", return_value=200),
        ):
            result = mod.process(
                body, _make_context({"template_type": "cite web", "api": api})
            )
            assert result.changes.get("archive") is True
            assert "archive-url = https://web.archive.org" in result.text
            assert "archive-date = 2024-01-01" in result.text
            assert "url-status = live" in result.text

    def test_wayback_found_with_existing_archive_incremental_skips(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch4"))
        api = ApiClient(cfg)
        body = " | url = https://example.com | archive-url = https://old.example"
        with patch.object(
            api,
            "check_wayback",
            return_value=(
                "https://web.archive.org/web/20240101000000/example",
                "2024-01-01",
            ),
        ):
            result = mod.process(
                body, _make_context({"template_type": "cite web", "api": api})
            )
            assert result.changes.get("archive") is None

    def test_force_refresh_replaces_archive(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch5"))
        api = ApiClient(cfg)
        body = " | url = https://example.com | archive-url = https://old.example | archive-date = 2020-01-01 | url-status = dead"
        with (
            patch.object(
                api,
                "check_wayback",
                return_value=(
                    "https://web.archive.org/web/20240101000000/example",
                    "2024-01-01",
                ),
            ),
            patch.object(api, "head_url", return_value=200),
        ):
            result = mod.process(
                body,
                _make_context(
                    {
                        "template_type": "cite web",
                        "api": api,
                        "mode": Mode.FORCE_REFRESH,
                    }
                ),
            )
            assert result.changes.get("archive") is True
            assert "old.example" not in result.text
            assert "archive-url = https://web.archive.org" in result.text

    def test_url_probe_dead_sets_status(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch6"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with (
            patch.object(
                api,
                "check_wayback",
                return_value=(
                    "https://web.archive.org/web/20240101000000/example",
                    "2024-01-01",
                ),
            ),
            patch.object(api, "head_url", return_value=404),
        ):
            result = mod.process(
                body, _make_context({"template_type": "cite web", "api": api})
            )
            assert "url-status = dead" in result.text

    def test_url_probe_exception_assumes_live(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch7"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with (
            patch.object(
                api,
                "check_wayback",
                return_value=(
                    "https://web.archive.org/web/20240101000000/example",
                    "2024-01-01",
                ),
            ),
            patch.object(api, "head_url", side_effect=Exception("timeout")),
        ):
            result = mod.process(
                body, _make_context({"template_type": "cite web", "api": api})
            )
            assert "url-status = live" in result.text

    def test_create_archive_success(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch8"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with (
            patch.object(
                api,
                "check_wayback",
                side_effect=[
                    None,
                    (
                        "https://web.archive.org/web/20240101000000/example",
                        "2024-01-01",
                    ),
                ],
            ),
            patch.object(api, "save_wayback", return_value=True),
            patch.object(api, "head_url", return_value=200),
        ):
            result = mod.process(
                body,
                _make_context(
                    {"template_type": "cite web", "api": api, "create_archive": True}
                ),
            )
            assert result.changes.get("archive") is True
            assert "archive-url = " in result.text

    def test_create_archive_save_failed(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch9"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with (
            patch.object(api, "check_wayback", return_value=None),
            patch.object(api, "save_wayback", return_value=False),
        ):
            result = mod.process(
                body,
                _make_context(
                    {"template_type": "cite web", "api": api, "create_archive": True}
                ),
            )
            assert result.changes.get("archive") is None

    def test_create_archive_save_ok_not_ready(self, tmp_path):
        mod = ArchiveModule()
        cfg = ApiConfig(cache_dir=str(tmp_path / "arch10"))
        api = ApiClient(cfg)
        body = " | url = https://example.com"
        with (
            patch.object(api, "check_wayback", side_effect=[None, None]),
            patch.object(api, "save_wayback", return_value=True),
        ):
            result = mod.process(
                body,
                _make_context(
                    {"template_type": "cite web", "api": api, "create_archive": True}
                ),
            )
            assert result.changes.get("archive") is None
