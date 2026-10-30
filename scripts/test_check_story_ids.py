#!/usr/bin/env python3
"""Offline unit tests for scripts/check_story_ids.py (BITB-235).

Everything here runs with NO network and NO repository state: the git layer is monkeypatched
with canned `merge-base`/`ls-tree` outputs and the GitHub layer with a FakeClient mirroring
``scripts/test_auto_update_prs.py``. The pure decision core (``find_conflicts``) is exercised
parametrically over the collision/renumber edge cases the BITB-235 story calls out.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "check_story_ids", _SCRIPTS_DIR / "check_story_ids.py"
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_story_ids"] = mod  # dataclass annotations resolve via sys.modules
_spec.loader.exec_module(mod)

REPO = "owner/repo"
WORKFLOW = _SCRIPTS_DIR.parent / ".github" / "workflows" / "story-id-check.yml"


def story_path(number: int, slug: str = "story") -> str:
    return f"docs/BACKLOG_STORIES/BITB-{number:03d}-{slug}.md"


# --- pure decision core --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("added", "deleted", "base", "other_prs", "expected_ids"),
    [
        pytest.param(
            [story_path(301)],
            [],
            [story_path(300)],
            {},
            [],
            id="unique new id passes",
        ),
        pytest.param(
            [story_path(301)],
            [],
            [story_path(300), story_path(301)],
            {},
            ["BITB-301"],
            id="id already claimed on base fails",
        ),
        pytest.param(
            [story_path(301)],
            [],
            [story_path(300)],
            {1203: [story_path(301, "other")]},
            ["BITB-301"],
            id="id claimed by another open pr fails",
        ),
        pytest.param(
            [story_path(302)],
            [story_path(301)],
            [story_path(301)],
            {},
            [],
            id="renumber (delete old id, add new id) passes",
        ),
        pytest.param(
            [story_path(303), story_path(303, "dupe")],
            [],
            [story_path(300)],
            {},
            ["BITB-303"],
            id="same id added twice within one pr fails",
        ),
        pytest.param(
            [story_path(301, "renamed")],
            [story_path(301)],
            [story_path(301)],
            {},
            [],
            id="base file deleted plus same number re-added (rename-in-place) passes",
        ),
    ],
)
def test_find_conflicts_edge_cases(
    added: list[str],
    deleted: list[str],
    base: list[str],
    other_prs: dict[int, list[str]],
    expected_ids: list[str],
) -> None:
    conflicts = mod.find_conflicts(added, deleted, base, other_prs, "origin/main")
    assert [conflict.story_id for conflict in conflicts] == expected_ids


def test_id_claimed_by_base_and_other_pr_lists_both_claims() -> None:
    conflicts = mod.find_conflicts(
        [story_path(301)],
        [],
        [story_path(301, "base-file")],
        {1203: [story_path(301, "other-pr")]},
        "origin/main",
    )
    assert len(conflicts) == 1
    assert conflicts[0].story_id == "BITB-301"
    wheres = [claim.where for claim in conflicts[0].claims]
    assert wheres == ["the base branch (origin/main)", "open PR #1203"]


def test_base_branch_rename_after_branch_keeps_its_claim() -> None:
    """The release subtraction is by *path*: the PR deletes the old base path it branched from,
    but the base branch has since renamed the same-numbered file — that surviving path keeps
    claiming the id and the collision must still be reported."""
    conflicts = mod.find_conflicts(
        [story_path(301, "pr-new")],
        [story_path(301, "base-old")],
        [story_path(301, "base-renamed-by-main")],
        {},
        "origin/main",
    )
    assert [conflict.story_id for conflict in conflicts] == ["BITB-301"]
    assert conflicts[0].claims == (
        mod.Claim("the base branch (origin/main)", story_path(301, "base-renamed-by-main")),
    )


def test_non_story_paths_are_ignored() -> None:
    conflicts = mod.find_conflicts(
        ["docs/DONE/BITB-301-moved.md", "docs/BACKLOG_STORIES/notes.md", "api/main.py"],
        [],
        [story_path(300), "docs/BACKLOG_STORIES/session-log-2026-10-26.md"],
        {1203: ["docs/DONE/BITB-302-x.md", "frontend/src/app/page.tsx"]},
        "origin/main",
    )
    assert conflicts == []


def test_conflicts_sort_numerically_not_lexicographically() -> None:
    conflicts = mod.find_conflicts(
        [story_path(1000), story_path(999)],
        [],
        [story_path(999, "on-base"), story_path(1000, "on-base")],
        {},
        "origin/main",
    )
    assert [conflict.story_id for conflict in conflicts] == ["BITB-999", "BITB-1000"]


# --- git layer (mocked run_git) -------------------------------------------------------------


class FakeGit:
    """Canned git: ls-tree outputs for the merge-base, HEAD, and the base-branch tip."""

    def __init__(
        self,
        *,
        merge_base: str,
        merge_base_files: list[str],
        head_files: list[str],
        base_tip_files: list[str],
    ) -> None:
        self.trees = {
            merge_base: merge_base_files,
            "HEAD": head_files,
            "origin/main": base_tip_files,
        }
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        if args[:2] == ("merge-base", "origin/main") and args[2] == "HEAD":
            return "mb000\n"
        if args[0] == "ls-tree":
            rev = args[4]
            if rev not in self.trees:
                raise mod.GitError(f"git ls-tree ... {rev} ... failed: bad object")
            return "\0".join(self.trees[rev]) + ("\0" if self.trees[rev] else "")
        raise AssertionError(f"unexpected git call: {args}")


@pytest.fixture
def renumber_repo(monkeypatch: pytest.MonkeyPatch) -> FakeGit:
    """A PR that deletes BITB-301-old and adds BITB-302-new (the canonical renumber)."""
    fake = FakeGit(
        merge_base="mb000",
        merge_base_files=[story_path(300), story_path(301, "old")],
        head_files=[story_path(300), story_path(302, "new")],
        base_tip_files=[story_path(300), story_path(301, "old")],
    )
    monkeypatch.setattr(mod, "run_git", fake)
    return fake


def test_git_layer_computes_adds_and_deletes_vs_merge_base(
    renumber_repo: FakeGit,
) -> None:
    added, deleted = mod.pr_added_and_deleted_story_paths("origin/main")
    assert added == [story_path(302, "new")]
    assert deleted == [story_path(301, "old")]
    # ls-tree of the merge-base and of HEAD, plus the base-branch tip for base claims.
    assert renumber_repo.calls[0] == ("merge-base", "origin/main", "HEAD")


def test_git_error_propagates_as_giterror(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: str) -> str:
        raise mod.GitError("git merge-base origin/main HEAD failed: not found")

    monkeypatch.setattr(mod, "run_git", refuse)
    with pytest.raises(mod.GitError, match="merge-base"):
        mod.pr_added_and_deleted_story_paths("origin/main")


def test_ls_tree_parses_nul_separated_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "run_git",
        lambda *a: "docs/BACKLOG_STORIES/BITB-1-a.md\0" "docs/BACKLOG_STORIES/BITB-2-b.md\0",
    )
    assert mod.git_ls_tree_story_paths("origin/main") == [
        "docs/BACKLOG_STORIES/BITB-1-a.md",
        "docs/BACKLOG_STORIES/BITB-2-b.md",
    ]


# --- github layer (FakeClient) --------------------------------------------------------------


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        self.calls.append((method, path))
        if (method, path) not in self.responses:
            raise AssertionError(f"unexpected API call: {method} {path}")
        return self.responses[(method, path)]


def list_path(page: int = 1) -> str:
    return f"/repos/{REPO}/pulls?state=open&base=main&per_page=100&page={page}"


def files_path(number: int, page: int = 1) -> str:
    return f"/repos/{REPO}/pulls/{number}/files?per_page=100&page={page}"


def file_entry(filename: str, status: str) -> dict:
    return {"filename": filename, "status": status}


def make_pr(number: int) -> dict:
    return {"number": number, "state": "open", "draft": False}


def _factory(client: FakeClient):
    return lambda token: client


def test_other_pr_claims_collect_added_story_files_and_skip_self() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1200), make_pr(1203), make_pr(1215)]),
            ("GET", files_path(1200)): (
                200,
                [
                    file_entry(story_path(240, "modified"), "modified"),
                    file_entry("docs/BACKLOG.md", "modified"),
                ],
            ),
            ("GET", files_path(1203)): (
                200,
                [
                    file_entry(story_path(241, "from-1203"), "added"),
                    file_entry(story_path(239, "removed-by-1203"), "removed"),
                ],
            ),
            ("GET", files_path(1215)): (
                200,
                [
                    file_entry(story_path(241, "from-1215-renamed"), "renamed"),
                    file_entry(story_path(242, "fork-add"), "added"),
                ],
            ),
        }
    )
    claims = mod.other_open_pr_claims(client, REPO, "main", current_pr=1215)
    # 1200 modified only — no claim. 1203 adds BITB-241. 1215 is the current PR: skipped.
    assert claims == {1203: [story_path(241, "from-1203")]}


def test_other_pr_claims_paginate_all_pages() -> None:
    page1 = [make_pr(n) for n in range(1, 101)]
    client = FakeClient(
        {
            ("GET", list_path(1)): (200, page1),
            ("GET", list_path(2)): (200, [make_pr(101)]),
            **{
                ("GET", files_path(n)): (
                    200,
                    [file_entry(story_path(500, f"pr{n}"), "added")],
                )
                for n in range(1, 102)
            },
        }
    )
    claims = mod.other_open_pr_claims(client, REPO, "main", current_pr=1)
    assert sorted(claims) == list(range(2, 102))
    # 2 list pages + one files fetch for each of the 100 other PRs (PR #1 is self, skipped).
    assert len(client.calls) == 2 + 100


def test_unreadable_pr_is_skipped_with_warning_not_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1203), make_pr(1204)]),
            ("GET", files_path(1203)): (404, {"message": "gone"}),
            ("GET", files_path(1204)): (200, [file_entry(story_path(241, "pr1204"), "added")]),
        }
    )
    claims = mod.other_open_pr_claims(client, REPO, "main", current_pr=1215)
    assert claims == {1204: [story_path(241, "pr1204")]}
    err = capsys.readouterr().err
    assert "::warning::skipping PR #1203" in err


def test_auth_error_on_list_aborts() -> None:
    client = FakeClient({("GET", list_path()): (403, {"message": "nope"})})
    with pytest.raises(mod.AuthError, match="pull-requests: read"):
        mod.other_open_pr_claims(client, REPO, "main", current_pr=1)


# --- main() integration (git mocked, API faked) ----------------------------------------------


def test_main_passes_for_a_renumber(
    monkeypatch: pytest.MonkeyPatch, renumber_repo: FakeGit, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1203)]),
            ("GET", files_path(1203)): (200, [file_entry("docs/BACKLOG.md", "modified")]),
        }
    )
    rc = mod.main(
        ["--pr", "9999"],
        env={"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "t"},
        client_factory=_factory(client),
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK: this PR adds story file(s) with id(s) BITB-302" in out
    # The base-branch tip was enumerated for base claims after the merge-base diff.
    assert (
        "ls-tree",
        "-r",
        "--name-only",
        "-z",
        "origin/main",
        "--",
        "docs/BACKLOG_STORIES",
    ) in renumber_repo.calls


def test_main_fails_with_actionable_message_on_base_collision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        mod,
        "run_git",
        FakeGit(
            merge_base="mb000",
            merge_base_files=[story_path(241, "old")],
            head_files=[story_path(241, "old"), story_path(241, "from-this-pr")],
            base_tip_files=[story_path(241, "old")],
        ),
    )
    client = FakeClient({("GET", list_path()): (200, [make_pr(1203), make_pr(9999)])})
    # Another PR adds the same id (PR #1203 claims BITB-241 — the 2026-10-26 collision).
    client.responses[("GET", files_path(1203))] = (
        200,
        [file_entry(story_path(241, "from-1203"), "added")],
    )
    rc = mod.main(
        ["--pr", "9999"],
        env={"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "t"},
        client_factory=_factory(client),
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert "::error ::BITB-241 is already claimed" in captured.out
    err = captured.err
    assert "BITB-241" in err
    assert "the base branch (origin/main)" in err
    assert "open PR #1203" in err
    assert "AGENTS.md -> Backlog Hygiene" in err
    assert "FIRST claimant keeps the ID" in err


def test_main_fails_on_duplicate_add_within_the_pr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        mod,
        "run_git",
        FakeGit(
            merge_base="mb000",
            merge_base_files=[story_path(300)],
            head_files=[story_path(300), story_path(301, "a"), story_path(301, "b")],
            base_tip_files=[story_path(300)],
        ),
    )
    client = FakeClient({("GET", list_path()): (200, [])})
    rc = mod.main(
        ["--pr", "9999"],
        env={"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "t"},
        client_factory=_factory(client),
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "BITB-301" in err
    assert "this PR itself (duplicate add)" in err


def test_main_short_circuits_when_no_story_files_are_added(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        mod,
        "run_git",
        FakeGit(
            merge_base="mb000",
            # The PR only *modifies* BITB-301 — the same path exists on both sides.
            merge_base_files=[story_path(300), story_path(301)],
            head_files=[story_path(300), story_path(301)],
            base_tip_files=[story_path(300), story_path(301)],
        ),
    )
    rc = mod.main(
        ["--pr", "9999"],
        env={"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "t"},
        client_factory=_factory(FakeClient({})),
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK: this PR adds no docs/BACKLOG_STORIES/ story files" in out


def test_main_returns_2_on_git_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(*args: str) -> str:
        raise mod.GitError("git merge-base origin/main HEAD failed: fatal: Not a valid ref")

    monkeypatch.setattr(mod, "run_git", refuse)
    assert mod.main([], env={}, client_factory=lambda t: FakeClient({})) == 2
    assert "merge-base" in capsys.readouterr().err


def test_main_returns_2_when_pr_context_is_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        mod,
        "run_git",
        FakeGit(
            merge_base="mb000",
            merge_base_files=[],
            head_files=[story_path(301)],
            base_tip_files=[],
        ),
    )
    rc = mod.main(
        ["--pr", "9999"],
        env={"GITHUB_REPOSITORY": REPO},
        client_factory=lambda t: FakeClient({}),
    )
    assert rc == 2
    assert "--token is missing" in capsys.readouterr().err


def test_main_without_pr_checks_base_branch_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        mod,
        "run_git",
        FakeGit(
            merge_base="mb000",
            merge_base_files=[story_path(300)],
            head_files=[story_path(300), story_path(301, "new")],
            base_tip_files=[story_path(300), story_path(301, "claimed-on-main")],
        ),
    )
    rc = mod.main([], env={}, client_factory=lambda t: FakeClient({}))
    assert rc == 1
    captured = capsys.readouterr()
    assert "NOTE: no --pr given" in captured.out
    assert "BITB-301" in captured.err
    assert "claimed-on-main" in captured.err


# --- workflow guards ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def test_workflow_triggers_on_pr_story_paths(workflow: dict) -> None:
    paths = workflow["on"]["pull_request"]["paths"]
    assert workflow["on"]["pull_request"]["branches"] == ["main"]
    assert "docs/BACKLOG_STORIES/**" in paths
    assert "scripts/check_story_ids.py" in paths
    assert "scripts/test_check_story_ids.py" in paths


def test_workflow_permissions_are_read_only(workflow: dict) -> None:
    assert workflow["permissions"] == {"contents": "read", "pull-requests": "read"}


def test_workflow_check_step_runs_the_script(workflow: dict) -> None:
    run_steps = [
        step for job in workflow["jobs"].values() for step in job["steps"] if "run" in step
    ]
    assert any("scripts/check_story_ids.py" in step["run"] for step in run_steps)
    assert any("pytest scripts/test_check_story_ids.py" in step["run"] for step in run_steps)
