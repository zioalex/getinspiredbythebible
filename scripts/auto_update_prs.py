#!/usr/bin/env python3
"""Update the branch of every opted-in open PR that is behind ``main`` (BITB-165).

``main`` requires PR branches to be up to date before merging, and merge queues are unavailable
on a personal-account repository, so every PR needs a manual "Update branch" click after each
merge. This script runs whenever ``main`` moves and calls GitHub's update-branch endpoint for
each PR that opted in (auto-merge enabled, or the ``autoupdate`` label), so combined with
auto-merge the PRs merge themselves once green.

A personal access token is required, not the default ``GITHUB_TOKEN``: pushes and branch
updates made with ``GITHUB_TOKEN`` do not trigger workflows, so CI would never run on the
updated PR and auto-merge would wait forever.

Stdlib only, so the workflow needs no dependency install.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, NoReturn

OPT_IN_LABEL = "autoupdate"
PAGE_SIZE = 100
TIMEOUT_SECONDS = 30
SKIP_AUTHORS = {"dependabot[bot]": "dependabot"}
SKIP_HEAD_PREFIXES = (("release-please--", "release-please"),)
OUTCOMES = ("updated", "up-to-date", "skipped", "conflict", "dry-run", "error")
AUTH_STATUSES = (401, 403)


class AuthError(RuntimeError):
    """Token or permission problem: abort the whole run instead of trying the next PR."""


class GitHubClient:
    """Minimal GitHub REST client that returns HTTP errors instead of raising."""

    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        self.token = token
        self.api_url = api_url.rstrip("/")

    def request(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(  # noqa: S310 - fixed https API url
            f"{self.api_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "vox-quieta-auto-update-prs",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310
                return resp.status, _parse(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _parse(exc.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"{method} {path} failed: {exc}") from exc


def _parse(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


@dataclass
class Result:
    number: int
    title: str
    outcome: str
    detail: str


def _opted_in(pr: dict) -> bool:
    if pr.get("auto_merge"):
        return True
    return any(label.get("name") == OPT_IN_LABEL for label in pr.get("labels") or [])


def _skip_reason(pr: dict, repo_full_name: str, base: str) -> str | None:
    if pr.get("state") != "open":
        return "not open"
    if pr.get("draft"):
        return "draft"
    if pr["base"]["ref"] != base:
        return f"base is not {base}"
    head_repo = pr["head"].get("repo")
    if head_repo is None or head_repo["full_name"] != repo_full_name:
        return "fork"
    login = (pr.get("user") or {}).get("login", "")
    if login in SKIP_AUTHORS:
        return SKIP_AUTHORS[login]
    for prefix, reason in SKIP_HEAD_PREFIXES:
        if pr["head"]["ref"].startswith(prefix):
            return reason
    return None


def is_eligible(pr: dict, repo_full_name: str, base: str) -> tuple[bool, str]:
    reason = _skip_reason(pr, repo_full_name, base)
    if reason:
        return False, reason
    if not _opted_in(pr):
        return False, f"not opted in (enable auto-merge or add the '{OPT_IN_LABEL}' label)"
    return True, "eligible"


def _message(body: Any) -> str:
    if isinstance(body, dict) and body.get("message"):
        return str(body["message"])
    return "no message"


def _raise(what: str, status: int, body: Any) -> NoReturn:
    error = AuthError if status in AUTH_STATUSES else RuntimeError
    raise error(f"{what} failed: HTTP {status}: {_message(body)}")


def list_open_prs(client: GitHubClient, repo: str, base: str) -> list[dict]:
    prs: list[dict] = []
    page = 1
    while True:
        path = f"/repos/{repo}/pulls?state=open&base={base}&per_page={PAGE_SIZE}&page={page}"
        status, body = client.request("GET", path)
        if status != 200:
            _raise("listing PRs", status, body)
        prs.extend(body)
        if len(body) < PAGE_SIZE:
            return prs
        page += 1


def _fetch_pr(client: GitHubClient, repo: str, number: int) -> dict:
    status, body = client.request("GET", f"/repos/{repo}/pulls/{number}")
    if status != 200:
        _raise(f"fetching PR #{number}", status, body)
    return body


def _behind_by(client: GitHubClient, repo: str, base: str, pr: dict) -> int:
    sha = pr["head"]["sha"]
    # per_page=1: only behind_by is needed, not the full commit/file listing.
    status, body = client.request("GET", f"/repos/{repo}/compare/{base}...{sha}?per_page=1")
    if status != 200:
        _raise(f"comparing PR #{pr['number']}", status, body)
    if not isinstance(body, dict) or not isinstance(body.get("behind_by"), int):
        raise RuntimeError(f"comparing PR #{pr['number']} returned no behind_by")
    return body["behind_by"]


def _update(client: GitHubClient, repo: str, pr: dict, behind: int) -> Result:
    number, title = pr["number"], pr["title"]
    status, body = client.request(
        "PUT",
        f"/repos/{repo}/pulls/{number}/update-branch",
        {"expected_head_sha": pr["head"]["sha"]},
    )
    if status == 202:
        return Result(number, title, "updated", f"{behind} commits behind")
    if status == 422:
        return Result(number, title, "conflict", _message(body))
    _raise(f"updating PR #{number}", status, body)


def _process_pr(client: GitHubClient, repo: str, base: str, pr: dict, dry_run: bool) -> Result:
    number, title = pr["number"], pr["title"]
    eligible, reason = is_eligible(pr, repo, base)
    if not eligible:
        return Result(number, title, "skipped", reason)
    behind = _behind_by(client, repo, base, pr)
    if behind == 0:
        return Result(number, title, "up-to-date", "")
    if dry_run:
        return Result(number, title, "dry-run", f"{behind} commits behind")
    return _update(client, repo, pr, behind)


def process(
    client: GitHubClient,
    repo: str,
    base: str,
    only_pr: int | None = None,
    dry_run: bool = False,
) -> list[Result]:
    prs = [_fetch_pr(client, repo, only_pr)] if only_pr else list_open_prs(client, repo, base)
    results = []
    for pr in prs:
        try:
            results.append(_process_pr(client, repo, base, pr, dry_run))
        except AuthError:
            raise
        except RuntimeError as exc:
            # One PR's transient failure must not hide the others or lose the report.
            results.append(Result(pr["number"], pr["title"], "error", str(exc)))
    return results


def render_summary(results: list[Result], base: str) -> str:
    lines = [f"## Auto-update PR branches (base `{base}`)", ""]
    if results:
        lines += ["| PR | Title | Outcome | Detail |", "| --- | --- | --- | --- |"]
        for r in results:
            title = r.title.replace("|", "\\|")
            lines.append(f"| #{r.number} | {title} | {r.outcome} | {r.detail} |")
    else:
        lines.append("No open PRs.")
    counts = ", ".join(f"{o}: {sum(r.outcome == o for r in results)}" for o in OUTCOMES)
    return "\n".join(lines + ["", counts, ""])


def _parse_args(argv: list[str] | None, env: Mapping[str, str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=env.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--base", default=env.get("BASE_BRANCH") or "main")
    parser.add_argument("--pr", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _report(results: list[Result], base: str, env: Mapping[str, str]) -> None:
    for r in results:
        print(f"#{r.number} {r.title}: {r.outcome} {r.detail}".rstrip())
        if r.outcome == "conflict":
            print(
                f"::warning::PR #{r.number} could not be updated automatically: "
                f"{r.detail} — resolve manually"
            )
        elif r.outcome == "error":
            print(f"::error::PR #{r.number} could not be checked or updated: {r.detail}")
    summary_path = env.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(render_summary(results, base))


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    client_factory: Callable[..., GitHubClient] = GitHubClient,
) -> int:
    env = os.environ if env is None else env
    args = _parse_args(argv, env)
    token = env.get("GH_TOKEN", "")
    if not token:
        print(
            "::error::GH_TOKEN is empty. Set repository secret AUTO_UPDATE_PR_TOKEN "
            "(fine-grained PAT with Contents: read/write and Pull requests: read/write on this "
            "repository). The default GITHUB_TOKEN cannot be used because branch updates it "
            "makes do not trigger CI."
        )
        return 1
    if not args.repo:
        print("::error::No repository given (--repo or GITHUB_REPOSITORY).")
        return 1
    client = client_factory(token, env.get("GITHUB_API_URL") or "https://api.github.com")
    try:
        results = process(client, args.repo, args.base, args.pr, args.dry_run)
    except RuntimeError as exc:
        print(f"::error::{exc}")
        return 1
    _report(results, args.base, env)
    return 1 if any(r.outcome == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
