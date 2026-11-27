#!/usr/bin/env python3
"""Tests for scripts/release_notes.py (BITB-367)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import backlog  # noqa: E402
import release_notes  # noqa: E402

S = "docs/BACKLOG_STORIES/"


def _story(story_id: str, kind: str, status: str, milestone: str | None, title: str) -> str:
    lines = ["---", f"id: {story_id}", f"status: {status}", "priority: P2", f"kind: {kind}"]
    if milestone:
        lines.append(f"milestone: {milestone}")
    lines += ["size: S", "created: 2026-11-27", "---"]
    return "\n".join(lines) + f"\n\n# {story_id}: {title}\n\nBody.\n"


STORIES = {
    "BITB-101": ("feature", "done", "R1", "Read the answer aloud"),
    "BITB-102": ("nfr", "done", "R1", "Rate-limit search"),
    "BITB-103": ("fix", "done", "R1", "Crisis card shows for S11"),
    "BITB-104": ("chore", "done", "R1", "Golden set"),
    "BITB-105": ("fix", "in-review", "R1", "Language switch starts a new chat"),
    "BITB-106": ("chore", "todo", "R1", "More golden cases"),
    "BITB-107": ("nfr", "cancelled", "R1", "Dropped idea"),
    "BITB-108": ("fix", "todo", "R2", "Header at 320px"),
    "BITB-109": ("feature", "done", None, "Unplanned feature"),
}


@pytest.fixture
def stories(tmp_path: Path) -> list[backlog.Story]:
    for story_id, (kind, status, milestone, title) in STORIES.items():
        path = tmp_path / S / f"{story_id}-x.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_story(story_id, kind, status, milestone, title), encoding="utf-8")
    return backlog.load_all(tmp_path)


def test_notes_sections_internal_count_and_still_open(stories) -> None:
    notes = release_notes.render_notes(stories, "r1", "R1: Safe chat", "People get a safe answer.")
    assert notes.startswith("## R1: Safe chat\n\nPeople get a safe answer.\n")
    order = [notes.index(h) for h in ("### New features", "### Quality & reliability", "### Fixes")]
    assert order == sorted(order)
    assert "- Read the answer aloud (BITB-101)" in notes
    assert "- Rate-limit search (BITB-102)" in notes
    assert "- Crisis card shows for S11 (BITB-103)" in notes
    assert "_Plus 1 internal change (tooling, tests, docs): BITB-104._" in notes
    still_open = notes.split("### Still open (moves to the next release)")[1]
    assert "- Language switch starts a new chat (BITB-105, in-review)" in still_open
    for absent in (
        "Golden set (",
        "More golden cases",
        "Dropped idea",
        "Header at 320px",
        "Unplanned",
    ):
        assert absent not in notes.replace("BITB-104", "")


def test_notes_with_nothing_done(stories) -> None:
    notes = release_notes.render_notes(stories, "R2")
    assert notes.startswith("## R2\n")
    assert "_No product changes are done in this milestone yet._" in notes
    assert "- Header at 320px (BITB-108, todo)" in notes


def test_gate(stories) -> None:
    ok, report = release_notes.gate(stories, "R1")
    assert not ok
    assert report.startswith("R1 is not complete: 2 of 7 stories open.")
    assert "- BITB-105 in-review (fix)" in report and "- BITB-106 todo (chore)" in report
    assert release_notes.gate(stories, "R9") == (True, "OK: no stories carry milestone R9.\n")
    done_only = [s for s in stories if s.id not in {"BITB-105", "BITB-106"}]
    assert release_notes.gate(done_only, "R1") == (True, "OK: R1 is complete (5 stories).\n")


def test_current_milestone(stories) -> None:
    assert release_notes.current_milestone(stories) == "R1"
    later = [s for s in stories if s.id not in {"BITB-105", "BITB-106"}]
    assert release_notes.current_milestone(later) == "R2"
    assert release_notes.current_milestone([]) == ""


def test_current_milestone_orders_numerically(tmp_path: Path) -> None:
    for story_id, milestone in (("BITB-201", "R10"), ("BITB-202", "R9")):
        path = tmp_path / S / f"{story_id}-x.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_story(story_id, "fix", "todo", milestone, "x"), encoding="utf-8")
    assert release_notes.current_milestone(backlog.load_all(tmp_path)) == "R9"


def test_pick_github_milestone() -> None:
    milestones = [
        {"number": 7, "state": "open", "title": "R10: Later", "description": ""},
        {"number": 3, "state": "closed", "title": "R1: Shipped", "description": ""},
        {"number": 4, "state": "open", "title": "Backlog", "description": ""},
        {
            "number": 5,
            "state": "open",
            "title": "R2: Smoother chat",
            "description": "Outcome: switching language works.\n\nDone when: ...",
        },
    ]
    assert release_notes.pick_github_milestone(milestones) == {
        "number": 5,
        "key": "R2",
        "title": "R2: Smoother chat",
        "outcome": "Switching language works.",
    }
    assert release_notes.pick_github_milestone([]) == {}


def test_cli(stories, tmp_path: Path, capsys, monkeypatch) -> None:
    root = tmp_path
    assert release_notes.main(["--root", str(root), "gate", "--milestone", "R1"]) == 1
    assert "R1 is not complete" in capsys.readouterr().out
    assert release_notes.main(["--root", str(root), "current"]) == 0
    assert capsys.readouterr().out == "R1\n"
    assert release_notes.main(["--root", str(root), "notes", "--milestone", "R2"]) == 0
    assert capsys.readouterr().out.startswith("## R2\n")
    with pytest.raises(SystemExit) as exc:
        release_notes.main(["--root", str(root), "gate", "--milestone", "v1.63"])
    assert exc.value.code == 2
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps([{"title": "R3: x", "number": 9}])))
    assert release_notes.main(["github-milestone"]) == 0
    assert json.loads(capsys.readouterr().out)["key"] == "R3"


def test_real_backlog_r1_is_open() -> None:
    stories = backlog.load_all(_SCRIPTS_DIR.parent)
    ok, report = release_notes.gate(stories, "R1")
    assert not ok and "BITB-321" in report
    assert release_notes.render_notes(stories, "R1").startswith("## R1\n")
