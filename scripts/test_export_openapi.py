#!/usr/bin/env python3
"""Regression tests for scripts/export_openapi.py (BITB-261).

Offline by construction: the export imports the FastAPI app inside a *stripped*
environment (only the keyless dummy seeds reach Settings() — see the script's
module docstring), so no database and no LLM keys are needed. The tests cover:

- the offline import works with a clean environment (the story's main risk);
- the rendered JSON is deterministic (two loads byte-identical) and its
  paths/schemas are key-sorted (the point of the committed artifact);
- machine independence: a hostile caller environment (real provider configs,
  hostile Settings values) cannot change the output;
- `--check` exits 0 when the committed artifact matches and 1 (with a diff on
  stderr) when it is stale;
- plain generation writes the artifact.

The `--check`/generation paths are exercised against a *temporary* copy of the
artifact path (monkeypatched), never the committed file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import export_openapi  # noqa: E402


@pytest.fixture(scope="module")
def rendered() -> str:
    """Render the app's OpenAPI document once for the read-only assertions."""
    return export_openapi.render_openapi_json(export_openapi.load_openapi_document())


def test_loads_offline_with_clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The story's main risk: importing the app needs no DATABASE_URL or LLM keys."""
    for key in (
        "DATABASE_URL",
        "LLM_PROVIDER",
        "EMBEDDING_PROVIDER",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "AZURE_OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    document = export_openapi.load_openapi_document()
    assert document["openapi"].startswith("3.")
    assert document["paths"], "expected a non-empty paths object"


def test_export_is_machine_independent(rendered: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hostile caller environment must not change the exported bytes.

    The export strips os.environ around the app import (save/replace/restore),
    so Settings() only ever sees the keyless dummy seeds — a machine with real
    provider configs, or hostile values for Settings fields that could plausibly
    reach the schema (a different DATABASE_URL, LLM_PROVIDER=claude with its
    key check, EMBEDDING_PROVIDER=azure_openai, MAX_MESSAGE_LENGTH / LLM token
    limits, debug flags), must produce byte-identical output to a clean run.
    """
    for key, value in {
        "DATABASE_URL": "postgresql://hostile:hostile@10.0.0.1:5432/hostile",  # pragma: allowlist secret
        "LLM_PROVIDER": "claude",
        "ANTHROPIC_API_KEY": "sk-ant-hostile",  # pragma: allowlist secret
        "EMBEDDING_PROVIDER": "azure_openai",
        "AZURE_OPENAI_ENDPOINT": "https://hostile.example.com",
        "MAX_MESSAGE_LENGTH": "999",
        "LLM_MAX_TOKENS": "4096",
        "EMBEDDING_DIMENSIONS": "1536",
        "DEBUG": "true",
        "APP_VERSION": "9.9.9",
    }.items():
        monkeypatch.setenv(key, value)
    hostile = export_openapi.render_openapi_json(export_openapi.load_openapi_document())
    assert hostile == rendered


def test_render_is_deterministic() -> None:
    """Two loads must be byte-identical — otherwise the artifact is churn, not diff."""
    first = export_openapi.render_openapi_json(export_openapi.load_openapi_document())
    second = export_openapi.render_openapi_json(export_openapi.load_openapi_document())
    assert first == second


def test_render_sorts_every_object_key(rendered: str) -> None:
    """json.dumps(sort_keys=True) sorts recursively; re-render must be a no-op string."""
    document = json.loads(rendered)
    # Paths and schemas must appear in sorted (not registration) order.
    assert list(document["paths"]) == sorted(document["paths"])
    schemas = document.get("components", {}).get("schemas", {})
    assert list(schemas) == sorted(schemas)
    assert json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n" == rendered


def test_check_passes_when_artifact_matches(
    rendered: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "openapi.json"
    artifact.write_text(rendered, encoding="utf-8")
    monkeypatch.setattr(export_openapi, "_ARTIFACT_PATH", artifact)
    assert export_openapi.main(["--check"]) == 0


def test_check_fails_when_artifact_is_stale(
    rendered: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    artifact = tmp_path / "openapi.json"
    document = json.loads(rendered)
    # Simulate drift: drop one path (an endpoint removed or renamed on the API).
    stale_paths = sorted(document["paths"])[:-1]
    stale = dict(document)
    stale["paths"] = {p: document["paths"][p] for p in stale_paths}
    artifact.write_text(
        json.dumps(stale, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(export_openapi, "_ARTIFACT_PATH", artifact)
    assert export_openapi.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "stale" in err
    assert "parity-export" in err


def test_check_fails_when_artifact_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(export_openapi, "_ARTIFACT_PATH", tmp_path / "absent.json")
    assert export_openapi.main(["--check"]) == 1


def test_generation_writes_the_artifact(
    rendered: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "openapi.json"
    monkeypatch.setattr(export_openapi, "_ARTIFACT_PATH", artifact)
    assert export_openapi.main([]) == 0
    assert artifact.read_text(encoding="utf-8") == rendered


def test_committed_artifact_matches_the_app(rendered: str) -> None:
    """Guard for CI parity: the committed docs/parity/openapi.json is up to date."""
    committed = (_REPO_ROOT / "docs" / "parity" / "openapi.json").read_text(encoding="utf-8")
    assert committed == rendered
