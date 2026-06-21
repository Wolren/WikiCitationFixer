import pytest

from wikifix.config import ApiConfig, CitationStats, Mode, ProcessingResult


class TestMode:
    def test_incremental(self):
        assert Mode.INCREMENTAL.value == 1

    def test_force_refresh(self):
        assert Mode.FORCE_REFRESH.value == 2

    def test_enum_members(self):
        assert {m.name for m in Mode} == {"INCREMENTAL", "FORCE_REFRESH"}


class TestApiConfig:
    def test_defaults(self):
        cfg = ApiConfig()
        assert cfg.user_agent == "WikiCitationFixer/3.0"
        assert cfg.ncbi_delay == 0.34
        assert cfg.crossref_delay == 0.05
        assert cfg.cache_dir is None
        assert cfg.cache_ttl == 604800
        assert cfg.max_workers == 4
        assert cfg.crossref_email == ""
        assert cfg.ncbi_api_key == ""
        assert cfg.semantic_scholar_api_key == ""

    def test_frozen(self):
        cfg = ApiConfig()
        with pytest.raises(AttributeError):
            cfg.user_agent = "custom"

    def test_from_env_plain(self, monkeypatch):
        monkeypatch.delenv("CROSSREF_EMAIL", raising=False)
        monkeypatch.delenv("NCBI_API_KEY", raising=False)
        monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
        monkeypatch.delenv("WIKIFIX_CACHE_DIR", raising=False)
        cfg = ApiConfig.from_env()
        assert cfg.crossref_email == ""
        assert cfg.ncbi_api_key == ""
        assert cfg.user_agent == "WikiCitationFixer/3.0"
        assert cfg.cache_dir is None

    def test_from_env_with_keys(self, monkeypatch):
        monkeypatch.setenv("CROSSREF_EMAIL", "test@example.com")
        monkeypatch.setenv("NCBI_API_KEY", "ncbi_key_123")
        monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "ss_key_456")
        monkeypatch.setenv("WIKIFIX_CACHE_DIR", "/tmp/wikifix_cache")
        cfg = ApiConfig.from_env()
        assert cfg.crossref_email == "test@example.com"
        assert cfg.ncbi_api_key == "ncbi_key_123"
        assert cfg.semantic_scholar_api_key == "ss_key_456"
        assert "test@example.com" in cfg.user_agent
        assert cfg.ncbi_delay == 0.1
        assert cfg.semantic_scholar_delay == 0.1
        assert cfg.cache_dir == "/tmp/wikifix_cache"

    def test_from_env_warns_missing_path(self, caplog):
        ApiConfig.from_env("/nonexistent/path/.env")
        assert "env file not found" in caplog.text

    def test_from_env_dotenv_missing(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("CROSSREF_EMAIL=dotenv_test@test.com")
        monkeypatch.delenv("CROSSREF_EMAIL", raising=False)
        cfg = ApiConfig.from_env(str(env_file))
        assert cfg.crossref_email == "dotenv_test@test.com"

    def test_from_env_with_overrides(self):
        cfg = ApiConfig.from_env(cache_dir="/custom/cache", max_workers=8)
        assert cfg.cache_dir == "/custom/cache"
        assert cfg.max_workers == 8

    def test_from_env_with_env_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CROSSREF_EMAIL=from_file@example.com\nNCBI_API_KEY=file_key\n"
        )
        monkeypatch.delenv("CROSSREF_EMAIL", raising=False)
        monkeypatch.setenv("NCBI_API_KEY", "env_override")
        cfg = ApiConfig.from_env(str(env_file))
        assert cfg.crossref_email == "from_file@example.com"
        assert cfg.ncbi_api_key == "env_override"

    def test_cache_dir_none_default(self):
        cfg = ApiConfig()
        assert cfg.cache_dir is None

    def test_cache_dir_empty_disables_cache(self):
        cfg = ApiConfig(cache_dir="")
        assert cfg.cache_dir == ""


class TestProcessingResult:
    def test_no_changes(self):
        r = ProcessingResult(text="body", changes={})
        assert r.any_changed() is False

    def test_some_changes(self):
        r = ProcessingResult(text="body", changes={"spacing": True})
        assert r.any_changed() is True

    def test_new_template_type(self):
        r = ProcessingResult(text="body", changes={}, new_template_type="cite journal")
        assert r.new_template_type == "cite journal"

    def test_rename_params(self):
        r = ProcessingResult(text="body", changes={}, rename_params={"old": "new"})
        assert r.rename_params == {"old": "new"}

    def test_drop_params(self):
        r = ProcessingResult(text="body", changes={}, drop_params={"bad_param"})
        assert r.drop_params == {"bad_param"}


class TestCitationStats:
    def test_defaults(self):
        s = CitationStats()
        assert s.total == 0
        assert s.module_stats == {}

    def test_accumulation(self):
        s = CitationStats(total=5)
        s.module_stats["spacing"] = 3
        assert s.total == 5
        assert s.module_stats["spacing"] == 3
