#!/usr/bin/env python3
"""Tests for scripts/check_backlog_story_ids.py (BITB-111).

Builds tiny synthetic fixtures under pytest's ``tmp_path`` fixture for each case -- never a
deliberately-broken fixture committed to the real ``docs/`` tree -- and points the guard's
module-level path constants at them via monkeypatch, mirroring the
sys.path-insert-then-import style of ``scripts/test_run_search_eval_probe.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "check_backlog_story_ids", _SCRIPTS_DIR / "check_backlog_story_ids.py"
)
assert _spec is not None and _spec.loader is not None
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _make_repo(
    tmp_path: Path, *, story_files: dict[str, str], done_files: dict[str, str], backlog_md: str
) -> None:
    story_dir = tmp_path / "docs" / "BACKLOG_STORIES"
    done_dir = tmp_path / "docs" / "DONE"
    story_dir.mkdir(parents=True)
    done_dir.mkdir(parents=True)
    for name, content in story_files.items():
        (story_dir / name).write_text(content, encoding="utf-8")
    for name, content in done_files.items():
        (done_dir / name).write_text(content, encoding="utf-8")
    (tmp_path / "docs" / "BACKLOG.md").write_text(backlog_md, encoding="utf-8")


@pytest.fixture
def point_guard_at(monkeypatch, tmp_path):
    """Repoint the guard's module-level path constants at a scratch repo root."""

    def _point(repo_root: Path) -> None:
        monkeypatch.setattr(guard, "_REPO_ROOT", repo_root)
        monkeypatch.setattr(guard, "_STORY_DIR", repo_root / "docs" / "BACKLOG_STORIES")
        monkeypatch.setattr(guard, "_DONE_DIR", repo_root / "docs" / "DONE")
        monkeypatch.setattr(guard, "_BACKLOG_MD", repo_root / "docs" / "BACKLOG.md")
        # Fixtures are self-contained; the real repo's companion-doc / pre-existing-debt
        # allowlists must never mask a problem planted by a test.
        monkeypatch.setattr(guard, "_ALLOWED_SHARED_ID_GROUPS", ())
        monkeypatch.setattr(guard, "_MISSING_BACKLOG_ENTRY_EXEMPT", frozenset())

    return _point


def test_clean_repo_passes(tmp_path, point_guard_at, capsys):
    _make_repo(
        tmp_path,
        story_files={
            "BITB-001-first-story.md": "# BITB-001: First Story\n",
            "BITB-002-second-story.md": "# BITB-002: Second Story\n",
        },
        done_files={
            "BITB-003-shipped-story.md": "# BITB-003: Shipped Story\n",
        },
        backlog_md=(
            "# Product Backlog\n\n"
            "### BITB-001: First Story\n\n"
            "### BITB-002: Second Story\n\n"
            "### BITB-003: Shipped Story\n"
        ),
    )
    point_guard_at(tmp_path)

    assert guard.main() == 0
    out = capsys.readouterr().out
    assert "OK" in out


def test_duplicate_id_with_no_allowlist_entry_fails(tmp_path, point_guard_at, capsys):
    _make_repo(
        tmp_path,
        story_files={
            "BITB-001-first-story.md": "# BITB-001: First Story\n",
            # A second, unrelated story wrongly reused BITB-001.
            "BITB-001-second-unrelated-story.md": "# BITB-001: Second Unrelated Story\n",
        },
        done_files={},
        backlog_md=(
            "# Product Backlog\n\n"
            "### BITB-001: First Story\n\n"
            "### BITB-001: Second Unrelated Story\n"
        ),
    )
    point_guard_at(tmp_path)

    assert guard.main() == 1
    err = capsys.readouterr().err
    assert "BITB-001 maps to 2 files" in err
    assert "BITB-001-first-story.md" in err
    assert "BITB-001-second-unrelated-story.md" in err


def test_story_file_with_no_backlog_entry_fails(tmp_path, point_guard_at, capsys):
    _make_repo(
        tmp_path,
        story_files={
            "BITB-001-first-story.md": "# BITB-001: First Story\n",
            "BITB-002-orphaned-story.md": "# BITB-002: Orphaned Story\n",
        },
        done_files={},
        # BITB-002 has no heading or mention anywhere in BACKLOG.md.
        backlog_md=("# Product Backlog\n\n### BITB-001: First Story\n"),
    )
    point_guard_at(tmp_path)

    assert guard.main() == 1
    err = capsys.readouterr().err
    assert "BITB-002-orphaned-story.md" in err
    assert "no docs/BACKLOG.md entry" in err
    # The properly cross-referenced story must not be flagged.
    assert "BITB-001-first-story.md" not in err


def test_incidental_prose_mention_does_not_count_as_a_backlog_entry(
    tmp_path, point_guard_at, capsys
):
    """A bare `BITB-NNN` token inside another story's prose (e.g. "renumbered to
    BITB-002-...md") is not a real entry for BITB-002 and must still fail -- this is the
    exact false-pass the old `\\bBITB-NNN\\b` substring search let through."""
    _make_repo(
        tmp_path,
        story_files={
            "BITB-001-first-story.md": "# BITB-001: First Story\n",
            "BITB-002-orphaned-story.md": "# BITB-002: Orphaned Story\n",
        },
        done_files={},
        backlog_md=(
            "# Product Backlog\n\n"
            "### BITB-001: First Story\n\n"
            "Note (ID collision): the old orphan file was renumbered to "
            "`BITB-002-orphaned-story.md`. This mention is prose inside BITB-001's own "
            "entry, not a heading or Full Story link for BITB-002.\n"
        ),
    )
    point_guard_at(tmp_path)

    assert guard.main() == 1
    err = capsys.readouterr().err
    assert "BITB-002-orphaned-story.md" in err
    assert "no docs/BACKLOG.md entry" in err


def test_real_heading_counts_as_a_backlog_entry(tmp_path, point_guard_at, capsys):
    """A genuine `### ... BITB-NNN: ...` heading is a real entry and must pass."""
    _make_repo(
        tmp_path,
        story_files={
            "BITB-002-real-story.md": "# BITB-002: Real Story\n",
        },
        done_files={},
        backlog_md=("# Product Backlog\n\n### \U0001f3af BITB-002: Real Story\n"),
    )
    point_guard_at(tmp_path)

    assert guard.main() == 0
    assert "OK" in capsys.readouterr().out


def test_full_story_link_counts_as_a_backlog_entry_even_without_a_matching_heading(
    tmp_path, point_guard_at, capsys
):
    """A `**Full Story:**` link naming this exact file is a real entry too, even when the
    surrounding section's heading does not itself contain the id (e.g. a shared write-up)."""
    _make_repo(
        tmp_path,
        story_files={
            "BITB-002-real-story.md": "# BITB-002: Real Story\n",
        },
        done_files={},
        backlog_md=(
            "# Product Backlog\n\n"
            "### Some Combined Write-Up\n\n"
            "**Full Story:** `docs/BACKLOG_STORIES/BITB-002-real-story.md`\n"
        ),
    )
    point_guard_at(tmp_path)

    assert guard.main() == 0
    assert "OK" in capsys.readouterr().out


def _allow_bitb_005_pair(monkeypatch):
    monkeypatch.setattr(
        guard,
        "_ALLOWED_SHARED_ID_GROUPS",
        (
            frozenset(
                {
                    "docs/DONE/BITB-005-ANALYSIS.md",
                    "docs/DONE/BITB-005-RESOLUTION.md",
                }
            ),
        ),
    )


def test_documented_companion_pair_is_not_a_collision(
    tmp_path, point_guard_at, monkeypatch, capsys
):
    """The allowlist mechanism itself: two files sharing an id ARE allowed -- and do not fail
    -- when they are exactly the documented companion-doc pair and nothing else claims that
    id."""
    _make_repo(
        tmp_path,
        story_files={
            "BITB-001-unrelated-story.md": "# BITB-001: Unrelated Story\n",
        },
        done_files={
            "BITB-005-ANALYSIS.md": "# BITB-005 analysis\n",
            "BITB-005-RESOLUTION.md": "# BITB-005 resolution\n",
        },
        backlog_md=("# Product Backlog\n\n### BITB-001: Unrelated Story\n"),
    )
    point_guard_at(tmp_path)
    _allow_bitb_005_pair(monkeypatch)

    assert guard.main() == 0
    assert "OK" in capsys.readouterr().out


def test_allowlisted_pair_plus_rogue_claimant_still_fails(
    tmp_path, point_guard_at, monkeypatch, capsys
):
    """Regression test for the exact bug an adversarial review found: the allowlisted
    companion-doc pair counts as ONE claimant on its id, not zero -- so a pair plus one
    extra, unrelated file sharing the same id is two claimants and must still fail, not be
    swallowed by subtracting the pair down to a single "remaining" file."""
    _make_repo(
        tmp_path,
        story_files={
            # A genuinely different, unrelated story wrongly reused id 005 -- this is not
            # part of the documented BITB-005-ANALYSIS/RESOLUTION companion pair.
            "BITB-005-rogue-unrelated-story.md": "# BITB-005: Rogue Unrelated Story\n",
        },
        done_files={
            "BITB-005-ANALYSIS.md": "# BITB-005 analysis\n",
            "BITB-005-RESOLUTION.md": "# BITB-005 resolution\n",
        },
        backlog_md=("# Product Backlog\n\n### BITB-005: Rogue Unrelated Story\n"),
    )
    point_guard_at(tmp_path)
    _allow_bitb_005_pair(monkeypatch)

    assert guard.main() == 1
    err = capsys.readouterr().err
    assert "BITB-005 maps to 3 files" in err
    assert "BITB-005-rogue-unrelated-story.md" in err
    assert "BITB-005-ANALYSIS.md" in err
    assert "BITB-005-RESOLUTION.md" in err


def test_missing_backlog_entry_exemption_suppresses_known_debt(
    tmp_path, point_guard_at, monkeypatch, capsys
):
    """The exemption list lets a named pre-existing gap pass without masking new ones."""
    _make_repo(
        tmp_path,
        story_files={
            "BITB-001-first-story.md": "# BITB-001: First Story\n",
            "BITB-002-known-gap.md": "# BITB-002: Known Gap\n",
        },
        done_files={},
        backlog_md=("# Product Backlog\n\n### BITB-001: First Story\n"),
    )
    point_guard_at(tmp_path)
    monkeypatch.setattr(
        guard,
        "_MISSING_BACKLOG_ENTRY_EXEMPT",
        frozenset({"docs/BACKLOG_STORIES/BITB-002-known-gap.md"}),
    )

    assert guard.main() == 0
    assert "OK" in capsys.readouterr().out
