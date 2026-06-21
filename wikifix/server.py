"""Flask server exposing wikifix as an HTTP API.

Usage:
    python -m wikifix.server
    python -m wikifix.server --port 8080 --debug
"""

from __future__ import annotations

import difflib
import os
import tempfile
from pathlib import Path
from typing import Any

from wikifix import ApiConfig, CitationPipeline, Mode, __version__
from wikifix.__main__ import MODULE_REGISTRY

try:
    from flask import Flask, jsonify, request
    from flask.typing import ResponseReturnValue
    from flask_cors import CORS
except ImportError:
    msg = (
        "Flask and flask-cors are required for the server. "
        "Install with: pip install wikifix[server]"
    )
    raise ImportError(msg) from None

app = Flask(__name__)
CORS(app)


def _build_pipeline(data: dict[str, Any]) -> CitationPipeline:
    module_names = data.get("modules", "expand,authors,dates,ids,spacing,archive")
    module_names = [m.strip() for m in module_names.split(",") if m.strip()]
    unknown = set(module_names) - set(MODULE_REGISTRY)
    if unknown:
        raise ValueError(f"Unknown modules: {', '.join(sorted(unknown))}")
    modules = [MODULE_REGISTRY[n]() for n in module_names]

    mode = Mode.FORCE_REFRESH if data.get("force") else Mode.INCREMENTAL

    ids_to_fetch = data.get("ids", "issn,pmid,pmc,s2cid,qid")
    ids_to_fetch = [i.strip() for i in ids_to_fetch.split(",") if i.strip()]

    return CitationPipeline(
        modules=modules,
        mode=mode,
        author_style=data.get("author_style", "normal"),
        refresh_authors=data.get("refresh_authors", False),
        max_authors=data.get("max_authors", 6),
        ids_to_fetch=ids_to_fetch,
        force_archive_all=data.get("force_archive", False),
        create_archive=data.get("create_archive", False),
        ref_names=data.get("ref_names", False),
        strip_issn=data.get("strip_issn", False),
        spacing_style=data.get("spacing_style", "standard"),
        api_config=ApiConfig.from_env(),
    )


@app.route("/fix", methods=["POST"])
def fix() -> ResponseReturnValue:
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "No wikitext provided"}), 400

    try:
        pipeline = _build_pipeline(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    in_fd, in_path = tempfile.mkstemp(suffix=".txt", text=True)
    with os.fdopen(in_fd, "w", encoding="utf-8") as f:
        f.write(text)
    out_fd, out_path = tempfile.mkstemp(suffix=".txt", text=True)
    os.close(out_fd)

    try:
        pipeline.process_file(Path(in_path), Path(out_path))
        fixed = Path(out_path).read_text(encoding="utf-8")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(in_path)
        os.unlink(out_path)

    diff = "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True),
            fixed.splitlines(keepends=True),
            fromfile="original",
            tofile="fixed",
            lineterm="",
        )
    )

    return jsonify(
        {
            "original": text,
            "fixed": fixed,
            "diff": diff,
            "version": __version__,
        }
    )


@app.route("/health")
def health() -> ResponseReturnValue:
    return jsonify({"status": "ok", "version": __version__})


def main() -> None:
    host = os.environ.get("WIKIFIX_HOST", "0.0.0.0")
    port = int(os.environ.get("WIKIFIX_PORT", "8000"))
    debug = os.environ.get("WIKIFIX_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
