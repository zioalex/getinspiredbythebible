#!/usr/bin/env python3
"""Guard against docs/BACKLOG.md status drift from docs/BACKLOG_STORIES/ (BITB-153).

`docs/BACKLOG.md` carries its own copy of every story's heading emoji and `**Status:**`
line, duplicated from the canonical `docs/BACKLOG_STORIES/BITB-NNN-*.md` file. Nothing kept
the two in sync: a story finished and marked `✅ Done` in its own file, but its
`docs/BACKLOG.md` section was never updated, so the index went on advertising it as
`🎯 Todo`. A dedup pass that trusts the index (as `AGENTS.md` -> Backlog Hygiene tells every
session to do before picking up work) can then treat already-shipped work as open — which is
exactly what nearly happened during the 2026-09-14 backlog audit that found five such stories
(BITB-027, BITB-028, BITB-029, BITB-047, BITB-100) all done in their own file but still `🎯`
in the index. See `docs/BACKLOG_STORIES/BITB-153-backlog-status-index-drift.md`.

This guard checks one direction only, the one that actually wastes work: a story file marked
`✅ Done` (or `✅ Complete`) whose `docs/BACKLOG.md` section heading is not also `✅`. It does
not police the reverse (a `docs/BACKLOG.md` heading claiming `✅` ahead of its story file, or
any of the other status values) — those don't cause a finished story to be picked up again,
and folding them in would trade a sharp, evidenced check for a fuzzy one.

A story file with no `docs/BACKLOG.md` entry at all is a different, already-guarded problem
(`scripts/check_backlog_story_ids.py`, BITB-111) and is skipped here to avoid duplicate
errors for the same root cause. Likewise, an ID that currently maps to *more than one* file
in `docs/BACKLOG_STORIES/` (a live collision, BITB-111's other failure mode) is skipped
entirely: this guard cannot tell which file a `docs/BACKLOG.md` heading actually belongs to
once two stories share an ID, and guessing risks marking the wrong story's entry Done.

Usage:

    python3 scripts/check_backlog_status_sync.py

Exits 0 and prints a summary when nothing has drifted. Exits 1 and prints one error per
drifted story otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_STORY_DIR = _REPO_ROOT / "docs" / "BACKLOG_STORIES"
_BACKLOG_MD = _REPO_ROOT / "docs" / "BACKLOG.md"

_ID_FROM_FILENAME = re.compile(r"^(BITB-\d+)-")
_STATUS_LINE = re.compile(r"^\*\*Status:\*\*\s*(\S+)", re.MULTILINE)
_DONE_MARK = "✅"


def _relpath(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _story_is_done(story_text: str) -> bool:
    match = _STATUS_LINE.search(story_text)
    return bool(match) and match.group(1) == _DONE_MARK


def _find_backlog_section(backlog_text: str, story_id: str) -> str | None:
    """Return the docs/BACKLOG.md section text for ``story_id``, or None if it has none.

    A "section" runs from its own heading line up to (but not including) the next
    ``##``-``####`` heading, matching how every entry in this file is laid out.
    """
    heading_re = re.compile(rf"^(#{{2,4}})[^\n]*\b{re.escape(story_id)}\b.*$", re.MULTILINE)
    match = heading_re.search(backlog_text)
    if not match:
        return None
    level = len(match.group(1))
    next_heading_re = re.compile(rf"^#{{2,{level}}}\s", re.MULTILINE)
    next_match = next_heading_re.search(backlog_text, match.end())
    end = next_match.start() if next_match else len(backlog_text)
    return backlog_text[match.start() : end]


def _collect_story_files_by_id() -> dict[str, list[Path]]:
    by_id: dict[str, list[Path]] = {}
    for path in sorted(_STORY_DIR.glob("*.md")):
        match = _ID_FROM_FILENAME.match(path.name)
        if match:
            by_id.setdefault(match.group(1), []).append(path)
    return by_id


def check() -> list[str]:
    if not _BACKLOG_MD.is_file():
        return [f"{_relpath(_BACKLOG_MD)} does not exist — cannot verify status sync."]
    backlog_text = _BACKLOG_MD.read_text(encoding="utf-8")
    by_id = _collect_story_files_by_id()

    errors: list[str] = []
    for path in sorted(_STORY_DIR.glob("*.md")):
        match = _ID_FROM_FILENAME.match(path.name)
        if not match:
            continue
        story_id = match.group(1)
        if len(by_id[story_id]) > 1:
            continue  # live ID collision — scripts/check_backlog_story_ids.py's job (BITB-111)
        story_text = path.read_text(encoding="utf-8")
        if not _story_is_done(story_text):
            continue

        section = _find_backlog_section(backlog_text, story_id)
        if section is None:
            # No docs/BACKLOG.md entry at all — a different guard's job (BITB-111).
            continue

        heading_line = section.splitlines()[0]
        if _DONE_MARK in heading_line:
            continue

        errors.append(
            f"{story_id} ({_relpath(path)}) is Done, but its {_relpath(_BACKLOG_MD)} "
            f"heading is not marked {_DONE_MARK}:\n    {heading_line.strip()}"
        )
    return errors


def main() -> int:
    errors = check()
    if not errors:
        print(
            f"OK: every {_DONE_MARK} Done story in {_relpath(_STORY_DIR)}/ that has a "
            f"{_relpath(_BACKLOG_MD)} entry has that entry marked {_DONE_MARK} too."
        )
        return 0

    print(f"FAIL: {len(errors)} story/-ies are Done but not reflected in the backlog index:\n", file=sys.stderr)
    for error in errors:
        print(f"  * {error}\n", file=sys.stderr)
    print(
        "Update the docs/BACKLOG.md heading (and its Status line) to match the story file, "
        "or move the entry to docs/DONE/ if this repo's convention is to retire it there.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
