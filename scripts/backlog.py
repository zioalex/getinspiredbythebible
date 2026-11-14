#!/usr/bin/env python3
"""Query and validate the story backlog (BITB-313).

Every story file in ``docs/BACKLOG_STORIES/`` and ``docs/DONE/`` carries a YAML front
matter block that is the **single source of truth** for its status, priority, size, rank
and PRs. ``docs/BACKLOG.md`` is a small stub that feature PRs never edit, so parallel PRs
cannot conflict on it. This script gives humans and coding agents (including small local
models with a 32k context window) compact, offline, deterministic views:

    python3 scripts/backlog.py list [--status todo,in-progress] [--priority P1] [--grep TEXT]
    python3 scripts/backlog.py show BITB-313 [--full]
    python3 scripts/backlog.py changelog [--since 2026-11-01] [--limit 50]
    python3 scripts/backlog.py check
    python3 scripts/backlog.py render
    python3 scripts/backlog.py next-id

Standard library only: no PyYAML, no network, no GitHub token. The front matter uses a
tiny YAML subset (one ``key: value`` per line, inline ``[a, b]`` lists, no comments) that
this file parses and writes itself, so a status change is a single, uniquely anchored
line edit.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_ROOT = Path(__file__).resolve().parent.parent

STORY_DIRS: tuple[str, ...] = ("docs/BACKLOG_STORIES", "docs/DONE")

STATUSES: tuple[str, ...] = ("todo", "in-progress", "in-review", "blocked", "done", "cancelled")
PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3", "icebox")
SIZES: tuple[str, ...] = ("XS", "S", "M", "L", "XL")
CLOSED_STATUSES: frozenset[str] = frozenset({"done", "cancelled"})

# Fixed key order of the front matter (one key per line).
FIELD_ORDER: tuple[str, ...] = (
    "id",
    "status",
    "priority",
    "size",
    "rank",
    "created",
    "prs",
    "follow_ups",
    "depends_on",
    "supersedes",
)
_LIST_INT_KEYS = frozenset({"prs"})
_LIST_ID_KEYS = frozenset({"follow_ups", "depends_on"})

# Deliberate exceptions: groups of files (repo-relative paths) that may share one BITB-NNN id
# because they are companion documents of a single story, not a collision (BITB-111). Add an
# entry only with a comment explaining why the files are one story, not two.
ALLOWED_SHARED_ID_GROUPS: tuple[frozenset[str], ...] = (
    # BITB-147: the CI/Ollama-timeout investigation was archived as a paired analysis +
    # resolution doc, both kept under one id as companion halves of one write-up.
    frozenset(
        {
            "docs/DONE/BITB-147-ANALYSIS-CI-OLLAMA-TIMEOUT.md",
            "docs/DONE/BITB-147-RESOLUTION-CI-OLLAMA-TIMEOUT.md",
        }
    ),
)

_ID_RE = re.compile(r"^BITB-\d{3,}$")
_FILENAME_ID_RE = re.compile(r"^(BITB-\d+)-")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TITLE_PREFIX_RE = re.compile(r"^BITB-\d+\s*:?\s*")
_BOLD_HEADER_RE = re.compile(r"^\*\*(Status|Priority|Size|Created):\*\*")
_FIX_HINT = "see docs/backlog/LEGEND.md for the front-matter schema"


class FrontMatterError(ValueError):
    """Raised when a front-matter block does not follow the supported schema."""


# --------------------------------------------------------------------------------------
# Front-matter parsing / writing
# --------------------------------------------------------------------------------------


def _parse_scalar(raw: str) -> str:
    return raw.strip()


def _parse_list(key: str, raw: str) -> list[Any]:
    raw = raw.strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        raise FrontMatterError(f"'{key}' must be an inline list like [a, b], got {raw!r}")
    inner = raw[1:-1].strip()
    items = [part.strip() for part in inner.split(",")] if inner else []
    if any(not item for item in items):
        raise FrontMatterError(f"'{key}' has an empty list item: {raw!r}")
    if key in _LIST_INT_KEYS:
        try:
            return [int(item) for item in items]
        except ValueError as exc:
            raise FrontMatterError(f"'{key}' must be a list of integers, got {raw!r}") from exc
    return items


def split_front_matter(text: str) -> tuple[str | None, str]:
    """Return ``(front_matter_block, rest)``; the block is ``None`` when absent."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 3)
    if end == -1:
        if text.endswith("\n---"):
            return text[4:-4], ""
        raise FrontMatterError("front matter opened with '---' but is never closed")
    return text[4 : end + 1], text[end + 5 :]


def parse_front_matter(block: str) -> dict[str, Any]:
    """Parse the supported YAML subset into a dict (values: str, int or list)."""
    meta: dict[str, Any] = {}
    for lineno, line in enumerate(block.splitlines(), start=1):
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            raise FrontMatterError(f"line {lineno}: comments are not allowed in front matter")
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not re.fullmatch(r"[a-z_]+", key):
            raise FrontMatterError(f"line {lineno}: expected 'key: value', got {line!r}")
        if key in meta:
            raise FrontMatterError(f"line {lineno}: duplicate key '{key}'")
        if key in _LIST_INT_KEYS or key in _LIST_ID_KEYS:
            meta[key] = _parse_list(key, value)
        elif key == "rank":
            try:
                meta[key] = int(value.strip())
            except ValueError as exc:
                raise FrontMatterError(f"line {lineno}: rank must be an integer") from exc
        else:
            meta[key] = _parse_scalar(value)
    return meta


def format_front_matter(meta: dict[str, Any]) -> str:
    """Render ``meta`` as a front-matter block (``---`` fences included, fixed key order)."""
    lines = ["---"]
    for key in FIELD_ORDER:
        if key not in meta:
            continue
        value = meta[key]
        if isinstance(value, list):
            if not value:
                continue
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif value is None or value == "":
            continue
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# Story loading
# --------------------------------------------------------------------------------------


@dataclass
class Story:
    path: str  # repo-relative, posix
    id: str  # from the filename
    title: str
    meta: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    header_lines: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return str(self.meta.get("status", "?"))

    @property
    def priority(self) -> str:
        return str(self.meta.get("priority", "?"))

    @property
    def size(self) -> str:
        return str(self.meta.get("size", "-"))

    @property
    def prs(self) -> list[int]:
        return list(self.meta.get("prs", []))

    @property
    def rank(self) -> int | None:
        rank = self.meta.get("rank")
        return rank if isinstance(rank, int) else None

    @property
    def number(self) -> int:
        return int(self.id.split("-")[1])


def _title_from_body(body: str) -> tuple[str | None, list[str]]:
    """Return the first H1 (BITB prefix stripped) and the leading metadata block lines."""
    lines = body.splitlines()
    title: str | None = None
    h1_index = -1
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            title = _TITLE_PREFIX_RE.sub("", line[2:].strip())
            h1_index = idx
            break
    header: list[str] = []
    if h1_index >= 0:
        for line in lines[h1_index + 1 :]:
            if line.strip() and not line.startswith("**"):
                break
            header.append(line)
    return title, header


def load_story(root: Path, path: Path) -> Story:
    rel = path.relative_to(root).as_posix()
    match = _FILENAME_ID_RE.match(path.name)
    story = Story(path=rel, id=match.group(1) if match else "", title="")
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        story.errors.append(
            f"not valid UTF-8 ({exc.reason} at byte {exc.start}) — re-save as UTF-8"
        )
        return story
    if text.startswith("\ufeff"):
        story.errors.append("starts with a UTF-8 BOM — remove it (the file must begin with '---')")
        text = text.lstrip("\ufeff")
    try:
        block, body = split_front_matter(text)
    except FrontMatterError as exc:
        story.errors.append(f"{exc} — close the front matter with a line containing only '---'")
        return story
    title, header = _title_from_body(body)
    story.title = title or ""
    story.header_lines = header
    if title is None:
        story.errors.append("no '# BITB-NNN: Title' heading — add the story title as an H1")
    if block is None:
        story.errors.append("no front matter — add a '---' block (" + _FIX_HINT + ")")
        return story
    try:
        story.meta = parse_front_matter(block)
    except FrontMatterError as exc:
        story.errors.append(f"bad front matter: {exc} — {_FIX_HINT}")
    return story


def story_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in STORY_DIRS:
        directory = root / rel
        if directory.is_dir():
            files.extend(p for p in sorted(directory.glob("*.md")) if _FILENAME_ID_RE.match(p.name))
    return files


def load_all(root: Path) -> list[Story]:
    return [load_story(root, p) for p in story_files(root)]


def sort_key(story: Story) -> tuple[int, int, int, str]:
    prio = PRIORITIES.index(story.priority) if story.priority in PRIORITIES else len(PRIORITIES)
    rank = story.rank
    return (prio, rank if rank is not None else 10**9, story.number, story.path)


# --------------------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------------------


def _group_is_allowed(paths: set[str]) -> bool:
    """A shared id is allowed when its files are exactly one allowlisted companion group."""
    remaining = set(paths)
    groups = 0
    for group in ALLOWED_SHARED_ID_GROUPS:
        if group <= remaining:
            remaining -= group
            groups += 1
    return len(remaining) + groups <= 1


def check_stories(stories: list[Story]) -> list[str]:  # noqa: C901
    """Return ``path: problem — fix hint`` lines for every violation."""
    errors: list[str] = []
    known_ids = {s.id for s in stories}
    by_id: dict[str, list[Story]] = {}
    for story in stories:
        by_id.setdefault(story.id, []).append(story)
        for err in story.errors:
            errors.append(f"{story.path}: {err}")
        if story.id and not _ID_RE.match(story.id):
            errors.append(
                f"{story.path}: id {story.id!r} must be zero-padded to 3 digits "
                f"(e.g. BITB-{story.number:03d}) — rename the file and set the 'id:' line"
            )
        meta = story.meta
        if not meta:
            continue
        if meta.get("id") != story.id:
            errors.append(
                f"{story.path}: front-matter id {meta.get('id')!r} does not match the filename "
                f"id {story.id!r} — set 'id: {story.id}'"
            )
        if "id" in meta and not _ID_RE.match(str(meta["id"])):
            errors.append(
                f"{story.path}: id must look like BITB-123 (zero-padded, 3+ digits) "
                "— fix the 'id:' line"
            )
        if meta.get("status") not in STATUSES:
            errors.append(
                f"{story.path}: status {meta.get('status')!r} invalid — use one of "
                + ", ".join(STATUSES)
            )
        if meta.get("priority") not in PRIORITIES:
            errors.append(
                f"{story.path}: priority {meta.get('priority')!r} invalid — use one of "
                + ", ".join(PRIORITIES)
            )
        if "size" in meta and meta["size"] not in SIZES:
            errors.append(
                f"{story.path}: size {meta['size']!r} invalid — use one of " + ", ".join(SIZES)
            )
        if "created" in meta and not _DATE_RE.match(str(meta["created"])):
            errors.append(f"{story.path}: created must be an ISO date (YYYY-MM-DD)")
        for key in sorted(set(meta) - set(FIELD_ORDER)):
            errors.append(f"{story.path}: unknown front-matter key '{key}' — remove it")
        for key in ("follow_ups", "depends_on"):
            for ref in meta.get(key, []):
                if ref not in known_ids:
                    errors.append(
                        f"{story.path}: {key} references {ref}, which has no story file "
                        "— fix the id or create the story"
                    )
        for line in story.header_lines:
            if _BOLD_HEADER_RE.match(line):
                errors.append(
                    f"{story.path}: header still has a bold '{line.split(':**')[0][2:]}' line — "
                    "move the value into the front matter and delete the bold line"
                )
                break
    for story_id, group in sorted(by_id.items()):
        if len(group) > 1 and not _group_is_allowed({s.path for s in group}):
            files = ", ".join(sorted(s.path for s in group))
            errors.append(
                f"{story_id}: maps to {len(group)} files ({files}) — each id must name exactly "
                "one story; renumber the later one (see AGENTS.md -> Story IDs are sequential)"
            )
    return errors


# --------------------------------------------------------------------------------------
# list / show / render / next-id
# --------------------------------------------------------------------------------------


def _csv(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def filter_stories(
    stories: list[Story],
    *,
    status: str | None = None,
    priority: str | None = None,
    size: str | None = None,
    grep: str | None = None,
    show_all: bool = False,
) -> list[Story]:
    statuses = _csv(status)
    priorities = {p.upper() if p.upper().startswith("P") else p for p in _csv(priority) or set()}
    sizes = {s.upper() for s in _csv(size) or set()}
    needle = grep.lower() if grep else None
    out = []
    for story in stories:
        if statuses is not None:
            if story.status not in statuses:
                continue
        elif not show_all and story.status in CLOSED_STATUSES:
            continue
        if priorities and story.priority not in priorities:
            continue
        if sizes and story.size not in sizes:
            continue
        if needle and needle not in f"{story.id} {story.title}".lower():
            continue
        out.append(story)
    return sorted(out, key=sort_key)


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _pr_label(story: Story) -> str:
    return f"#{story.prs[-1]}" if story.prs else "-"


# Every compact line is capped at this many bytes so that 165 open stories (today's backlog)
# stay under the 12 KB (~3k token) agent budget regardless of title length (BITB-313).
MAX_LINE_BYTES = 73


def _truncate_bytes(text: str, budget: int) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= budget:
        return text
    cut = raw[: max(budget - 3, 0)].decode("utf-8", errors="ignore").rstrip()
    return cut + "…"


def format_compact(stories: list[Story], max_line: int = MAX_LINE_BYTES) -> str:
    lines = []
    for s in stories:
        prefix = f"{s.id} {s.priority} {s.size} {s.status} {_pr_label(s)} "
        budget = max(max_line - len(prefix.encode("utf-8")), 12)
        lines.append(prefix + _truncate_bytes(s.title, budget))
    return "\n".join(lines) + ("\n" if lines else "")


def format_md(stories: list[Story]) -> str:
    lines = ["| ID | Pri | Size | Status | PR | Title |", "|---|---|---|---|---|---|"]
    for s in stories:
        title = s.title.replace("|", "\\|")
        lines.append(
            f"| [{s.id}]({s.path.removeprefix('docs/')}) | {s.priority} | {s.size} | {s.status} "
            f"| {_pr_label(s)} | {title} |"
        )
    return "\n".join(lines) + "\n"


def format_json(stories: list[Story]) -> str:
    rows = [{**s.meta, "title": s.title, "path": s.path} for s in stories]
    return json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_index(stories: list[Story]) -> str:
    """Full deterministic markdown index (P0->P3, icebox, then done/cancelled)."""
    open_stories = [s for s in stories if s.status not in CLOSED_STATUSES]
    closed = [s for s in stories if s.status in CLOSED_STATUSES]
    out = ["# Backlog index", "", f"{len(stories)} stories ({len(open_stories)} open).", ""]
    for prio in PRIORITIES:
        group = sorted((s for s in open_stories if s.priority == prio), key=sort_key)
        if not group:
            continue
        out += [f"## {prio} ({len(group)})", "", format_md(group).rstrip("\n"), ""]
    if closed:
        out += [
            f"## Done / cancelled ({len(closed)})",
            "",
            format_md(sorted(closed, key=lambda s: (-s.number, s.path))).rstrip("\n"),
            "",
        ]
    return "\n".join(out)


def next_id(stories: list[Story]) -> str:
    highest = max((s.number for s in stories if s.id), default=0)
    return f"BITB-{highest + 1:03d}"


def normalize_id(raw: str) -> str | None:
    """``BITB-1``, ``bitb-001`` and ``1`` all become ``BITB-001``; ``None`` when not an id."""
    match = re.fullmatch(r"(?:BITB-)?(\d+)", raw.strip(), re.IGNORECASE)
    return f"BITB-{int(match.group(1)):03d}" if match else None


def show_story(root: Path, stories: list[Story], story_id: str, full: bool) -> str:
    wanted = normalize_id(story_id) or story_id.upper()
    matches = [s for s in stories if s.id == wanted]
    if not matches:
        raise SystemExit(f"{story_id}: no such story (try: python3 scripts/backlog.py list --all)")
    out: list[str] = []
    for story in matches:
        out.append(f"path: {story.path}")
        if full:
            out.append((root / story.path).read_text(encoding="utf-8").rstrip("\n"))
        else:
            out.append(format_front_matter(story.meta).rstrip("\n"))
            out.append(f"title: {_truncate(story.title, 120)}")
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# changelog (derived from git history, never hand-written)
# --------------------------------------------------------------------------------------

_BITB_IN_SUBJECT = re.compile(r"BITB-(\d+(?:/\d+)*)")
_PR_IN_SUBJECT = re.compile(r"\(#\d+\)")


def expand_ids(subject: str) -> list[str]:
    """Every story id in ``subject``; slash forms like ``BITB-282/283`` expand to both ids."""
    found: list[str] = []
    for match in _BITB_IN_SUBJECT.finditer(subject):
        found.extend(f"BITB-{int(num):03d}" for num in match.group(1).split("/"))
    return list(dict.fromkeys(found))


def git_changelog(
    root: Path, ref: str = "origin/main", since: str | None = None, limit: int | None = None
) -> list[str]:
    """Entries ``- DATE: BITB-NNN[, BITB-MMM] — subject`` from first-parent subjects."""

    def run(target: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "log", "--first-parent", "--format=%cs%x09%s", target],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

    result = run(ref)
    if result.returncode != 0 and ref != "HEAD":
        result = run("HEAD")
    if result.returncode != 0:
        raise SystemExit(f"git log failed: {result.stderr.strip()}")
    entries: list[str] = []
    for line in result.stdout.splitlines():
        date, _, subject = line.partition("\t")
        ids = expand_ids(subject)
        if not ids or not _PR_IN_SUBJECT.search(subject):
            continue
        if since and date < since:
            continue
        entries.append(f"- {date}: {', '.join(ids)} — {subject}")
        if limit is not None and len(entries) >= limit:
            break
    return entries


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backlog.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=_DEFAULT_ROOT, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="one line per story")
    p_list.add_argument("--status", help="comma list; default: every open status")
    p_list.add_argument("--priority", help="comma list, e.g. P0,P1")
    p_list.add_argument("--size", help="comma list, e.g. XS,S")
    p_list.add_argument("--grep", help="case-insensitive text in id + title")
    p_list.add_argument("--all", action="store_true", help="include done and cancelled")
    p_list.add_argument("--limit", type=int, help="print at most N stories")
    p_list.add_argument("--format", choices=("compact", "md", "json"), default="compact")

    p_show = sub.add_parser("show", help="path + front matter of one story")
    p_show.add_argument("id")
    p_show.add_argument("--full", action="store_true", help="print the whole file")

    p_log = sub.add_parser("changelog", help="derived from git log subjects")
    p_log.add_argument("--ref", default="origin/main")
    p_log.add_argument("--since", help="YYYY-MM-DD")
    p_log.add_argument("--limit", type=int, help="print at most N entries")

    sub.add_parser("check", help="validate every story's front matter")
    sub.add_parser("render", help="full markdown index to stdout")
    sub.add_parser("next-id", help="highest id + 1 in the local tree")
    return parser


def _validated(
    parser: argparse.ArgumentParser, flag: str, raw: str | None, allowed: tuple[str, ...]
) -> str | None:
    """Normalise a comma list against the enum (case-insensitive); exit 2 on a bad value."""
    if not raw:
        return None
    by_lower = {value.lower(): value for value in allowed}
    values = []
    for part in (p.strip() for p in raw.split(",") if p.strip()):
        if part.lower() not in by_lower:
            parser.error(f"{flag}: invalid value {part!r}; allowed: {', '.join(allowed)}")
        values.append(by_lower[part.lower()])
    return ",".join(values)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(parser, args)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:  # noqa: C901
    root: Path = args.root
    if args.command == "changelog":
        entries = git_changelog(root, args.ref, args.since, args.limit)
        sys.stdout.write("\n".join(entries) + ("\n" if entries else ""))
        return 0
    stories = load_all(root)
    if args.command == "check":
        errors = check_stories(stories)
        if errors:
            print(f"FAIL: {len(errors)} problem(s)\n", file=sys.stderr)
            for err in errors:
                print(f"  * {err}", file=sys.stderr)
            return 1
        print(f"OK: {len(stories)} stories")
        return 0
    if args.command == "list":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit: must be at least 1")
        picked = filter_stories(
            stories,
            status=_validated(parser, "--status", args.status, STATUSES),
            priority=_validated(parser, "--priority", args.priority, PRIORITIES),
            size=_validated(parser, "--size", args.size, SIZES),
            grep=args.grep,
            show_all=args.all,
        )
        if args.limit is not None:
            picked = picked[: args.limit]
        formatter = {"compact": format_compact, "md": format_md, "json": format_json}
        sys.stdout.write(formatter[args.format](picked))
        return 0
    if args.command == "show":
        if normalize_id(args.id) is None and not re.fullmatch(r"BITB-\d+", args.id, re.IGNORECASE):
            parser.error(f"invalid story id {args.id!r}; expected BITB-NNN")
        sys.stdout.write(show_story(root, stories, args.id, args.full))
        return 0
    if args.command == "render":
        sys.stdout.write(render_index(stories))
        return 0
    if args.command == "next-id":
        print(next_id(stories))
        return 0
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
