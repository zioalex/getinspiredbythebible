#!/usr/bin/env python3
"""Tests for scripts/migrate_backlog_frontmatter.py (BITB-313)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import backlog  # noqa: E402
import migrate_backlog_frontmatter as mig  # noqa: E402

S = "docs/BACKLOG_STORIES/"
D = "docs/DONE/"


@pytest.mark.parametrize(
    ("raw", "status", "prs"),
    [
        ("🎯 Todo", "todo", []),
        ("Todo", "todo", []),
        ("📋 Backlog", "todo", []),
        ("📋 Proposed — not yet started.", "todo", []),
        ("Todo → Done", "done", []),
        ("🚧 In Progress", "in-progress", []),
        ("🔄 In progress — PR #1272 (constraint documented)", "in-progress", [1272]),
        ("🚧 Partially Shipped — backend + web slice", "in-progress", []),
        ("🔍 In Review", "in-review", []),
        ("🔄 In Review (PR #1225)", "in-review", [1225]),
        ("🔄 In PR (PR #637 — 2026-05-29)", "in-review", [637]),
        ("🟡 Code Complete — Pending Validation", "in-review", []),
        ("� In Review — PR #1196", "in-review", [1196]),
        ("✅ Done", "done", []),
        ("✅ Merged", "done", []),
        ("✅ Done — PR #1226, merged 2026-10-28", "done", [1226]),
        ("✅ Done (2026-08-15)", "done", []),
        ("✅ RESOLVED - glitch", "done", []),
        ("❌ Cancelled — decided in BITB-185", "cancelled", []),
        ("⏸️ Gated Later; unscheduled", "blocked", []),
        ("Blocked on BITB-085", "blocked", []),
    ],
)
def test_normalize_status(raw: str, status: str, prs: list[int]) -> None:
    info = mig.normalize_status(raw)
    assert info.status == status
    assert info.prs == prs


def test_normalize_status_notes_and_dependencies() -> None:
    done = mig.normalize_status("✅ Done — PR #1226, merged 2026-10-28")
    assert done.note == "PR #1226, merged 2026-10-28"
    blocked = mig.normalize_status("🎯 Todo (blocked by BITB-230)")
    assert blocked.status == "todo" and blocked.depends_on == ["BITB-230"]
    # A PR that merely blocks the story is not an implementing PR.
    assert mig.normalize_status("🎯 Todo (blocked by PR #1202 merge)").prs == []
    assert mig.normalize_status("🎯 Todo — gated on BITB-262 landing").depends_on == ["BITB-262"]


def test_unknown_status_aborts_naming_the_file() -> None:
    with pytest.raises(mig.MigrationError, match="docs/x.md"):
        mig.normalize_status("Wibble", "docs/x.md")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("P1", ("P1", "")),
        ("P2 (Medium)", ("P2", "")),
        ("P0 (Critical/Blocker)", ("P0", "")),
        ("P1 (High - Blocks feature deployment)", ("P1", "(High - Blocks feature deployment)")),
        ("P3 — pure waste, but bounded", ("P3", "pure waste, but bounded")),
        ("High — core user experience feature", ("P1", "core user experience feature")),
        ("Whatever", (None, "Whatever")),
    ],
)
def test_normalize_priority(raw: str, expected: tuple[str | None, str]) -> None:
    assert mig.normalize_priority(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("S", ("S", "")),
        ("M (1-2 days)", ("M", "")),
        ("S (< 4 hrs)", ("S", "")),
        ("XS (single table edit)", ("XS", "(single table edit)")),
        ("S–M (one workflow)", ("M", "S–M (one workflow)")),
        ("S–M", ("M", "S–M")),
        ("Provisional XL (4–6 weeks)", ("XL", "")),
        (
            "XL (4–6 implementation weeks after all gates)",
            ("XL", "(4–6 implementation weeks after all gates)"),
        ),
        ("Large", ("L", "")),
        ("Huge", (None, "Huge")),
    ],
)
def test_normalize_size(raw: str, expected: tuple[str | None, str]) -> None:
    assert mig.normalize_size(raw) == expected


INDEX = """# Product Backlog

## Changelog

- 2026-11-01: BITB-020 done

## P0 - Critical (Ship Now)

### 🎯 BITB-001: First P0

**Status:** 🎯 Todo
**Priority:** P0
**Size:** S
**Created:** 2026-11-01

Summary one.

---

### 🚧 BITB-002: Second P0

**Status:** 🚧 In Progress
Summary two.

## P1 - High Priority (Next Sprint)

### 🎯 BITB-003: Only in index, todo

**Status:** 🎯 Todo (blocked by BITB-001)
**Priority:** P1
**Size:** M
**Created:** 2026-10-01

Index-only body text.

**Full Story:** nowhere

---

## P3 - Low Priority (Future)

### 🎯 BITB-004: Stale file marker

**Status:** ✅ Done — PR #77, merged 2026-10-02
**Size:** XS

## Done (Recent Completions)

### ✅ BITB-005: Index-only done

**Status:** ✅ Done (PR #55 merged 2026-01-01)
**Size:** L
Done body.

### ✅ BITB-004: Stale file marker

**Status:** ✅ Done (dup)

## Icebox (Ideas for Future Consideration)

- idea
"""

STORY_1 = """# BITB-001: First P0

**Status:** 🔄 In progress — PR #1272 (constraint documented)
**Priority:** P0 (Critical/Blocker)
**Size:** S (< 2 hours)
**Created:** 2026-11-01
**Prompted by:** the owner

## Problem

Text that must survive byte-for-byte.
"""

STORY_2 = """# BITB-002: Second P0

**Status:** 🚧 Partially Shipped — backend + web slice below; Android port and the
instrumentation/IP-cap work are tracked separately in
[BITB-003](BITB-003-x.md)

**Priority:** P0
**Size:** M

Body paragraph.
"""

STORY_4 = """# BITB-004: Stale file marker

**Status:** 🎯 Todo | **Priority:** P2 | **Size:** S | **Date:** 2026-09-19

## Problem

Body.
"""

STORY_6 = """# BITB-006: Not in the index and no status

Plain body, no header lines at all.
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    files = {
        "docs/BACKLOG.md": INDEX,
        S + "BITB-001-first.md": STORY_1,
        S + "BITB-002-second.md": STORY_2,
        D + "BITB-004-stale.md": STORY_4,
        S + "BITB-006-plain.md": STORY_6,
        D + "not-a-story.md": "# ignored\n",
    }
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def _meta(root: Path, rel: str) -> dict[str, object]:
    block, _ = backlog.split_front_matter((root / rel).read_text(encoding="utf-8"))
    assert block is not None
    return backlog.parse_front_matter(block)


def test_dry_run_writes_nothing(repo: Path) -> None:
    before = (repo / S / "BITB-001-first.md").read_text(encoding="utf-8")
    report = mig.run(repo, repo / "docs" / "BACKLOG.md", write=False)
    assert (repo / S / "BITB-001-first.md").read_text(encoding="utf-8") == before
    assert not (repo / S / "BITB-003-only-in-index-todo.md").exists()
    assert len(report.migrated) == 4 and len(report.created_from_index) == 2


def test_migration_end_to_end(repo: Path) -> None:
    report = mig.run(repo, repo / "docs" / "BACKLOG.md", write=True)

    one = _meta(repo, S + "BITB-001-first.md")
    assert one == {
        "id": "BITB-001",
        "status": "in-progress",
        "priority": "P0",
        "size": "S",
        "rank": 10,  # first entry of the P0 section
        "created": "2026-11-01",
        "prs": [1272],
    }
    text = (repo / S / "BITB-001-first.md").read_text(encoding="utf-8")
    assert "**Status:**" not in text and "**Priority:**" not in text
    assert "**Status note:** PR #1272 (constraint documented)" in text
    assert "**Prompted by:** the owner" in text
    assert text.endswith("## Problem\n\nText that must survive byte-for-byte.\n")

    two = _meta(repo, S + "BITB-002-second.md")
    assert two["rank"] == 20 and two["status"] == "in-progress" and two["size"] == "M"
    two_text = (repo / S / "BITB-002-second.md").read_text(encoding="utf-8")
    assert "[BITB-003](BITB-003-x.md)" in two_text  # wrapped status folded into the note
    assert "\n\n\n" not in two_text  # no double blank lines left behind

    # Pipe-joined header; stale file "Todo" loses to the index's Done; Date becomes created.
    four = _meta(repo, D + "BITB-004-stale.md")
    assert four["status"] == "done" and four["prs"] == [77] and four["priority"] == "P2"
    assert four["created"] == "2026-09-19" and four["size"] == "S"
    assert "**Date:**" not in (repo / D / "BITB-004-stale.md").read_text(encoding="utf-8")
    assert any("BITB-004 status" in c and "index wins" in c for c in report.conflicts)

    # No header and not in the index: defaults are reported, body untouched.
    six = _meta(repo, S + "BITB-006-plain.md")
    assert six["status"] == "todo" and six["priority"] == "P3"
    assert any("BITB-006" in d for d in report.defaults)
    assert (repo / S / "BITB-006-plain.md").read_text(encoding="utf-8").endswith(STORY_6)

    # Index-only entries become files; done ones go to docs/DONE.
    three = repo / S / "BITB-003-only-in-index-todo.md"
    assert _meta(repo, three.relative_to(repo).as_posix())["depends_on"] == ["BITB-001"]
    assert "# BITB-003: Only in index, todo" in three.read_text(encoding="utf-8")
    assert "Index-only body text." in three.read_text(encoding="utf-8")
    assert "**Status:**" not in three.read_text(encoding="utf-8")
    five = _meta(repo, D + "BITB-005-index-only-done.md")
    assert five["status"] == "done" and five["prs"] == [55] and five["size"] == "L"

    assert report.duplicates == ["BITB-004: duplicate index heading ignored"]
    assert (repo / D / "not-a-story.md").read_text(encoding="utf-8") == "# ignored\n"
    assert backlog.check_stories(backlog.load_all(repo)) == []


def test_migration_is_idempotent(repo: Path) -> None:
    mig.run(repo, repo / "docs" / "BACKLOG.md", write=True)
    snapshot = {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.md")}
    again = mig.run(repo, repo / "docs" / "BACKLOG.md", write=True)
    assert again.migrated == [] and again.created_from_index == []
    assert {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.md")} == snapshot


def test_rank_is_seeded_per_priority_section() -> None:
    entries, duplicates = mig.parse_index(INDEX)
    assert [(i, entries[i].rank) for i in ("BITB-001", "BITB-002", "BITB-003", "BITB-004")] == [
        ("BITB-001", 10),
        ("BITB-002", 20),
        ("BITB-003", 10),
        ("BITB-004", 10),
    ]
    assert entries["BITB-005"].rank is None  # Done section has no rank
    assert duplicates == ["BITB-004"]


def test_main_aborts_on_unknown_status(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / S / "BITB-006-plain.md").write_text(
        "# BITB-006: X\n\n**Status:** Wibble\n", encoding="utf-8"
    )
    code = mig.main(["--root", str(repo), "--dry-run"])
    assert code == 1
    assert "BITB-006-plain.md" in capsys.readouterr().err
