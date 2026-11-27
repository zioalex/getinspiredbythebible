#!/usr/bin/env python3
"""Tests for scripts/pr_kind.py (BITB-366)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import backlog  # noqa: E402
import pr_kind  # noqa: E402

S = "docs/BACKLOG_STORIES/"


def _story(
    story_id: str,
    kind: str | None = None,
    milestone: str | None = None,
    created: str = "2026-11-27",
) -> str:
    lines = ["---", f"id: {story_id}", "status: todo", "priority: P2"]
    if kind:
        lines.append(f"kind: {kind}")
    if milestone:
        lines.append(f"milestone: {milestone}")
    lines += ["size: S", f"created: {created}", "---"]
    return "\n".join(lines) + f"\n\n# {story_id}: A story\n\nBody.\n"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    files = {
        "BITB-101-feature.md": _story("BITB-101", "feature", "R1"),
        "BITB-102-nfr.md": _story("BITB-102", "nfr", "R1"),
        "BITB-103-fix.md": _story("BITB-103", "fix", "R1"),
        "BITB-104-chore.md": _story("BITB-104", "chore"),
        "BITB-105-spike.md": _story("BITB-105", "spike"),
        "BITB-106-fix-r2.md": _story("BITB-106", "fix", "R2"),
        "BITB-107-old.md": _story("BITB-107", created="2026-11-20"),
        "BITB-108-new.md": _story("BITB-108"),
        "BITB-109-fix.md": _story("BITB-109", "fix", "R1"),
    }
    for name, text in files.items():
        path = tmp_path / S / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _classify(root: Path, title: str, author: str = "someone", head_ref: str = "x"):
    return pr_kind.classify(title, author, head_ref, backlog.load_all(root))


@pytest.mark.parametrize(
    ("title", "kind", "milestone"),
    [
        ("feat(web): new thing (BITB-101)", "feature", "R1"),
        ("fix(api): rate-limit search (BITB-102)", "nfr", "R1"),
        ("feat(infra): failover hop (BITB-102)", "nfr", "R1"),
        ("perf(api): faster (BITB-102)", "nfr", "R1"),
        ("fix(android): crash (BITB-103)", "fix", "R1"),
        ("ci: retry install (BITB-104)", "chore", ""),
        ("docs(backlog): file stories (BITB-104)", "chore", ""),
        ("chore: decision record (BITB-105)", "spike", ""),
        ("revert: undo the feature (BITB-101)", "feature", "R1"),
        ("fix(api)!: breaking fix (BITB-103)", "fix", "R1"),
    ],
)
def test_valid_titles(root: Path, title: str, kind: str, milestone: str) -> None:
    result = _classify(root, title)
    assert result.errors == []
    assert (result.kind, result.milestone) == (kind, milestone)


def test_multiple_ids_same_kind_and_slash_form(root: Path) -> None:
    result = _classify(root, "fix(api): two fixes (BITB-103, BITB-109)")
    assert (
        result.errors == [] and result.kind == "fix" and result.stories == ["BITB-103", "BITB-109"]
    )
    assert _classify(root, "fix(api): slash (BITB-103/109)").stories == ["BITB-103", "BITB-109"]


@pytest.mark.parametrize(
    ("title", "needle"),
    [
        ("fix(opencode): watchdog (BITB-104)", "a `chore` change may not use the `fix:` type"),
        ("feat(parity): registry (BITB-104)", "a `chore` change may not use the `feat:` type"),
        ("feat: experiment (BITB-105)", "a `spike` change may not use the `feat:` type"),
        ("chore: new screen (BITB-101)", "a `feature` change may not use the `chore:` type"),
        ("feat(web): bug (BITB-103)", "a `fix` change may not use the `feat:` type"),
        ("ci: hardening (BITB-102)", "a `nfr` change may not use the `ci:` type"),
        ("fix: mixed (BITB-101, BITB-103)", "different kinds (feature: BITB-101; fix: BITB-103)"),
        (
            "fix: two releases (BITB-103, BITB-106)",
            "different milestones (R1: BITB-103; R2: BITB-106)",
        ),
        ("fix: no story", "names no BITB-NNN story"),
        ("fix: ghost (BITB-999)", "BITB-999 has no story file"),
        ("Fix the thing (BITB-103)", "is not a conventional commit"),
        ("fix: new story without kind (BITB-108)", "BITB-108 has no `kind`"),
    ],
)
def test_rule_violations(root: Path, title: str, needle: str) -> None:
    result = _classify(root, title)
    assert any(needle in e for e in result.errors), result.errors


def test_story_older_than_cutover_without_kind_only_warns(root: Path) -> None:
    result = _classify(root, "fix(api): old story (BITB-107)")
    assert result.errors == [] and result.kind == ""
    assert any("BITB-107 has no `kind`" in w for w in result.warnings)


@pytest.mark.parametrize(
    ("author", "head_ref"),
    [
        ("dependabot[bot]", "dependabot/pip/x"),
        ("github-actions[bot]", "anything"),
        ("zioalex", "release-please--branches--main"),
    ],
)
def test_automation_is_skipped_as_chore(root: Path, author: str, head_ref: str) -> None:
    result = _classify(root, "build(deps): bump something", author, head_ref)
    assert result.skip and result.kind == "chore" and result.errors == []


def test_cli_json_and_github_output(root: Path, tmp_path: Path, capsys) -> None:
    out = tmp_path / "gh_output"
    code = pr_kind.main(
        [
            "--root",
            str(root),
            "--title",
            "fix(api): rate limit (BITB-102)",
            "--author",
            "someone",
            "--json",
            "--github-output",
            str(out),
        ]
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out.splitlines()[0])
    assert data["kind"] == "nfr" and data["milestone"] == "R1" and data["product"] is True
    written = dict(line.split("=", 1) for line in out.read_text().splitlines())
    assert written == {
        "skip": "false",
        "kind": "nfr",
        "milestone": "R1",
        "product": "true",
        "wip_limit": str(pr_kind.WIP_LIMIT),
    }


def test_cli_fails_with_annotation(root: Path, capsys) -> None:
    code = pr_kind.main(["--root", str(root), "--title", "fix(opencode): x (BITB-104)"])
    assert code == 1
    assert "::error::a `chore` change may not use the `fix:` type" in capsys.readouterr().out


def test_allowed_types_cover_every_kind_and_match_commitlint() -> None:
    assert set(pr_kind.ALLOWED_TYPES) == set(backlog.KINDS)
    commitlint = (_SCRIPTS_DIR.parent / "commitlint.config.cjs").read_text(encoding="utf-8")
    for types in pr_kind.ALLOWED_TYPES.values():
        for commit_type in types:
            assert f'"{commit_type}"' in commitlint, commit_type


def test_real_tree_r1_titles() -> None:
    """The open R1 PRs, as titled on 2026-11-26, classify against the real backlog."""
    stories = backlog.load_all(_SCRIPTS_DIR.parent)
    ok = pr_kind.classify(
        "fix(api): stop echoing raw exception text from public routes (BITB-317)", "a", "b", stories
    )
    assert (ok.kind, ok.milestone, ok.errors) == ("nfr", "R1", [])
    tooling = pr_kind.classify(
        "fix(opencode): add stream-stall watchdog (BITB-270)", "a", "b", stories
    )
    assert tooling.kind == "chore" and tooling.errors
