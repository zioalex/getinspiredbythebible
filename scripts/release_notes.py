#!/usr/bin/env python3
"""Product release notes and the release gate, from the stories in a milestone (BITB-367).

A product release is a GitHub milestone titled ``R<n>: <outcome>`` (docs/RELEASE_PROCESS.md,
"Product releases"). Its stories carry ``milestone: R<n>`` in their front matter (BITB-368).
This script turns those stories into notes for people who never read a commit, and tells the
Release PR whether the milestone is done:

    python3 scripts/release_notes.py notes --milestone R1 [--title "R1: ..."] [--outcome TEXT]
    python3 scripts/release_notes.py gate --milestone R1
    python3 scripts/release_notes.py current
    python3 scripts/release_notes.py user --milestone R1
    python3 scripts/release_notes.py check [--version 1.63.0]
    gh api repos/OWNER/REPO/milestones | python3 scripts/release_notes.py github-milestone

* ``notes``: the outcome, then "New features", "Quality & reliability" (nfr) and "Fixes" — one
  line per *done* story — a one-line count of internal changes (chore, spike), and "Still open"
  for product stories that move to the next release.
* ``gate``: exit 1 while any story in the milestone is not done or cancelled.
* ``current``: the lowest ``R<n>`` that still has open stories (empty when none).
* ``github-milestone``: from the GitHub milestones JSON on stdin, the lowest open ``R<n>: ...``
  as JSON ``{"number", "key", "title", "outcome"}`` (``{}`` when there is none).
* ``user``: a first English draft of the end-user What's New for a milestone (BITB-175) — one
  plain bullet per done feature/fix story — to edit, translate and save as
  ``release-notes/<version>/<locale>.md``.
* ``check``: validate every ``release-notes/<version>/`` folder (all 11 locales, at most 500
  characters, bullets only, no story ids or code); ``--version X.Y.Z`` also requires that folder.

The developer CHANGELOG.md stays as release-please writes it. Stdlib only.
Tests: python -m pytest scripts/test_release_notes.py -v
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import backlog  # noqa: E402

SECTIONS: tuple[tuple[str, str], ...] = (
    ("feature", "New features"),
    ("nfr", "Quality & reliability"),
    ("fix", "Fixes"),
)
_GITHUB_TITLE_RE = re.compile(r"^(R[1-9]\d*):\s*(.+)$")
_OUTCOME_RE = re.compile(r"^\s*Outcome:\s*(.+?)\s*$", re.IGNORECASE)

# End-user What's New (BITB-175): one file per release and locale, shown in the web modal, the
# Android sheet and the Play Store "What's new" field. The locales are the app's UI languages
# (frontend/messages/*.json). 500 characters is the Play Store limit per language.
USER_NOTES_DIR = "release-notes"
LOCALES: tuple[str, ...] = ("en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko")
MAX_USER_NOTE_CHARS = 500
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_TITLE_ID_RE = re.compile(r"\s*\(?BITB-\d+(?:/\d+)*\)?")
_FORBIDDEN_IN_USER_NOTES = (
    (re.compile(r"BITB-\d+", re.IGNORECASE), "a story id"),
    (re.compile(r"`"), "code formatting"),
    (re.compile(r"\(#\d+\)|https?://github\.com", re.IGNORECASE), "a PR reference"),
)


def in_milestone(stories: list[backlog.Story], milestone: str) -> list[backlog.Story]:
    wanted = milestone.upper()
    return sorted((s for s in stories if s.milestone == wanted), key=backlog.sort_key)


def open_stories(stories: list[backlog.Story]) -> list[backlog.Story]:
    return [s for s in stories if s.status not in backlog.CLOSED_STATUSES]


def _milestone_number(key: str) -> int:
    return int(key[1:])


def current_milestone(stories: list[backlog.Story]) -> str:
    keys = {s.milestone for s in open_stories(stories) if s.milestone != "-"}
    return min(keys, key=_milestone_number) if keys else ""


def render_notes(
    stories: list[backlog.Story], milestone: str, title: str = "", outcome: str = ""
) -> str:
    picked = in_milestone(stories, milestone)
    done = [s for s in picked if s.status == "done"]
    lines = [f"## {title or milestone.upper()}", ""]
    if outcome:
        lines += [outcome, ""]
    wrote_any = False
    for kind, heading in SECTIONS:
        group = [s for s in done if s.kind == kind]
        if not group:
            continue
        wrote_any = True
        lines += [f"### {heading}", ""]
        lines += [f"- {s.title} ({s.id})" for s in group]
        lines.append("")
    if not wrote_any:
        lines += ["_No product changes are done in this milestone yet._", ""]
    internal = [s for s in done if s.kind not in backlog.PRODUCT_KINDS]
    if internal:
        noun = "change" if len(internal) == 1 else "changes"
        lines += [
            f"_Plus {len(internal)} internal {noun} (tooling, tests, docs): "
            + ", ".join(s.id for s in internal)
            + "._",
            "",
        ]
    moved = [s for s in open_stories(picked) if s.kind in backlog.PRODUCT_KINDS]
    if moved:
        lines += ["### Still open (moves to the next release)", ""]
        lines += [f"- {s.title} ({s.id}, {s.status})" for s in moved]
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def gate(stories: list[backlog.Story], milestone: str) -> tuple[bool, str]:
    picked = in_milestone(stories, milestone)
    if not picked:
        return True, f"OK: no stories carry milestone {milestone.upper()}.\n"
    pending = open_stories(picked)
    if not pending:
        return True, f"OK: {milestone.upper()} is complete ({len(picked)} stories).\n"
    lines = [f"{milestone.upper()} is not complete: {len(pending)} of {len(picked)} stories open."]
    lines += [f"- {s.id} {s.status} ({s.kind}): {s.title}" for s in pending]
    return False, "\n".join(lines) + "\n"


def draft_user_notes(stories: list[backlog.Story], milestone: str) -> str:
    """English draft: one bullet per done feature, then fix, story in the milestone."""
    done = [s for s in in_milestone(stories, milestone) if s.status == "done"]
    picked = [s for kind in ("feature", "fix") for s in done if s.kind == kind]
    if not picked:
        return ""
    return "".join(f"- {_TITLE_ID_RE.sub('', s.title).strip()}\n" for s in picked)


def _check_note_file(path: Path, rel: str) -> list[str]:
    """Problems with one ``release-notes/<version>/<locale>.md`` file."""
    if not path.is_file():
        return [f"{rel}: missing (every release needs all 11 languages)"]
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return [f"{rel}: empty"]
    errors = []
    if len(text) > MAX_USER_NOTE_CHARS:
        errors.append(f"{rel}: {len(text)} characters, the Play Store allows {MAX_USER_NOTE_CHARS}")
    bad = next((ln for ln in text.splitlines() if ln.strip() and not ln.startswith("- ")), None)
    if bad is not None:
        errors.append(f"{rel}: every line must be a '- ' bullet: {bad!r}")
    for pattern, what in _FORBIDDEN_IN_USER_NOTES:
        if pattern.search(text):
            errors.append(f"{rel}: contains {what}; users never see those")
    return errors


def check_user_notes(root: Path, required_version: str = "") -> list[str]:
    """Problems with ``release-notes/<version>/<locale>.md``, as ``path: problem`` lines."""
    base = root / USER_NOTES_DIR
    errors: list[str] = []
    versions = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    if required_version and not (base / required_version).is_dir():
        errors.append(
            f"{USER_NOTES_DIR}/{required_version}/: missing — write the user What's New for "
            "this release (docs/RELEASE_PROCESS.md, 'Writing the user What's New')"
        )
    for folder in versions:
        rel = f"{USER_NOTES_DIR}/{folder.name}"
        if not _VERSION_RE.match(folder.name):
            errors.append(f"{rel}/: folder name must be a release version like 1.63.0")
            continue
        for locale in LOCALES:
            errors += _check_note_file(folder / f"{locale}.md", f"{rel}/{locale}.md")
        extra = sorted(p.name for p in folder.glob("*.md") if p.stem not in LOCALES)
        for name in extra:
            errors.append(f"{rel}/{name}: not one of the app's locales ({', '.join(LOCALES)})")
    return errors


def pick_github_milestone(milestones: list[dict]) -> dict:
    """The lowest open ``R<n>: ...`` milestone, with its outcome line, or ``{}``."""
    found = []
    for item in milestones:
        if item.get("state", "open") != "open":
            continue
        match = _GITHUB_TITLE_RE.match(str(item.get("title", "")))
        if match:
            found.append((_milestone_number(match.group(1)), match.group(1), item))
    if not found:
        return {}
    _, key, item = min(found, key=lambda entry: entry[0])
    outcome = ""
    for line in str(item.get("description") or "").splitlines():
        hit = _OUTCOME_RE.match(line)
        if hit:
            outcome = hit.group(1)[:1].upper() + hit.group(1)[1:]
            break
    return {"number": item.get("number"), "key": key, "title": item["title"], "outcome": outcome}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release_notes.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=backlog._DEFAULT_ROOT, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    p_notes = sub.add_parser("notes", help="product release notes for a milestone")
    p_notes.add_argument("--milestone", required=True)
    p_notes.add_argument("--title", default="", help="heading, e.g. the GitHub milestone title")
    p_notes.add_argument("--outcome", default="", help="one-line outcome under the heading")
    p_gate = sub.add_parser("gate", help="exit 1 while the milestone has open stories")
    p_gate.add_argument("--milestone", required=True)
    sub.add_parser("current", help="lowest milestone that still has open stories")
    sub.add_parser("github-milestone", help="pick the current milestone from GitHub JSON on stdin")
    p_user = sub.add_parser("user", help="English draft of the end-user What's New")
    p_user.add_argument("--milestone", required=True)
    p_check = sub.add_parser("check", help="validate release-notes/<version>/<locale>.md")
    p_check.add_argument("--version", default="", help="also require this release's folder")
    args = parser.parse_args(argv)

    if args.command == "github-milestone":
        print(json.dumps(pick_github_milestone(json.load(sys.stdin)), sort_keys=True))
        return 0
    if args.command == "check":
        problems = check_user_notes(args.root, args.version)
        for problem in problems:
            print(f"::error::{problem}")
        if not problems:
            print("OK: release-notes/ is valid.")
        return 1 if problems else 0
    if getattr(args, "milestone", None) is not None and not re.fullmatch(
        r"R[1-9]\d*", args.milestone, re.IGNORECASE
    ):
        parser.error(f"--milestone: expected R1, R2, ..., got {args.milestone!r}")
    stories = backlog.load_all(args.root)
    if args.command == "notes":
        sys.stdout.write(render_notes(stories, args.milestone, args.title, args.outcome))
        return 0
    if args.command == "user":
        draft = draft_user_notes(stories, args.milestone)
        sys.stdout.write(draft or f"(no done feature or fix stories in {args.milestone.upper()})\n")
        return 0
    if args.command == "gate":
        ok, report = gate(stories, args.milestone)
        sys.stdout.write(report)
        return 0 if ok else 1
    print(current_milestone(stories))
    return 0


if __name__ == "__main__":
    sys.exit(main())
