#!/usr/bin/env python3
"""Export the FastAPI app's OpenAPI contract as a committed artifact (BITB-261).

The backend's request/response shapes are the contract every client (web,
Android, iOS-to-come) programs against. This script freezes that contract into
``docs/parity/openapi.json`` — a committed, machine-diffable artifact — and
gives CI two levers over it:

    python scripts/export_openapi.py
        Regenerate ``docs/parity/openapi.json`` from ``api/main.py:app``.
        Run it on the same PR as any route/schema change and commit the result.

    python scripts/export_openapi.py --check
        Regenerate in memory and diff against the committed artifact. Exits 1
        (with a unified diff) if it is stale — i.e. someone changed the API
        surface without regenerating. Safe for CI; makes no changes on disk.

    python scripts/export_openapi.py --output PATH
        Write the rendered spec somewhere other than the committed artifact
        (used by CI's oasdiff job to materialize base/head specs).

Offline import — the story's main technical risk
-------------------------------------------------
Importing ``api/main.py`` instantiates ``Settings()`` (``api/config.py``), a
Pydantic Settings class that reads EVERY field from the environment. The
offline test suite gets a working import by running with a ``DATABASE_URL``
that points at a database nobody connects to (unit tests mock the DB).

This script goes further than the test suite needs to: the artifact must be
**machine-independent**, so the caller's environment is *stripped* for the
duration of the app import. ``os.environ`` is saved, replaced with a
controlled environment containing ONLY the known-required seeds below, and
restored afterwards (save/replace/restore — chosen over a clean subprocess
because it keeps the export testable in-process and needs no extra machinery).
Any caller values that could otherwise leak into ``Settings()`` — e.g. a real
``LLM_PROVIDER=claude`` with its required key check, ``MAX_MESSAGE_LENGTH=999``
baked into a schema description, or a different ``DATABASE_URL`` — cannot reach
the import, so the output is identical on every machine. Only a few harmless
interpreter-level variables (``PATH``, ``HOME``, ...) pass through; every
Settings-shaped key does not.

Seeds (all keyless, none connected to):

- ``DATABASE_URL`` — a dummy DSN without the ``CONFIGURE_ME`` placeholder
  Settings rejects; never connected to (``app.openapi()`` builds the document
  from route/model metadata only).
- ``LLM_PROVIDER=ollama`` / ``EMBEDDING_PROVIDER=ollama`` — the keyless
  defaults, so no API keys are required.

Note: Settings additionally reads an ``.env`` file if present in the CWD
(``env_file``); this script is always run from the repo root, which has no
``.env`` (only ``.env.local`` / ``.env.dev``, which it does not read).

No database connection is made: ``app.openapi()`` builds the document purely
from route/model metadata; it never touches the DB (only the lifespan
handler does, and it does not run here). Verified offline on a fresh checkout:

    python scripts/export_openapi.py

The output is the same JSON the live service serves at the public,
unauthenticated ``/openapi.json`` path (see ``TURNSTILE_SKIP_PATHS`` in
``docs/SECURITY.md``) — it contains no secrets, only route and schema shapes.

Determinism
-----------
The artifact must diff meaningfully, not churn. The rendered JSON sorts every
object's keys (``json.dumps(..., sort_keys=True)`` sorts recursively), so path
order, schema order, and key order in the file are stable across regenerations
and independent of route registration order. Two runs on the same commit
produce byte-identical output (asserted by ``scripts/test_export_openapi.py``).

See ``docs/parity/README.md`` for the zero-to-running guide and the oasdiff
warn-vs-gate policy. Part of BITB-260 stage 1 (contracts layer).
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator

_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _REPO_ROOT / "api"
_ARTIFACT_PATH = _REPO_ROOT / "docs" / "parity" / "openapi.json"

# Dummy DSN with no CONFIGURE_ME placeholder (Settings rejects that), never
# connected to — app.openapi() builds the document from route metadata only.
# pragma comments: these are inert literals, not real credentials.
_OFFLINE_DATABASE_URL = "postgresql://openapi-export:openapi-export@localhost:5432/openapi_export"  # pragma: allowlist secret
# The ONLY variables Settings() may see during the app import (see the module
# docstring): the keyless seeds above plus interpreter-level passthrough that
# the import machinery itself may consult. Everything else the caller has set
# is stripped, so the export cannot vary per machine.
_OFFLINE_ENV_SEEDS = {
    "DATABASE_URL": _OFFLINE_DATABASE_URL,
    # Keyless defaults — Settings() requires no LLM keys for these providers.
    "LLM_PROVIDER": "ollama",
    "EMBEDDING_PROVIDER": "ollama",
}
# Interpreter-level passthrough: none of these is a Settings field; they are
# kept only so the Python import machinery behaves normally.
_PASSTHROUGH_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "SYSTEMROOT", "PWD", "TEMP", "TMP")


@contextlib.contextmanager
def _controlled_environ() -> Iterator[dict[str, str]]:
    """Replace ``os.environ`` with the controlled offline env for the import.

    Machine independence (BITB-261 round 2): the caller's environment is
    stripped — save/replace/restore around the app import — so no caller env
    var (a real DATABASE_URL, LLM_PROVIDER=claude, MAX_MESSAGE_LENGTH=999, …)
    can reach ``Settings()`` and leak into the generated schema. Only the
    keyless seeds plus interpreter-level passthrough keys are visible.
    """
    saved = dict(os.environ)
    try:
        os.environ.clear()
        for key in _PASSTHROUGH_KEYS:
            if key in saved:
                os.environ[key] = saved[key]
        os.environ.update(_OFFLINE_ENV_SEEDS)
        yield os.environ
    finally:
        os.environ.clear()
        os.environ.update(saved)


def load_openapi_document() -> dict[str, Any]:
    """Import the FastAPI app offline and return its OpenAPI document.

    No DB connection and no LLM keys are needed, and the caller's environment
    cannot influence the result: see the module docstring.
    """
    if str(_API_DIR) not in sys.path:
        # api/ uses flat imports (`from main import app`); put it on sys.path.
        sys.path.insert(0, str(_API_DIR))
    with _controlled_environ():
        from main import app  # noqa: E402  (import after sys.path setup is the point)

    return app.openapi()


def render_openapi_json(document: dict[str, Any]) -> str:
    """Render the document as deterministic JSON text (all keys sorted)."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _display(artifact: Path) -> str:
    """Best-effort display path: relative to the repo root when inside it."""
    try:
        return str(artifact.relative_to(_REPO_ROOT))
    except ValueError:
        return str(artifact)


def _print_stale_diff(committed: str, regenerated: str, artifact: Path) -> None:
    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        regenerated.splitlines(keepends=True),
        fromfile=_display(artifact),
        tofile="regenerated",
    )
    print(
        "FAIL: the committed OpenAPI artifact is stale — the API surface changed "
        "without regenerating.\n"
        "Run `make parity-export` (or `python scripts/export_openapi.py`) and commit "
        f"{_display(artifact)}.\n",
        file=sys.stderr,
    )
    sys.stderr.writelines(diff)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed artifact matches the app; do not write anything.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        # Hard-coded (not an f-string on _ARTIFACT_PATH) so monkeypatched paths
        # used by the tests don't blow up relative_to here.
        help="Write the spec somewhere other than docs/parity/openapi.json.",
    )
    args = parser.parse_args(argv)

    document = load_openapi_document()
    rendered = render_openapi_json(document)

    if args.check:
        artifact = args.output or _ARTIFACT_PATH
        committed = artifact.read_text(encoding="utf-8") if artifact.exists() else ""
        if committed != rendered:
            _print_stale_diff(committed, rendered, artifact)
            return 1
        print(
            f"OK: {_display(artifact)} matches the app's OpenAPI document "
            f"({len(document['paths'])} paths)."
        )
        return 0

    artifact = args.output or _ARTIFACT_PATH
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {_display(artifact)} ({len(document['paths'])} paths, "
        f"{len(document.get('components', {}).get('schemas', {}))} schemas)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
