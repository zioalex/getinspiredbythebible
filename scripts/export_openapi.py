#!/usr/bin/env python3
"""Export the FastAPI app's OpenAPI contract to ``docs/parity/openapi.json`` (BITB-261).

The committed artifact is the machine-diffable source of truth for the request/response
shapes every client (web, Android, iOS-to-come) talks to. See ``docs/parity/README.md``.

    python scripts/export_openapi.py            # (re)write docs/parity/openapi.json
    python scripts/export_openapi.py --check    # exit 1 if the committed file is stale

The export is fully OFFLINE: it imports ``api/main.py`` and calls ``app.openapi()``. No
database connection is opened, no LLM/embedding key is needed. ``Settings()`` only insists
that ``DATABASE_URL`` is not the placeholder, so this script pins a dummy URL (never
connected to). The caller's environment is stripped (only PATH/HOME/locale/Python vars are kept) and
``.env`` is not read (the script runs from a scratch cwd), so the output is identical on
every machine. It needs the backend dependencies (``api/requirements.txt``), i.e. the
project venv: ``make parity-export``.

Output is deterministic: JSON with sorted keys, 2-space indent, trailing newline.

--check   Regenerate in memory and diff against the committed file. Exits 1 (printing a
          unified diff) when they differ. Writes nothing; safe for CI.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _REPO_ROOT / "api"
_OUTPUT_PATH = _REPO_ROOT / "docs" / "parity" / "openapi.json"

# Dummy, never-connected URL: config.Settings rejects the CONFIGURE_ME placeholder default.
_OFFLINE_DATABASE_URL = (
    "postgresql://offline:offline@localhost:5432/offline"  # pragma: allowlist secret
)

# Only these caller env vars survive into the import. Everything else is dropped, because
# ``Settings()`` reads every variable (e.g. MAX_MESSAGE_LENGTH leaks into the schema, and
# LLM_PROVIDER=claude without a key would crash), which would make the artifact machine-specific.
_KEEP_ENV_PREFIXES = ("PYTHON", "LC_", "VIRTUAL_ENV")
_KEEP_ENV = {"PATH", "HOME", "LANG", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "USERPROFILE"}


def load_openapi_schema() -> dict:
    """Import ``api/main.py`` offline and return ``app.openapi()``.

    Temporarily replaces ``os.environ`` / cwd / ``sys.path`` and restores them afterwards.
    """
    saved_env = dict(os.environ)
    saved_path = list(sys.path)
    previous_cwd = os.getcwd()
    for name in list(os.environ):
        if name not in _KEEP_ENV and not name.startswith(_KEEP_ENV_PREFIXES):
            del os.environ[name]
    os.environ["DATABASE_URL"] = _OFFLINE_DATABASE_URL
    sys.path.insert(0, str(_API_DIR))
    # Settings reads ".env" relative to the cwd; run from an empty dir so a developer's
    # api/.env or repo-root .env can never leak into the artifact.
    try:
        with tempfile.TemporaryDirectory() as scratch:
            os.chdir(scratch)
            from main import app

            return app.openapi()
    finally:
        os.chdir(previous_cwd)
        os.environ.clear()
        os.environ.update(saved_env)
        sys.path[:] = saved_path


def render(schema: dict) -> str:
    """Deterministic serialisation: sorted keys (paths, schemas, ...), stable indent."""
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed artifact is up to date; do not write anything.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_OUTPUT_PATH,
        help="Artifact path (default: docs/parity/openapi.json).",
    )
    args = parser.parse_args(argv)

    generated = render(load_openapi_schema())
    output: Path = args.output
    label = (
        str(output.relative_to(_REPO_ROOT)) if output.is_relative_to(_REPO_ROOT) else str(output)
    )

    if args.check:
        current = output.read_text(encoding="utf-8") if output.exists() else ""
        if current == generated:
            print(f"OK: {label} matches the FastAPI app's OpenAPI schema.")
            return 0
        print(
            f"FAIL: {label} is stale (the API contract changed without regenerating).\n"
            "Run `make parity-export` and commit the result.\n",
            file=sys.stderr,
        )
        sys.stderr.writelines(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=label,
                tofile="generated",
            )
        )
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"Wrote {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
