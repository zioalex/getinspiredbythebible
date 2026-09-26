#!/usr/bin/env python3
"""Regression tests for scripts/generate_localized_book_map.py (BITB-059 / BITB-113).

Runs the generator against an isolated temporary copy of its inputs (never the real repo
files), so these tests can safely hand-edit a "generated" file to prove --check catches drift
without risking the actual committed files. Covers both generation groups: the book-name map
(BITB-059) and the verse grammar (BITB-113).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GENERATOR_SRC = _REPO_ROOT / "scripts" / "generate_localized_book_map.py"
_BOOK_MAP_JSON_SRC = _REPO_ROOT / "tests" / "fixtures" / "localized_book_map.json"
_GRAMMAR_JSON_SRC = _REPO_ROOT / "tests" / "fixtures" / "verse_grammar.json"

# Relative to the isolated temp repo root, matching the real layout the generator expects.
_KT_UTILS_REL = Path("android/app/src/main/kotlin/org/voxquieta/app/utils")
_TS_LIB_REL = Path("frontend/src/lib")

_ALL_TARGET_RELS = [
    _KT_UTILS_REL / "LocalizedBookToEnglish.kt",
    _TS_LIB_REL / "localizedBookMap.generated.ts",
    _KT_UTILS_REL / "VerseGrammar.kt",
    _TS_LIB_REL / "verseGrammar.generated.ts",
]


@pytest.fixture
def isolated_repo(tmp_path: Path) -> Path:
    """Build a throwaway repo containing only what the generator touches."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(_GENERATOR_SRC, tmp_path / "scripts" / "generate_localized_book_map.py")

    fixtures_dir = tmp_path / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    shutil.copy(_BOOK_MAP_JSON_SRC, fixtures_dir / "localized_book_map.json")
    shutil.copy(_GRAMMAR_JSON_SRC, fixtures_dir / "verse_grammar.json")

    (tmp_path / _KT_UTILS_REL).mkdir(parents=True)
    (tmp_path / _TS_LIB_REL).mkdir(parents=True)

    return tmp_path


def _run_generator(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "generate_localized_book_map.py"), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_check_fails_before_first_generation(isolated_repo: Path):
    """No generated files exist yet, so --check must report a mismatch (empty vs. generated)
    for every target and exit non-zero."""
    result = _run_generator(isolated_repo, "--check")
    assert result.returncode == 1, result.stderr
    for rel in _ALL_TARGET_RELS:
        assert "FAIL" in result.stderr
        assert rel.name in result.stderr


def test_write_then_check_passes_for_all_four_targets(isolated_repo: Path):
    write_result = _run_generator(isolated_repo)
    assert write_result.returncode == 0, write_result.stderr

    for rel in _ALL_TARGET_RELS:
        path = isolated_repo / rel
        assert path.exists(), f"generator did not write {rel}"
        assert path.stat().st_size > 0

    check_result = _run_generator(isolated_repo, "--check")
    assert check_result.returncode == 0, check_result.stderr
    assert "FAIL" not in check_result.stderr
    for rel in _ALL_TARGET_RELS:
        assert f"OK: {rel.name}" in check_result.stdout


@pytest.mark.parametrize("rel", _ALL_TARGET_RELS, ids=[str(r) for r in _ALL_TARGET_RELS])
def test_check_fails_after_hand_editing_a_generated_file(isolated_repo: Path, rel: Path):
    """A hand-edit to any one of the four generated files — book-map or grammar, Kotlin or
    TS — must be caught by --check, matching the CI guard in test_update.yml."""
    write_result = _run_generator(isolated_repo)
    assert write_result.returncode == 0, write_result.stderr

    target = isolated_repo / rel
    with target.open("a", encoding="utf-8") as f:
        f.write("\n// hand-edited — this should never survive --check\n")

    check_result = _run_generator(isolated_repo, "--check")
    assert (
        check_result.returncode == 1
    ), f"--check did not detect a hand-edit to {rel}:\n{check_result.stdout}\n{check_result.stderr}"
    assert f"FAIL: {rel.name}" in check_result.stderr


def test_grammar_targets_regenerate_from_an_edited_json(isolated_repo: Path):
    """Changing the canonical verse_grammar.json (e.g. bumping connector_repeat_max) and
    re-running the generator must change both grammar targets accordingly — proving they
    actually derive from the JSON rather than being static boilerplate."""
    write_result = _run_generator(isolated_repo)
    assert write_result.returncode == 0, write_result.stderr

    grammar_json_path = isolated_repo / "tests" / "fixtures" / "verse_grammar.json"
    grammar = json.loads(grammar_json_path.read_text(encoding="utf-8"))
    original_max = grammar["connector_repeat_max"]
    grammar["connector_repeat_max"] = original_max + 5
    grammar_json_path.write_text(json.dumps(grammar), encoding="utf-8")

    # The committed files are now stale relative to the edited JSON.
    stale_check = _run_generator(isolated_repo, "--check")
    assert stale_check.returncode == 1

    regen_result = _run_generator(isolated_repo)
    assert regen_result.returncode == 0, regen_result.stderr

    ts_content = (isolated_repo / _TS_LIB_REL / "verseGrammar.generated.ts").read_text(
        encoding="utf-8"
    )
    kt_content = (isolated_repo / _KT_UTILS_REL / "VerseGrammar.kt").read_text(encoding="utf-8")
    assert f"CONNECTOR_REPEAT_MAX = {original_max + 5}" in ts_content
    assert f"CONNECTOR_REPEAT_MAX: Int = {original_max + 5}" in kt_content

    fresh_check = _run_generator(isolated_repo, "--check")
    assert fresh_check.returncode == 0, fresh_check.stderr


def test_real_repo_generated_files_are_currently_in_sync():
    """Sanity check against the real repo (read-only: runs --check, never writes) — this is
    the same invocation CI runs in test_update.yml. Failing here means someone hand-edited a
    generated file or a JSON changed without regenerating."""
    result = subprocess.run(
        [sys.executable, str(_GENERATOR_SRC), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
