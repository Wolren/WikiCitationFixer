"""Runs the pipeline on every .txt file in tests/fixtures/texts/.

Drop a Wikipedia article's wikitext into that folder to include it in
both Python and JS cross-implementation tests.

Uses only non-API modules (cleanup, dates, spacing, sort, dedup) so that
tests are fast and deterministic without mocking network calls.
"""

from pathlib import Path

import pytest

from wikifix import ApiConfig, CitationPipeline, Mode
from wikifix.__main__ import MODULE_REGISTRY

TEXT_DIR = (
    Path(__file__).parents[1] / "wikifix-extension" / "tests" / "fixtures" / "texts"
)
FILES = sorted(TEXT_DIR.glob("*.txt"))


def _process(text: str) -> str:
    modules = [
        MODULE_REGISTRY[n]() for n in ("cleanup", "dates", "spacing", "sort", "dedup")
    ]
    pipeline = CitationPipeline(
        modules=modules,
        mode=Mode.INCREMENTAL,
        api_config=ApiConfig(cache_dir=None, max_workers=1),
    )
    import os
    import tempfile
    import time

    in_fd, in_p = tempfile.mkstemp(suffix=".txt")
    os.close(in_fd)
    out_fd, out_p = tempfile.mkstemp(suffix=".txt")
    os.close(out_fd)
    in_path = Path(in_p)
    out_path = Path(out_p)
    try:
        in_path.write_text(text, encoding="utf-8")
        pipeline.process_file(in_path, out_path)
        return out_path.read_text(encoding="utf-8")
    finally:
        for p in (in_path, out_path):
            for _ in range(3):
                try:
                    if p.exists():
                        p.unlink()
                    break
                except PermissionError:
                    time.sleep(0.05)


@pytest.mark.skipif(not FILES, reason="No .txt files in fixtures/texts/")
@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_text_file(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    assert original.strip(), f"{path.name} is empty"

    result = _process(original)

    assert result.strip(), f"Output for {path.name} is empty"
    assert "<ref><ref" not in result, f"Double <ref> in {path.name}"
    assert "<ref >" not in result, f"Empty <ref > in {path.name}"
    assert len(result) >= len(original) * 0.5, (
        f"Output for {path.name} is less than 50% of input length"
    )
