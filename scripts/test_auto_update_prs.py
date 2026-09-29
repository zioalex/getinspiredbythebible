#!/usr/bin/env python3
"""Tests for scripts/auto_update_prs.py and its workflow (BITB-165)."""

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
    "auto_update_prs", _SCRIPTS_DIR / "auto_update_prs.py"
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["auto_update_prs"] = mod  # dataclasses resolve annotations via sys.modules
_spec.loader.exec_module(mod)

REPO = "owner/repo"
WORKFLOW = _SCRIPTS_DIR.parent / ".github" / "workflows" / "auto-update-prs.yml"


def make_pr(number: int = 1, **overrides: Any) -> dict:
    pr: dict = {
        "number": number,
        "title": f"PR {number}",
        "state": "open",
        "draft": False,
        "auto_merge": {"merge_method": "squash"},
        "labels": [],
        "user": {"login": "alice"},
        "base": {"ref": "main"},
        "head": {"ref": f"feature/{number}", "sha": f"sha{number}", "repo": {"full_name": REPO}},
    }
    pr.update(overrides)
    return pr


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, Any]] = []

    def request(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        self.calls.append((method, path, body))
        return self.responses[(method, path)]

    def puts(self) -> list[tuple[str, str, Any]]:
        return [c for c in self.calls if c[0] == "PUT"]


def list_path(page: int = 1) -> str:
    return f"/repos/{REPO}/pulls?state=open&base=main&per_page=100&page={page}"


def compare_path(n: int) -> str:
    return f"/repos/{REPO}/compare/main...sha{n}?per_page=1"


def update_path(n: int) -> str:
    return f"/repos/{REPO}/pulls/{n}/update-branch"


@pytest.mark.parametrize(
    ("overrides", "eligible", "reason"),
    [
        ({"draft": True}, False, "draft"),
        ({"head": {"ref": "x", "sha": "s", "repo": {"full_name": "other/repo"}}}, False, "fork"),
        ({"head": {"ref": "x", "sha": "s", "repo": None}}, False, "fork"),
        ({"base": {"ref": "develop"}}, False, "base"),
        ({"user": {"login": "dependabot[bot]"}}, False, "dependabot"),
        (
            {
                "head": {
                    "ref": "release-please--branches--main",
                    "sha": "s",
                    "repo": {"full_name": REPO},
                }
            },
            False,
            "release-please",
        ),
        ({"auto_merge": None}, False, "not opted in"),
        ({"auto_merge": {"merge_method": "squash"}}, True, "eligible"),
        ({"auto_merge": None, "labels": [{"name": "autoupdate"}]}, True, "eligible"),
        ({"state": "closed"}, False, "not open"),
    ],
)
def test_eligibility(overrides: dict, eligible: bool, reason: str) -> None:
    ok, why = mod.is_eligible(make_pr(**overrides), REPO, "main")
    assert ok is eligible
    assert reason in why


def test_behind_pr_is_updated_with_expected_sha() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1)]),
            ("GET", compare_path(1)): (200, {"behind_by": 3}),
            ("PUT", update_path(1)): (202, {"message": "Updating pull request branch."}),
        }
    )
    results = mod.process(client, REPO, "main")
    assert [r.outcome for r in results] == ["updated"]
    assert client.puts() == [("PUT", update_path(1), {"expected_head_sha": "sha1"})]


def test_up_to_date_pr_is_not_touched() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1)]),
            ("GET", compare_path(1)): (200, {"behind_by": 0}),
        }
    )
    assert [r.outcome for r in mod.process(client, REPO, "main")] == ["up-to-date"]
    assert client.puts() == []


def test_conflict_is_not_fatal_and_next_pr_processed() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1), make_pr(2)]),
            ("GET", compare_path(1)): (200, {"behind_by": 1}),
            ("GET", compare_path(2)): (200, {"behind_by": 1}),
            ("PUT", update_path(1)): (422, {"message": "merge conflict between base and head"}),
            ("PUT", update_path(2)): (202, {}),
        }
    )
    results = mod.process(client, REPO, "main")
    assert [r.outcome for r in results] == ["conflict", "updated"]
    assert "merge conflict" in results[0].detail


def test_forbidden_update_raises() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1)]),
            ("GET", compare_path(1)): (200, {"behind_by": 1}),
            ("PUT", update_path(1)): (403, {"message": "Resource not accessible"}),
        }
    )
    with pytest.raises(RuntimeError, match="403"):
        mod.process(client, REPO, "main")


def test_list_error_raises() -> None:
    client = FakeClient({("GET", list_path()): (401, {"message": "Bad credentials"})})
    with pytest.raises(RuntimeError, match="401"):
        mod.list_open_prs(client, REPO, "main")


def test_pagination_reads_all_pages() -> None:
    page1 = [make_pr(n) for n in range(1, 101)]
    client = FakeClient(
        {("GET", list_path(1)): (200, page1), ("GET", list_path(2)): (200, [make_pr(101)])}
    )
    prs = mod.list_open_prs(client, REPO, "main")
    assert len(prs) == 101
    assert len(client.calls) == 2


def test_only_pr_fetches_single_pr_without_listing() -> None:
    client = FakeClient(
        {
            ("GET", f"/repos/{REPO}/pulls/7"): (200, make_pr(7)),
            ("GET", compare_path(7)): (200, {"behind_by": 0}),
        }
    )
    results = mod.process(client, REPO, "main", only_pr=7)
    assert [r.number for r in results] == [7]
    assert all("state=open" not in c[1] for c in client.calls)


def test_dry_run_does_not_update() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1)]),
            ("GET", compare_path(1)): (200, {"behind_by": 2}),
        }
    )
    results = mod.process(client, REPO, "main", dry_run=True)
    assert [r.outcome for r in results] == ["dry-run"]
    assert results[0].detail == "2 commits behind"
    assert client.puts() == []


def test_main_without_token_explains_secret(capsys: pytest.CaptureFixture[str]) -> None:
    rc = mod.main([], env={"GITHUB_REPOSITORY": REPO})
    assert rc == 1
    assert "AUTO_UPDATE_PR_TOKEN" in capsys.readouterr().out


def test_main_without_repo_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert mod.main([], env={"GH_TOKEN": "t"}) == 1
    assert "::error::" in capsys.readouterr().out


def _factory(client: FakeClient):
    return lambda token, api_url="https://api.github.com": client


def test_main_forbidden_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1)]),
            ("GET", compare_path(1)): (200, {"behind_by": 1}),
            ("PUT", update_path(1)): (403, {"message": "nope"}),
        }
    )
    rc = mod.main(
        [], env={"GH_TOKEN": "t", "GITHUB_REPOSITORY": REPO}, client_factory=_factory(client)
    )
    assert rc == 1
    assert "::error::" in capsys.readouterr().out


def test_main_writes_summary_and_warns_on_conflict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    summary = tmp_path / "summary.md"
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1), make_pr(2, draft=True)]),
            ("GET", compare_path(1)): (200, {"behind_by": 1}),
            ("PUT", update_path(1)): (422, {"message": "merge conflict"}),
        }
    )
    env = {"GH_TOKEN": "t", "GITHUB_REPOSITORY": REPO, "GITHUB_STEP_SUMMARY": str(summary)}
    rc = mod.main([], env=env, client_factory=_factory(client))
    out = capsys.readouterr().out
    assert rc == 0
    assert "::warning::PR #1 could not be updated automatically: merge conflict" in out
    text = summary.read_text()
    assert "| #1 | PR 1 | conflict | merge conflict |" in text
    assert "| #2 | PR 2 | skipped | draft |" in text
    assert "conflict: 1" in text


def test_one_pr_error_does_not_stop_the_sweep() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1), make_pr(2)]),
            ("GET", compare_path(1)): (502, None),
            ("GET", compare_path(2)): (200, {"behind_by": 1}),
            ("PUT", update_path(2)): (202, {}),
        }
    )
    results = mod.process(client, REPO, "main")
    assert [r.outcome for r in results] == ["error", "updated"]
    assert "HTTP 502" in results[0].detail


def test_auth_error_aborts_the_sweep() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1), make_pr(2)]),
            ("GET", compare_path(1)): (403, {"message": "Resource not accessible"}),
        }
    )
    with pytest.raises(mod.AuthError, match="403"):
        mod.process(client, REPO, "main")
    assert ("GET", compare_path(2), None) not in client.calls


def test_malformed_compare_body_is_an_error() -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1)]),
            ("GET", compare_path(1)): (200, None),
        }
    )
    [result] = mod.process(client, REPO, "main")
    assert result.outcome == "error"
    assert "behind_by" in result.detail


def test_network_error_becomes_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise mod.urllib.error.URLError("connection refused")

    monkeypatch.setattr(mod.urllib.request, "urlopen", refuse)
    with pytest.raises(RuntimeError, match="connection refused"):
        mod.GitHubClient("t").request("GET", "/x")


def test_main_reports_errors_and_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(
        {
            ("GET", list_path()): (200, [make_pr(1), make_pr(2)]),
            ("GET", compare_path(1)): (500, {"message": "boom"}),
            ("GET", compare_path(2)): (200, {"behind_by": 0}),
        }
    )
    summary = tmp_path / "summary.md"
    env = {"GH_TOKEN": "t", "GITHUB_REPOSITORY": REPO, "GITHUB_STEP_SUMMARY": str(summary)}
    assert mod.main([], env, _factory(client)) == 1
    assert "::error::PR #1 could not be checked or updated" in capsys.readouterr().out
    assert "| #2 | PR 2 | up-to-date |" in summary.read_text()


# --- workflow guards ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["update-branches"]["steps"]


def test_workflow_triggers(workflow: dict) -> None:
    triggers = workflow["on"]
    assert triggers["push"]["branches"] == ["main"]
    assert set(triggers["pull_request"]["types"]) == {"auto_merge_enabled", "labeled"}
    assert "dry_run" in triggers["workflow_dispatch"]["inputs"]


def test_workflow_permissions_read_only(workflow: dict) -> None:
    assert workflow["permissions"] == {"contents": "read"}


def test_workflow_checks_out_default_branch(workflow: dict) -> None:
    checkout = next(
        s for s in _steps(workflow) if str(s.get("uses", "")).startswith("actions/checkout")
    )
    ref = checkout["with"]["ref"]
    assert "default_branch" in ref
    assert "pull_request.head" not in ref


def test_workflow_uses_pat_not_github_token(workflow: dict) -> None:
    run_step = next(s for s in _steps(workflow) if "auto_update_prs.py" in s.get("run", ""))
    token = run_step["env"]["GH_TOKEN"]
    assert "AUTO_UPDATE_PR_TOKEN" in token
    assert "RELEASE_PLEASE_TOKEN" in token
    assert "secrets.GITHUB_TOKEN" not in token
    assert "${{" not in run_step["run"]


def test_workflow_concurrency_is_job_level_and_per_pr(workflow: dict) -> None:
    # Workflow-level concurrency would let any label event cancel a pending full sweep.
    assert "concurrency" not in workflow
    job = workflow["jobs"]["update-branches"]
    group = job["concurrency"]["group"]
    assert "pull_request.number" in group
    assert "sweep" in group
    assert job["concurrency"]["cancel-in-progress"] is False


def test_workflow_job_guard_filters_forks_and_labels(workflow: dict) -> None:
    guard = " ".join(workflow["jobs"]["update-branches"]["if"].split())
    assert "github.event.pull_request.head.repo.full_name == github.repository" in guard
    assert "github.event.label.name == 'autoupdate'" in guard
    assert "github.event.action == 'auto_merge_enabled'" in guard
    assert "github.event_name != 'pull_request'" in guard
