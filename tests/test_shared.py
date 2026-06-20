"""Cross-implementation shared fixtures test.

Reads the same JSON fixture file as the JS shared.test.ts and runs the
Python pipeline against each case. Verifies the same checks pass.
"""

import json
import os
from pathlib import Path

import pytest

from wikifix import ApiConfig, CitationPipeline, Mode
from wikifix.__main__ import MODULE_REGISTRY

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "wikifix-extension"
    / "tests"
    / "fixtures"
    / "shared.json"
)

with open(FIXTURE_PATH, encoding="utf-8") as f:
    FIXTURES = json.load(f)


def _process(
    text: str,
    modules_str: str,
    *,
    ref_names: bool = False,
) -> str:
    module_names = [m.strip() for m in modules_str.split(",") if m.strip()]
    unknown = set(module_names) - set(MODULE_REGISTRY)
    if unknown:
        pytest.skip(f"Python module(s) not found: {unknown}")

    modules = [MODULE_REGISTRY[n]() for n in module_names]
    pipeline = CitationPipeline(
        modules=modules,
        mode=Mode.INCREMENTAL,
        api_config=ApiConfig(cache_dir=None),
        ref_names=ref_names,
    )

    import tempfile

    in_fd, in_p = tempfile.mkstemp(suffix=".txt")
    os.close(in_fd)
    in_path = Path(in_p)
    out_fd, out_p = tempfile.mkstemp(suffix=".txt")
    os.close(out_fd)
    out_path = Path(out_p)
    try:
        in_path.write_text(text, encoding="utf-8")
        pipeline.process_file(in_path, out_path)
        result = out_path.read_text(encoding="utf-8")
        return result
    finally:
        import time

        for p in (in_path, out_path):
            for _ in range(3):
                try:
                    if p.exists():
                        p.unlink()
                    break
                except PermissionError:
                    time.sleep(0.05)


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f["name"] for f in FIXTURES])
def test_shared_fixture(fixture: dict, request: pytest.FixtureRequest) -> None:
    if fixture.get("xfail_py"):
        pytest.xfail(fixture["xfail_py"])
    result = _process(
        fixture["input"],
        fixture.get("modules", "expand,cleanup,dates,spacing,sort"),
        ref_names=fixture.get("ref_names", False),
    )

    for c in fixture.get("checks", []):
        assert c in result, f"Expected {c!r} in {result[:200]}..."

    for c in fixture.get("no_checks", []):
        assert c not in result, f"Unexpected {c!r} in {result[:200]}..."
