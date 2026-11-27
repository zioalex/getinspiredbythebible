#!/usr/bin/env python3
"""Classify a pull request by the product kind of the stories it implements (BITB-366).

Every PR title names the backlog stories it implements (`BITB-NNN`). Each story's front matter
carries a `kind` (feature, nfr, fix, chore, spike) and optionally a release `milestone` (BITB-368,
docs/backlog/LEGEND.md). This script reads the title, finds those stories in the checked-out tree
and decides:

* the PR's kind (one per PR: a PR delivers one outcome) -> the workflow applies `kind/<kind>`;
* the PR's milestone (`R1`, ...) -> the workflow assigns the GitHub milestone `R1: <outcome>`;
* whether the conventional-commit type fits the kind. The type drives the version bump and the
  CHANGELOG; the kind says what the change means for the product. Agent and CI tooling filed as
  `fix(opencode)` lands in the user-facing release notes, so `chore`/`spike` work may not use
  `feat`/`fix`.

Bot PRs (Dependabot, GitHub Actions) and release-please Release PRs are skipped: they implement no
story. A story created before the `kind` cut-over (backlog.KIND_REQUIRED_FROM) that still has no
kind only produces a warning, so PRs opened before this check existed are not turned red.

Usage (see .github/workflows/pr-kind.yml):

    python3 scripts/pr_kind.py --title "fix(api): ... (BITB-321)" --author someone \
        [--head-ref branch] [--json] [--github-output "$GITHUB_OUTPUT"]

Exit codes: 0 = OK (warnings allowed), 1 = the PR breaks a rule. Stdlib only.
Tests: python -m pytest scripts/test_pr_kind.py -v
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import backlog  # noqa: E402

# Which conventional-commit types each kind may use (docs/backlog/LEGEND.md). `revert` and
# `merge` describe how a change landed, not what it is, so they fit every kind.
ALLOWED_TYPES: dict[str, frozenset[str]] = {
    "feature": frozenset({"feat"}),
    "nfr": frozenset({"feat", "fix", "perf"}),
    "fix": frozenset({"fix"}),
    "chore": frozenset({"chore", "ci", "build", "docs", "test", "refactor", "style"}),
    "spike": frozenset({"chore", "docs"}),
}
ANY_KIND_TYPES = frozenset({"revert", "merge"})

# Open, non-draft PRs labelled with a product kind before a new one is a warning (owner, 2026-11-26;
# to be revisited). Read by the workflow so the number lives in one place.
WIP_LIMIT = 8

_TITLE_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?!?: (?P<subject>.+)$")
_RELEASE_PLEASE_PREFIX = "release-please--"


@dataclass
class Result:
    skip: bool = False
    kind: str = ""
    milestone: str = ""
    commit_type: str = ""
    stories: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_product(self) -> bool:
        return self.kind in backlog.PRODUCT_KINDS


def is_automation(author: str, head_ref: str) -> bool:
    """Bot PRs and release-please Release PRs implement no story."""
    return author.endswith("[bot]") or head_ref.startswith(_RELEASE_PLEASE_PREFIX)


def classify(  # noqa: C901
    title: str, author: str, head_ref: str, stories: list[backlog.Story]
) -> Result:
    result = Result()
    if is_automation(author, head_ref):
        result.skip = True
        result.kind = "chore"
        return result

    match = _TITLE_RE.match(title.strip())
    if not match:
        result.errors.append(
            f"title {title!r} is not a conventional commit (`type(scope): summary (BITB-NNN)`)"
        )
        return result
    result.commit_type = match.group("type")

    ids = backlog.expand_ids(title)
    result.stories = ids
    if not ids:
        result.errors.append(
            "the title names no BITB-NNN story — every change has a story (AGENTS.md -> "
            "Backlog Hygiene); add its id to the title, e.g. `... (BITB-123)`"
        )
        return result

    by_id = {s.id: s for s in stories}
    kinds: dict[str, list[str]] = {}
    milestones: dict[str, list[str]] = {}
    for story_id in ids:
        story = by_id.get(story_id)
        if story is None:
            result.errors.append(
                f"{story_id} has no story file in docs/BACKLOG_STORIES/ or docs/DONE/ — "
                "fix the id in the title or add the story to this PR"
            )
            continue
        kind = story.meta.get("kind")
        if not kind:
            created = str(story.meta.get("created", ""))
            message = (
                f"{story_id} has no `kind` in its front matter — add `kind: <"
                + "|".join(backlog.KINDS)
                + ">` after `priority` (docs/backlog/LEGEND.md)"
            )
            if created >= backlog.KIND_REQUIRED_FROM:
                result.errors.append(message)
            else:
                result.warnings.append(message)
            continue
        kinds.setdefault(str(kind), []).append(story_id)
        if story.meta.get("milestone"):
            milestones.setdefault(str(story.meta["milestone"]), []).append(story_id)

    if len(kinds) > 1:
        detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in sorted(kinds.items()))
        result.errors.append(
            f"the stories in this PR have different kinds ({detail}) — one PR delivers one "
            "outcome; split it, or fix a story's `kind`"
        )
    elif kinds:
        result.kind = next(iter(kinds))
        allowed = ALLOWED_TYPES.get(result.kind, frozenset()) | ANY_KIND_TYPES
        if result.commit_type not in allowed:
            result.errors.append(
                f"a `{result.kind}` change may not use the `{result.commit_type}:` type — use "
                + " / ".join(f"`{t}:`" for t in sorted(ALLOWED_TYPES[result.kind]))
                + " (docs/backlog/LEGEND.md). `feat`/`fix` put the change in the release "
                "notes users read."
            )

    if len(milestones) > 1:
        detail = "; ".join(f"{m}: {', '.join(v)}" for m, v in sorted(milestones.items()))
        result.errors.append(
            f"the stories in this PR belong to different milestones ({detail}) — split the PR "
            "or move a story"
        )
    elif milestones:
        result.milestone = next(iter(milestones))
    return result


def _write_github_output(path: str, result: Result) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"skip={'true' if result.skip else 'false'}\n")
        handle.write(f"kind={result.kind}\n")
        handle.write(f"milestone={result.milestone}\n")
        handle.write(f"product={'true' if result.is_product else 'false'}\n")
        handle.write(f"wip_limit={WIP_LIMIT}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pr_kind.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--root", type=Path, default=backlog._DEFAULT_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("--github-output", help="append skip/kind/milestone/product here")
    args = parser.parse_args(argv)

    stories = [] if is_automation(args.author, args.head_ref) else backlog.load_all(args.root)
    result = classify(args.title, args.author, args.head_ref, stories)
    if args.github_output:
        _write_github_output(args.github_output, result)
    if args.json:
        print(json.dumps({**asdict(result), "product": result.is_product}, sort_keys=True))
    elif result.skip:
        print("Skipped: bot or release PR (kind/chore).")
    else:
        stories_txt = ", ".join(result.stories) or "none"
        print(
            f"kind={result.kind or '-'} milestone={result.milestone or '-'} stories={stories_txt}"
        )
    for warning in result.warnings:
        print(f"::warning::{warning}")
    for error in result.errors:
        print(f"::error::{error}")
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
