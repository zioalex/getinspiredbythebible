#!/usr/bin/env python3
"""Tests for scripts/backlog.py (BITB-313)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import backlog  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent


def _story(
    story_id: str = "BITB-001",
    *,
    status: str = "todo",
    priority: str = "P2",
    size: str | None = "S",
    rank: int | None = None,
    title: str = "A story",
    extra: str = "",
) -> str:
    lines = ["---", f"id: {story_id}", f"status: {status}", f"priority: {priority}"]
    if size:
        lines.append(f"size: {size}")
    if rank is not None:
        lines.append(f"rank: {rank}")
    lines.append("created: 2026-11-13")
    lines.append("---")
    return "\n".join(lines) + f"\n\n# {story_id}: {title}\n\n{extra}\nBody.\n"


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def _check(tmp_path: Path, files: dict[str, str]) -> list[str]:
    return backlog.check_stories(backlog.load_all(_repo(tmp_path, files)))


S = "docs/BACKLOG_STORIES/"
D = "docs/DONE/"


# ---------------------------------------------------------------- parser / writer


def test_round_trip_preserves_fields_and_order() -> None:
    meta = {
        "supersedes": "free text: with colon",
        "prs": [1, 22],
        "id": "BITB-007",
        "rank": 30,
        "status": "in-review",
        "priority": "P0",
        "size": "XL",
        "created": "2026-01-02",
        "follow_ups": ["BITB-008"],
        "depends_on": [],
    }
    rendered = backlog.format_front_matter(meta)
    keys = [line.split(":")[0] for line in rendered.splitlines()[1:-1]]
    assert keys == [
        "id",
        "status",
        "priority",
        "size",
        "rank",
        "created",
        "prs",
        "follow_ups",
        "supersedes",
    ]  # fixed order, empty depends_on omitted
    block, rest = backlog.split_front_matter(rendered + "\n# T\n")
    assert rest == "\n# T\n"
    parsed = backlog.parse_front_matter(block or "")
    assert parsed["prs"] == [1, 22]
    assert parsed["rank"] == 30
    assert parsed["supersedes"] == "free text: with colon"
    assert backlog.format_front_matter(parsed) == rendered


@pytest.mark.parametrize(
    "block",
    ["id BITB-1", "prs: 12", "prs: [a]", "rank: x", "# comment", "id: A\nid: B", "follow_ups: [,]"],
)
def test_parse_rejects_bad_front_matter(block: str) -> None:
    with pytest.raises(backlog.FrontMatterError):
        backlog.parse_front_matter(block)


def test_split_front_matter_unclosed() -> None:
    with pytest.raises(backlog.FrontMatterError):
        backlog.split_front_matter("---\nid: BITB-1\n# T\n")
    assert backlog.split_front_matter("# T\n") == (None, "# T\n")


# ---------------------------------------------------------------- check


def test_check_clean(tmp_path: Path) -> None:
    files = {
        S + "BITB-001-a.md": _story("BITB-001", extra="See follow-up."),
        D + "BITB-002-b.md": _story("BITB-002", status="done"),
        D + "notes-not-a-story.md": "no front matter, ignored",
    }
    assert _check(tmp_path, files) == []


@pytest.mark.parametrize(
    ("content", "needle"),
    [
        ("# BITB-001: No front matter\n", "no front matter"),
        (_story(status="finished"), "status 'finished' invalid"),
        (_story(priority="P9"), "priority 'P9' invalid"),
        (_story(size="XXL"), "size 'XXL' invalid"),
        (_story("BITB-009"), "does not match the filename"),
        (_story().replace("created: 2026-11-13", "created: yesterday"), "ISO date"),
        (_story().replace("size: S", "size: S\nbogus: 1"), "unknown front-matter key 'bogus'"),
        (_story().replace("size: S", "size: S\nfollow_ups: [BITB-404]"), "BITB-404"),
        (_story().replace("size: S", "size: S\ndepends_on: [BITB-404]"), "depends_on"),
        (_story(extra="**Status:** todo"), "bold 'Status' line"),
        ("---\nid: BITB-001\nstatus: todo\n# T\n", "never closed"),
        (_story().replace("# BITB-001: A story", "no heading"), "no '# BITB-NNN: Title'"),
    ],
)
def test_check_error_classes(tmp_path: Path, content: str, needle: str) -> None:
    errors = _check(tmp_path, {S + "BITB-001-a.md": content})
    assert any(needle in e for e in errors), errors
    assert all(e.startswith("docs/BACKLOG_STORIES/BITB-001-a.md") for e in errors)


def test_check_duplicate_ids_and_allowlist(tmp_path: Path) -> None:
    errors = _check(
        tmp_path,
        {S + "BITB-001-a.md": _story(), D + "BITB-001-b.md": _story(status="done")},
    )
    assert any("maps to 2 files" in e for e in errors)


def test_check_companion_group_allowed_but_rogue_file_fails(tmp_path: Path) -> None:
    pair = {
        D + "BITB-147-ANALYSIS-CI-OLLAMA-TIMEOUT.md": _story("BITB-147", status="done"),
        D + "BITB-147-RESOLUTION-CI-OLLAMA-TIMEOUT.md": _story("BITB-147", status="done"),
    }
    assert _check(tmp_path, pair) == []
    pair[S + "BITB-147-rogue.md"] = _story("BITB-147")
    assert any("BITB-147: maps to 3 files" in e for e in _check(tmp_path, pair))


def test_check_partial_companion_group_fails(tmp_path: Path) -> None:
    files = {
        D + "BITB-147-ANALYSIS-CI-OLLAMA-TIMEOUT.md": _story("BITB-147", status="done"),
        S + "BITB-147-other.md": _story("BITB-147"),
    }
    assert any("BITB-147" in e for e in _check(tmp_path, files))


def test_check_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path, {S + "BITB-001-a.md": _story()})
    assert backlog.main(["--root", str(root), "check"]) == 0
    assert "OK: 1 stories" in capsys.readouterr().out
    (root / S / "BITB-002-b.md").write_text("# BITB-002: x\n", encoding="utf-8")
    assert backlog.main(["--root", str(root), "check"]) == 1
    assert "no front matter" in capsys.readouterr().err


# ---------------------------------------------------------------- list


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    return _repo(
        tmp_path,
        {
            S + "BITB-010-low.md": _story("BITB-010", priority="P3", title="Low thing"),
            S + "BITB-011-rank2.md": _story("BITB-011", priority="P1", rank=20, title="Second"),
            S + "BITB-012-rank1.md": _story("BITB-012", priority="P1", rank=10, title="First"),
            S + "BITB-013-norank.md": _story("BITB-013", priority="P1", title="No rank"),
            S + "BITB-005-top.md": _story("BITB-005", priority="P0", title="Top Chat bug"),
            S + "BITB-014-ice.md": _story("BITB-014", priority="icebox", title="Idea"),
            D + "BITB-001-done.md": _story("BITB-001", status="done", title="Shipped"),
            S
            + "BITB-015-wip.md": _story(
                "BITB-015",
                status="in-review",
                priority="P2",
                title="x" * 120,
                extra="",
            ).replace("created:", "prs: [1292, 1300]\ncreated:"),
        },
    )


def _ids(stories: list[backlog.Story]) -> list[str]:
    return [s.id for s in stories]


def test_list_sort_priority_rank_then_id(sample: Path) -> None:
    stories = backlog.filter_stories(backlog.load_all(sample))
    assert _ids(stories) == [
        "BITB-005",
        "BITB-012",
        "BITB-011",
        "BITB-013",
        "BITB-015",
        "BITB-010",
        "BITB-014",
    ]  # P0; P1 rank 10, 20, unranked; P2; P3; icebox. Done hidden by default.


def test_list_filters(sample: Path) -> None:
    all_stories = backlog.load_all(sample)
    assert _ids(backlog.filter_stories(all_stories, status="done")) == ["BITB-001"]
    assert len(backlog.filter_stories(all_stories, show_all=True)) == 8
    assert _ids(backlog.filter_stories(all_stories, priority="p0,P3")) == ["BITB-005", "BITB-010"]
    assert _ids(backlog.filter_stories(all_stories, grep="CHAT")) == ["BITB-005"]
    assert _ids(backlog.filter_stories(all_stories, size="s", status="in-review")) == ["BITB-015"]
    assert _ids(backlog.filter_stories(all_stories, priority="icebox")) == ["BITB-014"]


def test_compact_format_and_truncation(sample: Path) -> None:
    stories = backlog.filter_stories(backlog.load_all(sample), status="in-review")
    line = backlog.format_compact(stories).rstrip("\n")
    assert line.startswith("BITB-015 P2 S in-review #1300 ")
    title = line.split("#1300 ", 1)[1]
    assert len(title) == backlog.TITLE_WIDTH and title.endswith("…")
    assert backlog.format_compact([]) == ""


def test_md_and_json_formats(sample: Path) -> None:
    stories = backlog.filter_stories(backlog.load_all(sample), priority="P0")
    assert "| [BITB-005](BACKLOG_STORIES/BITB-005-top.md) | P0 | S | todo | - |" in (
        backlog.format_md(stories)
    )
    rows = json.loads(backlog.format_json(stories))
    assert rows[0]["id"] == "BITB-005" and rows[0]["title"] == "Top Chat bug"


def test_show_and_next_id(sample: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert backlog.main(["--root", str(sample), "show", "bitb-012"]) == 0
    out = capsys.readouterr().out
    assert "path: docs/BACKLOG_STORIES/BITB-012-rank1.md" in out
    assert "rank: 10" in out and "Body." not in out
    assert backlog.main(["--root", str(sample), "show", "BITB-012", "--full"]) == 0
    assert "Body." in capsys.readouterr().out
    with pytest.raises(SystemExit):
        backlog.main(["--root", str(sample), "show", "BITB-999"])
    assert backlog.main(["--root", str(sample), "next-id"]) == 0
    assert capsys.readouterr().out.strip() == "BITB-016"


def test_render_is_deterministic_and_grouped(sample: Path) -> None:
    first = backlog.render_index(backlog.load_all(sample))
    assert first == backlog.render_index(list(reversed(backlog.load_all(sample))))
    assert first.index("## P0") < first.index("## P1") < first.index("## icebox")
    assert first.index("## icebox") < first.index("## Done / cancelled")


# ---------------------------------------------------------------- changelog


def _git(root: Path, *args: str, date: str = "2026-11-10T12:00:00") -> None:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(root),
    }
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, env=env)


def _init(root: Path) -> None:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "commit.gpgsign", "false")


def test_changelog_from_git_subjects(tmp_path: Path) -> None:
    _init(tmp_path)
    for n, (date, subject) in enumerate(
        [
            ("2026-11-01T10:00:00", "chore: unrelated (#1)"),
            ("2026-11-02T10:00:00", "feat(api): thing (BITB-100) (#11)"),
            ("2026-11-05T10:00:00", "fix: two stories BITB-101 and BITB-102 (#12)"),
            ("2026-11-06T10:00:00", "docs: BITB-103 again BITB-103 (#13)"),
        ]
    ):
        (tmp_path / f"f{n}").write_text(str(n))
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-q", "-m", subject, date=date)
    entries = backlog.git_changelog(tmp_path, "origin/main")  # falls back to HEAD
    assert entries == [
        "- 2026-11-06: BITB-103 — docs: BITB-103 again BITB-103 (#13)",
        "- 2026-11-05: BITB-101, BITB-102 — fix: two stories BITB-101 and BITB-102 (#12)",
        "- 2026-11-02: BITB-100 — feat(api): thing (BITB-100) (#11)",
    ]
    assert backlog.git_changelog(tmp_path, "HEAD", since="2026-11-05") == entries[:2]
    assert backlog.git_changelog(tmp_path, "HEAD", limit=1) == entries[:1]


# ---------------------------------------------------------------- context budgets (real tree)


def test_budget_open_items_compact_listing() -> None:
    stories = backlog.filter_stories(
        backlog.load_all(_REPO_ROOT), status="todo,in-progress,in-review"
    )
    size = len(backlog.format_compact(stories).encode("utf-8"))
    assert size <= 12 * 1024, f"open-items listing is {size} bytes; budget is 12288 (BITB-313)"


def test_budget_show_without_full() -> None:
    stories = backlog.load_all(_REPO_ROOT)
    worst = max(
        len(backlog.show_story(_REPO_ROOT, stories, s.id, full=False).encode("utf-8"))
        for s in stories
    )
    assert worst <= 1024, f"`show` output reached {worst} bytes; budget is 1024 (BITB-313)"


def test_real_tree_passes_check() -> None:
    assert backlog.check_stories(backlog.load_all(_REPO_ROOT)) == []


# ---------------------------------------------------------------- conflict simulation


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def _merge_tree_conflicts(root: Path, ours: str, theirs: str) -> bool:
    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", ours, theirs],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode != 0


def test_parallel_story_additions_and_status_flips_merge_cleanly(tmp_path: Path) -> None:
    """Two branches off one base each add a story and flip another story's status."""
    version = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
    _init(tmp_path)
    paths = {n: S + f"BITB-00{n}-s{n}.md" for n in (1, 2, 3)}
    _repo(tmp_path, {p: _story(f"BITB-00{n}", title=f"S{n}") for n, p in paths.items()})
    _commit_all(tmp_path, "base")
    _git(tmp_path, "checkout", "-q", "-b", "a")
    (tmp_path / paths[1]).write_text(
        _story("BITB-001", status="in-review", title="S1").replace(
            "created:", "prs: [101]\ncreated:"
        )
    )
    _repo(tmp_path, {S + "BITB-004-x.md": _story("BITB-004", title="X")})
    _commit_all(tmp_path, "feat: BITB-004 (#101)")
    _git(tmp_path, "checkout", "-q", "main")
    _git(tmp_path, "checkout", "-q", "-b", "b")
    (tmp_path / paths[2]).write_text(_story("BITB-002", status="done", title="S2"))
    _repo(tmp_path, {S + "BITB-005-y.md": _story("BITB-005", title="Y")})
    _commit_all(tmp_path, "feat: BITB-005 (#102)")
    probe = subprocess.run(
        ["git", "merge-tree", "--write-tree", "a", "b"], cwd=tmp_path, capture_output=True
    )
    if probe.returncode not in (0, 1):
        pytest.skip(f"git merge-tree --write-tree unsupported: {version.strip()}")
    assert not _merge_tree_conflicts(tmp_path, "a", "b")
    assert not _merge_tree_conflicts(tmp_path, "b", "a")


def test_front_matter_status_flip_is_a_single_line_edit() -> None:
    text = _story("BITB-001")
    flipped = text.replace("status: todo", "status: done")
    changed = [a for a, b in zip(text.splitlines(), flipped.splitlines(), strict=True) if a != b]
    assert changed == ["status: todo"]
    assert text.count("status: todo") == 1
