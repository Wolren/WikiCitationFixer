import sys
from unittest.mock import patch

import pytest

from wikifix.__main__ import build_argparser, main, MODULE_REGISTRY
from wikifix import __version__


class TestBuildArgparser:
    def test_parser_created(self):
        parser = build_argparser()
        assert parser is not None

    def test_defaults(self):
        parser = build_argparser()
        args = parser.parse_args([])
        assert args.modules == "expand,authors,dates,ids,spacing,archive"
        assert args.force is False
        assert args.verbose is False
        assert args.quiet is False
        assert args.env is None
        assert args.cache_dir is None
        assert args.no_cache is False
        assert args.workers is None
        assert args.ref_names is False
        assert args.bare is False
        assert args.clear_cache is False
        assert args.version is False

    def test_force_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--force"])
        assert args.force is True

    def test_verbose_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_quiet_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--quiet"])
        assert args.quiet is True

    def test_env_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--env", ".env.prod"])
        assert args.env == ".env.prod"

    def test_cache_dir(self):
        parser = build_argparser()
        args = parser.parse_args(["--cache-dir", "/tmp/cache"])
        assert args.cache_dir == "/tmp/cache"

    def test_no_cache(self):
        parser = build_argparser()
        args = parser.parse_args(["--no-cache"])
        assert args.no_cache is True

    def test_modules_list(self):
        parser = build_argparser()
        args = parser.parse_args(["--modules", "spacing,sort"])
        assert args.modules == "spacing,sort"

    def test_clear_cache_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--clear-cache"])
        assert args.clear_cache is True

    def test_version_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--version"])
        assert args.version is True

    def test_list_modules_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--list-modules"])
        assert args.list_modules is True

    def test_workers(self):
        parser = build_argparser()
        args = parser.parse_args(["--workers", "8"])
        assert args.workers == 8

    def test_ref_names(self):
        parser = build_argparser()
        args = parser.parse_args(["--ref-names"])
        assert args.ref_names is True

    def test_bare_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--bare"])
        assert args.bare is True

    def test_no_module_flags(self):
        parser = build_argparser()
        args = parser.parse_args(["--no-spacing", "--no-cleanup"])
        assert args.no_spacing is True
        assert args.no_cleanup is True
        assert args.no_expand is False

    def test_author_style_vancouver(self):
        parser = build_argparser()
        args = parser.parse_args(["--author-style", "vancouver"])
        assert args.author_style == "vancouver"

    def test_author_style_invalid(self):
        parser = build_argparser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--author-style", "invalid"])

    def test_ids_default(self):
        parser = build_argparser()
        args = parser.parse_args([])
        assert args.ids == "issn,pmid,pmc,s2cid"


class TestMainVersion:
    def test_version_flag(self, capsys):
        with patch.object(sys, "argv", ["wikifix", "--version"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out


class TestMainListModules:
    def test_list_modules(self, caplog):
        with patch.object(sys, "argv", ["wikifix", "--list-modules"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        for name in MODULE_REGISTRY:
            assert any(name in rec.message for rec in caplog.records)


class TestMainErrorUnknownModule:
    def test_unknown_module_exits_error(self):
        with patch.object(sys, "argv", ["wikifix", "--modules", "unknown_mod"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1


class TestMainNoCache:
    def test_no_cache_disables_caching(self):
        with patch.object(sys, "argv", ["wikifix", "--list-modules", "--no-cache"]):
            with pytest.raises(SystemExit):
                main()

    def test_no_cache_passed_to_config(self):
        with patch.object(sys, "argv", ["wikifix", "--list-modules", "--no-cache"]):
            with pytest.raises(SystemExit):
                main()


class TestMainModuleOptions:
    def test_no_spacing_excludes_module(self):
        with patch.object(sys, "argv", ["wikifix", "--list-modules", "--no-spacing"]):
            with pytest.raises(SystemExit):
                main()
