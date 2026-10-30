#!/usr/bin/env python3
"""Fail a PR that adds a backlog story file whose BITB-NNN id is already claimed (BITB-235).

`AGENTS.md` (*Backlog Hygiene*) says story IDs are sequential: take the highest `BITB-NNN` on
`main` and add one. That only sees `main`, so two PRs opened concurrently pick the same number
(BITB-235: the header story was renumbered 206 → 212 → 213 → 219 in two days; PRs #1203 and
#1215 both claimed BITB-241 on 2026-10-26). `scripts/check_backlog_story_ids.py` (BITB-111)
only guards the *merged* tree, so it notices a collision only after the second PR lands. This
check catches it before merge, on the PR itself.

What it checks (only files the PR ADDS — modifications and deletions claim nothing):

1. Files added under `docs/BACKLOG_STORIES/BITB-NNN-*.md` vs the merge-base with the base
   branch (both sides enumerated with `git ls-tree`, so a rename detected by git is still an
   add + delete here — the semantics are pure path arithmetic, not diff heuristics).
2. The same id added twice *within* this PR.
3. Each added id against the base branch tip (`git ls-tree`): a base file this PR also
   deletes releases its claim — a renumber (delete `BITB-X-old.md`, add `BITB-Y-new.md`) or a
   rename-in-place (delete `BITB-X-old.md`, add `BITB-X-new.md`) must NOT be flagged just
   because the id existed on the base branch. The subtraction is by path, not id: if the base
   branch renamed the same-numbered file after this PR branched, the renamed base file keeps
   its claim and the collision is (correctly) still reported.
4. Each added id against every OTHER open PR on the same base that adds story files, via the
   GitHub API (`GITHUB_TOKEN`, needs `pull-requests: read`). Fork PRs are read through the
   same API like any other; a PR whose files cannot be fetched at all (e.g. deleted mid-run)
   is skipped with a `::warning::` rather than failing the whole check.

Ids under `docs/DONE/` are deliberately out of scope: cross-directory uniqueness is
BITB-111's job. This script only polices *new claims by open PRs*, which BITB-111 cannot see.

Usage (defaults match the GitHub Actions environment; see
`.github/workflows/story-id-check.yml`):

    python3 scripts/check_story_ids.py --help
    python3 scripts/check_story_ids.py \
        --base-ref origin/main --base-branch main \
        --pr 1234 --repo owner/name --token "$GITHUB_TOKEN"

Exit codes: 0 = no conflicts, 1 = duplicate claim(s) found, 2 = cannot run (git/API failure).

Stdlib only, so the workflow needs no dependency install. Offline unit tests:
`python -m pytest scripts/test_check_story_ids.py -v`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

STORY_DIR = "docs/BACKLOG_STORIES"
PAGE_SIZE = 100
TIMEOUT_SECONDS = 30
# PR-file statuses that create a NEW claim on an id. "modified" keeps whatever claim the base
# file already has (the base-branch comparison covers it); "removed" releases a claim.
ADDED_STATUSES = frozenset({"added", "renamed", "copied"})

_STORY_PATH_RE = re.compile(r"^docs/BACKLOG_STORIES/(BITB-\d+)-[^/]+\.md$")
_ID_DIGITS_RE = re.compile(r"\d+")

_AGENTS_RULE = (
    'Per AGENTS.md -> Backlog Hygiene ("Story IDs are sequential"): the FIRST claimant keeps '
    "the ID — the later PR renumbers its story before merging (rename the story file and "
    "update every docs/BACKLOG.md reference in that PR). If you opened first, say so in the "
    "other PR and have *it* renumber; do not just retry CI hoping it went away."
)


class GitError(RuntimeError):
    """A git command failed in a way the check cannot proceed past."""


class AuthError(RuntimeError):
    """Token or permission problem: abort the whole run instead of trying the next PR."""


@dataclass(frozen=True)
class Claim:
    """One other place a story id is already claimed."""

    where: str  # e.g. "the base branch (origin/main)" or "open PR #1203"
    file: str


@dataclass(frozen=True)
class Conflict:
    story_id: str
    added_files: tuple[str, ...]  # every file this PR adds under this id
    claims: tuple[Claim, ...]  # every other place the id is claimed


def story_id_from_path(path: str) -> str | None:
    """The BITB-NNN id a path claims, or None when the path is not a backlog story file."""
    match = _STORY_PATH_RE.match(path)
    return match.group(1) if match else None


def _sort_key(story_id: str) -> tuple[int, str]:
    digits = _ID_DIGITS_RE.search(story_id)
    return (int(digits.group()) if digits else 0, story_id)


def _claims_for_story_id(
    story_id: str,
    added_files: Sequence[str],
    surviving_base_paths: Sequence[str],
    other_pr_added_paths: Mapping[int, Iterable[str]],
    base_ref: str,
) -> list[Claim]:
    """Every other place ``story_id`` is claimed, in a stable order:
    in-PR duplicates first, then the base branch, then other open PRs by number."""
    claims: list[Claim] = []
    if len(added_files) > 1:
        claims.extend(Claim("this PR itself (duplicate add)", f) for f in added_files[1:])
    for base_path in surviving_base_paths:
        if story_id_from_path(base_path) == story_id:
            claims.append(Claim(f"the base branch ({base_ref})", base_path))
    for pr_number in sorted(other_pr_added_paths):
        for pr_path in other_pr_added_paths[pr_number]:
            if story_id_from_path(pr_path) == story_id:
                claims.append(Claim(f"open PR #{pr_number}", pr_path))
    return claims


def find_conflicts(
    added_paths: Iterable[str],
    deleted_paths: Iterable[str],
    base_paths: Iterable[str],
    other_pr_added_paths: Mapping[int, Iterable[str]],
    base_ref: str,
) -> list[Conflict]:
    """Pure decision core of the check — no git, no network, fully deterministic.

    ``added_paths``/``deleted_paths`` are the story files this PR adds/deletes relative to the
    merge-base; ``base_paths`` are the story files on the base branch *tip*; ``other_pr_added_paths``
    maps each other open PR number to the story files it adds.
    """
    added_by_id: dict[str, list[str]] = {}
    for path in added_paths:
        story_id = story_id_from_path(path)
        if story_id is not None:
            added_by_id.setdefault(story_id, []).append(path)

    deleted = set(deleted_paths)
    # A base file this PR deletes releases its id (renumber / rename-in-place). Subtraction is
    # by path: a same-numbered file the base branch renamed after this PR branched survives.
    surviving_base_paths = [p for p in base_paths if p not in deleted]

    conflicts: list[Conflict] = []
    for story_id in sorted(added_by_id, key=_sort_key):
        claims = _claims_for_story_id(
            story_id, added_by_id[story_id], surviving_base_paths, other_pr_added_paths, base_ref
        )
        if claims:
            conflicts.append(
                Conflict(story_id, tuple(sorted(added_by_id[story_id])), tuple(claims))
            )
    return conflicts


def render_report(conflicts: Sequence[Conflict]) -> str:
    """The full failure message: one block per conflicting id, then the AGENTS.md rule."""
    lines = [
        f"FAIL: this PR claims {len(conflicts)} story ID(s) that are already claimed:",
        "",
    ]
    for conflict in conflicts:
        added = " and ".join(conflict.added_files)
        lines.append(f"  * {conflict.story_id} — added by this PR as {added}:")
        lines.append("      the ID is already claimed by:")
        for claim in conflict.claims:
            lines.append(f"        - {claim.where}: {claim.file}")
        lines.append("")
    lines.append(_AGENTS_RULE)
    return "\n".join(lines)


# --- git layer -----------------------------------------------------------------------------


def run_git(*args: str) -> str:
    """Run one git command in the repo and return its stdout, raising GitError on failure."""
    proc = subprocess.run(["git", *args], capture_output=True, text=True, check=False, timeout=60)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        raise GitError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout


def git_ls_tree_story_paths(rev: str) -> list[str]:
    """Every `docs/BACKLOG_STORIES/BITB-*.md` path in the tree of ``rev`` (may be empty)."""
    out = run_git("ls-tree", "-r", "--name-only", "-z", rev, "--", STORY_DIR)
    return [path for path in out.split("\0") if path]


def pr_added_and_deleted_story_paths(base_ref: str) -> tuple[list[str], list[str]]:
    """Story files this PR adds/deletes, as path arithmetic against the merge-base.

    Both the merge-base tree and HEAD are enumerated with `git ls-tree` and set-compared:
    added = HEAD paths missing from the merge-base, deleted = merge-base paths missing from
    HEAD. No `git diff`, so rename detection cannot blur the two directions.
    """
    merge_base = run_git("merge-base", base_ref, "HEAD").strip()
    if not merge_base:
        raise GitError(f"no merge-base between {base_ref} and HEAD — is the branch orphaned?")
    base_snapshot = set(git_ls_tree_story_paths(merge_base))
    head_snapshot = set(git_ls_tree_story_paths("HEAD"))
    return sorted(head_snapshot - base_snapshot), sorted(base_snapshot - head_snapshot)


# --- github layer --------------------------------------------------------------------------


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
                "User-Agent": "vox-quieta-check-story-ids",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310
                return resp.status, _parse_json(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _parse_json(exc.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"{method} {path} failed: {exc}") from exc


def _parse_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _paginated_list(client: GitHubClient, first_page_path: str, what: str) -> list[dict]:
    """GET a paginated list endpoint, returning [] for a valid-but-empty answer."""
    items: list[dict] = []
    page = 1
    while True:
        path = f"{first_page_path}&page={page}"
        status, payload = client.request("GET", path)
        if status in (401, 403):
            raise AuthError(
                f"{what} failed with HTTP {status} — GITHUB_TOKEN needs pull-requests: read"
            )
        if status != 200 or not isinstance(payload, list):
            raise RuntimeError(f"{what} failed with HTTP {status}")
        items.extend(entry for entry in payload if isinstance(entry, dict))
        if len(payload) < PAGE_SIZE:
            return items
        page += 1


def list_open_prs(client: GitHubClient, repo: str, base_branch: str) -> list[dict]:
    """Every open PR targeting ``base_branch`` (all authors, drafts and forks included —
    drafts and fork PRs claim story IDs just as hard as any other PR)."""
    return _paginated_list(
        client,
        f"/repos/{repo}/pulls?state=open&base={base_branch}&per_page={PAGE_SIZE}",
        "listing open PRs",
    )


def pr_added_story_paths(client: GitHubClient, repo: str, pr_number: int) -> list[str]:
    """Story files PR ``pr_number`` adds, from the PR files API (works for fork PRs too)."""
    entries = _paginated_list(
        client,
        f"/repos/{repo}/pulls/{pr_number}/files?per_page={PAGE_SIZE}",
        f"fetching files of PR #{pr_number}",
    )
    return [
        str(entry["filename"])
        for entry in entries
        if entry.get("status") in ADDED_STATUSES and story_id_from_path(str(entry["filename"]))
    ]


def other_open_pr_claims(
    client: GitHubClient, repo: str, base_branch: str, current_pr: int
) -> dict[int, list[str]]:
    """Map every OTHER open PR to the story files it adds, skipping unreadable PRs loudly."""
    claims: dict[int, list[str]] = {}
    for pr in list_open_prs(client, repo, base_branch):
        number = pr.get("number")
        if not isinstance(number, int) or number == current_pr:
            continue
        try:
            added = pr_added_story_paths(client, repo, number)
        except RuntimeError as exc:
            # Only skip the PR that is *genuinely unreadable* (e.g. closed between the list
            # call and this fetch); a claim we cannot inspect is one we cannot report.
            print(f"::warning::skipping PR #{number} — {exc}", file=sys.stderr)
            continue
        if added:
            claims[number] = added
    return claims


# --- entry point ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_story_ids.py",
        description=(
            "Fail when this PR adds docs/BACKLOG_STORIES/BITB-NNN-*.md files whose IDs are "
            "already claimed on the base branch or by another open PR (BITB-235)."
        ),
        epilog=_AGENTS_RULE,
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="git ref of the base branch (default: %(default)s)",
    )
    parser.add_argument(
        "--base-branch",
        default="main",
        help="base branch name for the open-PR query (default: %(default)s)",
    )
    parser.add_argument(
        "--pr",
        type=int,
        default=0,
        help="this PR's number, so its own claims are excluded (0 or omitted = local run)",
    )
    parser.add_argument(
        "--repo",
        default="",
        help="owner/name of the repository (default: $GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--token",
        default="",
        help="GitHub API token with pull-requests: read (default: $GITHUB_TOKEN)",
    )
    return parser


def _pr_context_error(args: argparse.Namespace) -> str | None:
    """Why the open-PR part of the check cannot run given these args, or None if it can."""
    if not args.pr:
        return None
    if not args.repo:
        return "--repo is missing, so other open PRs cannot be queried."
    if not args.token:
        return "--token is missing, so other open PRs cannot be queried."
    return None


def _gather_claims(
    args: argparse.Namespace, client_factory: Callable[[str], GitHubClient]
) -> tuple[list[str], dict[int, list[str]]]:
    """Story files on the base branch tip plus the adds of every other open PR.

    Raises GitError/AuthError; the caller decides how the run must end on each.
    """
    base_paths = git_ls_tree_story_paths(args.base_ref)
    other_claims: dict[int, list[str]] = {}
    if args.pr:
        other_claims = other_open_pr_claims(
            client_factory(args.token), args.repo, args.base_branch, args.pr
        )
    return base_paths, other_claims


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    client_factory: Callable[[str], GitHubClient] = GitHubClient,
) -> int:
    env = os.environ if env is None else env
    args = build_parser().parse_args(argv)
    if not args.repo:
        args.repo = env.get("GITHUB_REPOSITORY", "")
    if not args.token:
        args.token = env.get("GITHUB_TOKEN", "")

    try:
        added, deleted = pr_added_and_deleted_story_paths(args.base_ref)
    except GitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not added:
        print(f"OK: this PR adds no {STORY_DIR}/ story files — nothing to check.")
        return 0

    error = _pr_context_error(args)
    if error:
        print(f"ERROR: --pr given but {error}", file=sys.stderr)
        return 2

    try:
        base_paths, other_claims = _gather_claims(args, client_factory)
    except (GitError, AuthError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.pr:
        print("NOTE: no --pr given — only the base branch is checked, other open PRs are not.")

    conflicts = find_conflicts(added, deleted, base_paths, other_claims, args.base_ref)
    if not conflicts:
        ids = ", ".join(sorted({story_id_from_path(p) or p for p in added}, key=_sort_key))
        print(f"OK: this PR adds story file(s) with id(s) {ids}, and none is already claimed.")
        return 0

    for conflict in conflicts:
        places = " and ".join(claim.where for claim in conflict.claims)
        print(f"::error ::{conflict.story_id} is already claimed by {places}")
    print(render_report(conflicts), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
