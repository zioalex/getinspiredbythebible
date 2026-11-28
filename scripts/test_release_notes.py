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


# ---------------------------------------------------------------- end-user What's New (BITB-175)

GOOD_NOTE = (
    "- Reading aloud keeps going with the screen off\n- Switching language starts a new chat\n"
)


def _write_notes(root: Path, version: str, locales=release_notes.LOCALES, text: str = GOOD_NOTE):
    folder = root / release_notes.USER_NOTES_DIR / version
    folder.mkdir(parents=True, exist_ok=True)
    for locale in locales:
        (folder / f"{locale}.md").write_text(text, encoding="utf-8")
    return folder


def test_draft_user_notes_lists_done_features_then_fixes(stories) -> None:
    assert release_notes.draft_user_notes(stories, "R1") == (
        "- Read the answer aloud\n- Crisis card shows for S11\n"
    )
    assert release_notes.draft_user_notes(stories, "R2") == ""


def test_check_user_notes_valid_and_required_version(tmp_path: Path) -> None:
    assert release_notes.check_user_notes(tmp_path) == []
    assert "release-notes/1.63.0/: missing" in release_notes.check_user_notes(tmp_path, "1.63.0")[0]
    _write_notes(tmp_path, "1.63.0")
    assert release_notes.check_user_notes(tmp_path, "1.63.0") == []


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("", "empty"),
        ("- " + "x" * 518, "520 characters, the Play Store allows 500"),
        ("Plain sentence, no bullet", "every line must be a '- ' bullet"),
        ("- Fixed chips (BITB-254)", "contains a story id"),
        ("- Uses `openai_moderation`", "contains code formatting"),
        ("- Faster replies (#1313)", "contains a PR reference"),
    ],
)
def test_check_user_notes_content_rules(tmp_path: Path, text: str, needle: str) -> None:
    _write_notes(tmp_path, "1.63.0")
    (tmp_path / "release-notes/1.63.0/it.md").write_text(text, encoding="utf-8")
    errors = release_notes.check_user_notes(tmp_path)
    assert any(e.startswith("release-notes/1.63.0/it.md: ") and needle in e for e in errors), errors


def test_check_user_notes_missing_extra_and_bad_folder(tmp_path: Path) -> None:
    _write_notes(tmp_path, "1.63.0", locales=("en", "it"))
    folder = _write_notes(tmp_path, "1.64.0")
    (folder / "jp.md").write_text(GOOD_NOTE, encoding="utf-8")
    (tmp_path / "release-notes/next").mkdir()
    errors = release_notes.check_user_notes(tmp_path)
    assert "release-notes/1.63.0/ko.md: missing (every release needs all 11 languages)" in errors
    assert any(
        e.startswith("release-notes/1.64.0/jp.md: not one of the app's locales") for e in errors
    )
    assert "release-notes/next/: folder name must be a release version like 1.63.0" in errors
    assert not any(e.startswith("release-notes/1.64.0/en.md") for e in errors)


def test_cli_user_and_check(stories, tmp_path: Path, capsys) -> None:
    assert release_notes.main(["--root", str(tmp_path), "user", "--milestone", "R1"]) == 0
    assert capsys.readouterr().out.startswith("- Read the answer aloud\n")
    assert release_notes.main(["--root", str(tmp_path), "check", "--version", "9.9.9"]) == 1
    assert "::error::release-notes/9.9.9/: missing" in capsys.readouterr().out
    _write_notes(tmp_path, "9.9.9")
    assert release_notes.main(["--root", str(tmp_path), "check", "--version", "9.9.9"]) == 0


def test_locales_match_the_frontend_messages() -> None:
    messages = _SCRIPTS_DIR.parent / "frontend" / "messages"
    assert sorted(p.stem for p in messages.glob("*.json")) == sorted(release_notes.LOCALES)


def test_real_release_notes_folder_is_valid() -> None:
    assert release_notes.check_user_notes(_SCRIPTS_DIR.parent) == []
