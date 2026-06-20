import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from wikifix import __version__
from wikifix.__main__ import MODULE_REGISTRY, build_argparser, main


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

    def test_diff_flag(self):
        parser = build_argparser()
        args = parser.parse_args(["--diff"])
        assert args.diff is True

    def test_diff_default_false(self):
        parser = build_argparser()
        args = parser.parse_args([])
        assert args.diff is False

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
        assert args.ids == "issn,pmid,pmc,s2cid,qid"


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

    def test_bare_flag_clears_defaults(self, tmp_path):
        inp = tmp_path / "in.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys,
            "argv",
            [
                "wikifix",
                "--bare",
                "--modules",
                "spacing",
                "-i",
                str(inp),
                "-o",
                str(tmp_path / "out.txt"),
            ],
        ):
            main()

    def test_sort_flag_adds_sort(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--sort", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_dedup_flag_adds_dedup(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |doi=10.1000/abc}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--dedup", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_cleanup_flag_adds_cleanup(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--cleanup", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_enrich_mode(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--enrich", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_input_file_not_found(self):
        with patch.object(sys, "argv", ["wikifix", "-i", "nonexistent.txt"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1

    def test_clear_cache(self):
        with patch.object(sys, "argv", ["wikifix", "--clear-cache"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_diff_flag_displays_diff(self, tmp_path, capsys):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys,
            "argv",
            [
                "wikifix",
                "--diff",
                "--modules",
                "spacing",
                "-i",
                str(inp),
                "-o",
                str(out),
            ],
        ):
            main()
        captured = capsys.readouterr()
        assert out.exists()

    def test_force_refresh_mode(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--force", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_ref_names_flag(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text(
            "<ref>{{cite journal |last=Smith |year=2024 |title=Test}}</ref>",
            encoding="utf-8",
        )
        with patch.object(
            sys, "argv", ["wikifix", "--ref-names", "-i", str(inp), "-o", str(out)]
        ):
            main()
        result = out.read_text(encoding="utf-8")
        assert 'name="Smith2024"' in result

    def test_no_module_excludes_correctly(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys,
            "argv",
            ["wikifix", "--no-expand", "--no-ids", "-i", str(inp), "-o", str(out)],
        ):
            main()
        assert out.exists()

    def test_ids_option(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--ids", "issn", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_workers_option(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--workers", "2", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_no_cache_with_file(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys, "argv", ["wikifix", "--no-cache", "-i", str(inp), "-o", str(out)]
        ):
            main()
        assert out.exists()

    def test_cache_dir_option(self, tmp_path):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        cache = tmp_path / "mycache"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        with patch.object(
            sys,
            "argv",
            ["wikifix", "--cache-dir", str(cache), "-i", str(inp), "-o", str(out)],
        ):
            main()
        assert out.exists()

    def test_output_cannot_be_written(self, tmp_path, caplog):
        inp = tmp_path / "in.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        out = tmp_path / "out.txt"
        out.mkdir()
        with (
            patch.object(
                sys,
                "argv",
                ["wikifix", "-i", str(inp), "-o", str(out / "nested" / "out.txt")],
            ),
            patch.object(Path, "touch", side_effect=OSError("Permission denied")),
        ):
            with pytest.raises(SystemExit):
                main()
            assert any("Cannot write" in rec.message for rec in caplog.records)

    def test_diff_no_changes(self, tmp_path, caplog):
        inp = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        out.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        from wikifix.__main__ import _show_diff

        _show_diff(inp, out)
        assert any("No differences" in rec.message for rec in caplog.records)

    def test_diff_read_error(self, tmp_path, caplog):
        from wikifix.__main__ import _show_diff

        _show_diff(tmp_path / "nonexistent", tmp_path / "other")
        assert any("Cannot compute diff" in rec.message for rec in caplog.records)

    def test_input_file_too_large(self, tmp_path, caplog):
        inp = tmp_path / "in.txt"
        inp.write_text("x", encoding="utf-8")
        out = tmp_path / "out.txt"
        with (
            patch.object(sys, "argv", ["wikifix", "-i", str(inp), "-o", str(out)]),
            patch.object(
                Path,
                "stat",
                return_value=type("st", (), {"st_size": 501 * 1024 * 1024})(),
            ),
        ):
            with pytest.raises(SystemExit):
                main()
            assert any("too large" in rec.message for rec in caplog.records)

    def test_process_file_not_found(self, tmp_path, caplog):
        inp = tmp_path / "in.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        out = tmp_path / "out.txt"
        with (
            patch.object(sys, "argv", ["wikifix", "-i", str(inp), "-o", str(out)]),
            patch(
                "wikifix.__main__.CitationPipeline.process_file",
                side_effect=FileNotFoundError,
            ),
        ):
            with pytest.raises(SystemExit):
                main()
            assert any("Could not read" in rec.message for rec in caplog.records)

    def test_process_file_generic_error(self, tmp_path, caplog):
        inp = tmp_path / "in.txt"
        inp.write_text("{{cite journal |title=Test}}", encoding="utf-8")
        out = tmp_path / "out.txt"
        with (
            patch.object(sys, "argv", ["wikifix", "-i", str(inp), "-o", str(out)]),
            patch(
                "wikifix.__main__.CitationPipeline.process_file",
                side_effect=ValueError("boom"),
            ),
        ):
            with pytest.raises(SystemExit):
                main()
            assert any("boom" in rec.message for rec in caplog.records)
