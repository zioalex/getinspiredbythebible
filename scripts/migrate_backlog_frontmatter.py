#!/usr/bin/env python3
"""One-off migration: bold story-header lines + BACKLOG.md index -> YAML front matter (BITB-313).

Before BITB-313 each story's status lived twice: in the bold ``**Status:**`` /
``**Priority:**`` / ``**Size:**`` / ``**Created:**`` header lines of its story file and in
its entry of the 424 KB ``docs/BACKLOG.md`` index. This script writes the front matter that
becomes the single source of truth (see ``scripts/backlog.py``):

* the story file wins; the index only fills gaps (``status`` from the index only when the
  story file has no ``**Status:**`` line);
* free-text statuses are normalised to the enum; PR numbers found in the status text move to
  ``prs``; remaining free text is kept as a ``**Status note:**`` line (nothing is lost);
* ``rank`` is seeded 10, 20, 30... from the index order inside each P0-P3 section;
* index entries without a story file (BITB-000..013) become new story files;
* it is idempotent: a file that already has front matter is left untouched.

Usage:

    python3 scripts/migrate_backlog_frontmatter.py --dry-run   # print the report only
    python3 scripts/migrate_backlog_frontmatter.py             # write the files

``--backlog PATH`` and ``--root PATH`` exist for tests. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backlog  # noqa: E402  (sibling module; path set up above)

_ROOT = Path(__file__).resolve().parent.parent

_EMOJI_STATUS = {
    "🎯": "todo",
    "🚧": "in-progress",
    "🔍": "in-review",
    "🔄": "in-review",
    "✅": "done",
    "❌": "cancelled",
    "⏸": "blocked",
}
_PRIORITY_WORDS = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3"}
_SIZE_WORDS = {"small": "S", "medium": "M", "large": "L"}
_SECTION_PRIORITY = {"P0": "P0", "P1": "P1", "P2": "P2", "P3": "P3", "Icebox": "icebox"}
_KEY_RE = re.compile(r"^\*\*(Status|Priority|Size|Created|Date):\*\*\s*(.*)$")
_HEADING_RE = re.compile(r"^###\s+(\S*?)\s*BITB-(\d+):\s*(.*)$")
_PIPE_SPLIT_RE = re.compile(r"\s+\|\s+(?=\*\*[A-Za-z ]+:\*\*)")
_WRAP_WIDTH = 75  # a Size line at least this long may continue on the next line
_WRAPPING_KEYS = frozenset({"Status", "Priority", "Size"})
_MIGRATION_DATE = "2026-11-13"

# Corrections for individual stories where the generic rules read the source text wrongly.
# BITB-002: "PR #171 merged, ready to start" -- #171 is a prerequisite, not the story's own PR.
_NO_PRS = frozenset({"BITB-002"})
# BITB-023/024: the old index held a *different* legacy story under the same number.
_EXTRA_NOTES: dict[str, str] = {
    story_id: (
        f"**Migration note ({_MIGRATION_DATE}, index):** the old `docs/BACKLOG.md` entry with "
        "the same number was a different legacy story, recoverable via "
        "`git show 2a8b257d:docs/BACKLOG.md`."
    )
    for story_id in ("BITB-023", "BITB-024")
}


def _note(kind: str, text: str) -> str:
    """A frozen migration note; labelled so it is never mistaken for a live status copy."""
    return f"**Migration note ({_MIGRATION_DATE}, {kind}):** {text}"


class MigrationError(Exception):
    """An unrecognised value: the run aborts and names the file."""


# --------------------------------------------------------------------------------------
# Value normalisation
# --------------------------------------------------------------------------------------

_STATUS_WORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^todo\s*(→|->)\s*done\b", re.I), "done"),
    (re.compile(r"^(todo|to do)\b", re.I), "todo"),
    (re.compile(r"^in[ -]progress\b", re.I), "in-progress"),
    (re.compile(r"^in[ -]review\b", re.I), "in-review"),
    (re.compile(r"^in pr\b", re.I), "in-review"),
    (re.compile(r"^(done|merged|complete[d]?)\b", re.I), "done"),
    (re.compile(r"^(cancelled|canceled)\b", re.I), "cancelled"),
    (re.compile(r"^blocked\b", re.I), "blocked"),
)
# Labels that map to an enum value but whose wording carries meaning, kept verbatim in the note.
_STATUS_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^backlog\b", re.I), "todo"),
    (re.compile(r"^proposed\b", re.I), "todo"),
    (re.compile(r"^partially shipped\b", re.I), "in-progress"),
    (re.compile(r"^code complete\b", re.I), "in-review"),
    (re.compile(r"^gated\b", re.I), "blocked"),
    (re.compile(r"^resolved\b", re.I), "done"),
)


@dataclass
class StatusInfo:
    status: str
    note: str = ""
    prs: list[int] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


def _strip_leading_symbols(text: str) -> str:
    return re.sub(r"^[^\w(]+", "", text.strip())


def normalize_status(raw: str, where: str = "") -> StatusInfo:
    """Map free-text status to the enum; raise ``MigrationError`` on an unknown value."""
    text = _strip_leading_symbols(raw)
    status: str | None = None
    note = text
    for pattern, value in _STATUS_WORDS:
        match = pattern.match(text)
        if match:
            status, note = value, text[match.end() :]
            break
    else:
        for pattern, value in _STATUS_LABELS:
            if pattern.match(text):
                status, note = value, text
                break
    if status is None:
        raise MigrationError(f"{where}: unrecognised status {raw!r}")
    note = note.strip().lstrip("—–-:|,").strip()
    without_blockers = re.sub(r"blocked (?:by|on) PR #\d+", "", text, flags=re.I)
    prs = list(dict.fromkeys(int(n) for n in re.findall(r"#(\d{2,5})\b", without_blockers)))
    deps = list(
        dict.fromkeys(re.findall(r"(?:blocked (?:by|on)|gated on)\s+(BITB-\d+)", text, flags=re.I))
    )
    if status == "blocked":
        deps = list(dict.fromkeys(re.findall(r"BITB-\d+", text)))
    return StatusInfo(status=status, note=note, prs=prs, depends_on=deps)


def status_from_emoji(heading_emoji: str) -> str | None:
    for emoji, status in _EMOJI_STATUS.items():
        if emoji in heading_emoji:
            return status
    return None


def normalize_priority(raw: str) -> tuple[str | None, str]:
    """Return ``(P0..P3 or None, leftover note)``; pure glosses like ``(High)`` are dropped."""
    text = raw.strip()
    match = re.search(r"\bP([0-3])\b", text)
    if match:
        prio = f"P{match.group(1)}"
        leftover = (text[: match.start()] + text[match.end() :]).strip()
    else:
        word = re.match(r"^(critical|high|medium|low)\b", text, re.I)
        if not word:
            return None, text
        prio = _PRIORITY_WORDS[word.group(1).lower()]
        leftover = text[word.end() :].strip()
    leftover = leftover.lstrip("—–-:").strip()
    if re.fullmatch(r"\((critical(/blocker)?|high|medium|low)\)", leftover, re.I):
        leftover = ""
    return prio, leftover


def normalize_size(raw: str) -> tuple[str | None, str]:
    """Return ``(XS..XL or None, note)``; a range keeps the larger size and the original."""
    text = raw.strip()
    match = re.match(
        r"^(?:provisional\s+)?(XS|XL|S|M|L)(?:\s*[–/-]\s*(XS|XL|S|M|L))?(?![A-Za-z])", text, re.I
    )
    if not match:
        word = re.match(r"^(small|medium|large)\b", text, re.I)
        if not word:
            return None, text
        return _SIZE_WORDS[word.group(1).lower()], text[word.end() :].strip()
    size = (match.group(2) or match.group(1)).upper()
    leftover = text[match.end() :].strip()
    if match.group(2) or text.lower().startswith("provisional"):
        return size, text
    if re.fullmatch(r"\(\s*[<~]?\s*\d[^)]{0,12}(hr|hour|day|week)s?\s*\)", leftover, re.I):
        leftover = ""
    return size, leftover


# --------------------------------------------------------------------------------------
# Header parsing (story files)
# --------------------------------------------------------------------------------------


@dataclass
class Header:
    """Raw metadata lifted from a header block or an index entry."""

    status_raw: str | None = None
    priority_raw: str | None = None
    size_raw: str | None = None
    created_raw: str | None = None
    date_raw: str | None = None
    extras: list[str] = field(default_factory=list)  # unknown pipe segments, kept verbatim


def _record(header: Header, key: str, value: str) -> None:
    attr = {
        "Status": "status_raw",
        "Priority": "priority_raw",
        "Size": "size_raw",
        "Created": "created_raw",
        "Date": "date_raw",
    }[key]
    if getattr(header, attr) is None:
        setattr(header, attr, value.strip())


def _first_value(header: Header, key: str) -> str | None:
    attr = {
        "Status": "status_raw",
        "Priority": "priority_raw",
        "Size": "size_raw",
        "Created": "created_raw",
        "Date": "date_raw",
    }[key]
    value: str | None = getattr(header, attr)
    return value


def parse_header_lines(lines: list[str]) -> tuple[Header, set[int], int]:
    """Scan ``lines`` (top to the first H2) and consume the first occurrence of each key.

    Returns ``(header, removed line indexes, index of the first removed line)``.
    """
    header = Header()
    removed: set[int] = set()
    first_removed = -1
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        match = _KEY_RE.match(lines[i])
        if match and match.group(1) in seen:
            # An exact repeat of an already-consumed key (e.g. a duplicated Size line) is
            # dropped; a differing repeat is a different statement and stays in the body.
            if match.group(2).strip() == _first_value(header, match.group(1)):
                removed.add(i)
            i += 1
            continue
        if not match:
            i += 1
            continue
        key, rest = match.group(1), match.group(2)
        if key == "Date":
            seen.add(key)
            _record(header, key, rest)
            removed.add(i)
            first_removed = i if first_removed < 0 else first_removed
            i += 1
            continue
        segments = _PIPE_SPLIT_RE.split(rest)
        value_lines = [segments[0]]
        consumed = [i]
        if len(segments) == 1 and key in _WRAPPING_KEYS:
            # A wrapped value continues on the following non-blank, non-bold lines. Status and
            # Priority always wrap; Size only when its first line is long enough to have wrapped.
            j = i
            while (
                (key != "Size" or len(lines[j]) >= _WRAP_WIDTH)
                and j + 1 < len(lines)
                and lines[j + 1].strip()
                and not lines[j + 1].startswith(("**", "#", "---"))
            ):
                j += 1
                value_lines.append(lines[j].strip())
                consumed.append(j)
        seen.add(key)
        _record(header, key, " ".join(v for v in value_lines if v))
        for extra in segments[1:]:
            sub = re.match(r"^\*\*([A-Za-z ]+):\*\*\s*(.*)$", extra.strip())
            if sub and sub.group(1) in {"Status", "Priority", "Size", "Created", "Date"}:
                seen.add(sub.group(1))
                _record(header, sub.group(1), sub.group(2))
            else:
                header.extras.append(extra.strip())
        removed.update(consumed)
        first_removed = min(consumed) if first_removed < 0 else min(first_removed, min(consumed))
        i = consumed[-1] + 1
    return header, removed, first_removed


# --------------------------------------------------------------------------------------
# Index parsing (docs/BACKLOG.md)
# --------------------------------------------------------------------------------------


@dataclass
class IndexEntry:
    id: str
    title: str
    emoji: str
    section: str
    header: Header
    body: list[str]
    rank: int | None = None


def _section_name(heading: str) -> str:
    for key in ("P0", "P1", "P2", "P3", "Icebox"):
        if re.match(rf"^{key}\b", heading):
            return key
    if heading.startswith("Done"):
        return "Done"
    return "other"


def parse_index(text: str) -> tuple[dict[str, IndexEntry], list[str]]:
    """Return ``({id: first entry}, [duplicate ids])``; ranks seeded per P0-P3 section."""
    lines = text.split("\n")
    entries: dict[str, IndexEntry] = {}
    duplicates: list[str] = []
    section = "other"
    counters: dict[str, int] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        h2 = re.match(r"^##\s+(.*)$", line)
        if h2:
            section = _section_name(h2.group(1))
            i += 1
            continue
        match = _HEADING_RE.match(line)
        if not match:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not re.match(r"^#{1,3}\s", lines[j]):
            j += 1
        block = lines[i + 1 : j]
        story_id = f"BITB-{int(match.group(2)):03d}"
        if story_id in entries:
            duplicates.append(story_id)
        else:
            header, removed, _ = parse_header_lines(block)
            body = [ln for k, ln in enumerate(block) if k not in removed]
            entry = IndexEntry(
                id=story_id,
                title=match.group(3).strip(),
                emoji=match.group(1),
                section=section,
                header=header,
                body=body,
            )
            if section in _SECTION_PRIORITY and section != "Icebox":
                counters[section] = counters.get(section, 0) + 10
                entry.rank = counters[section]
            entries[story_id] = entry
        i = j
    return entries, duplicates


# --------------------------------------------------------------------------------------
# Merge + rewrite
# --------------------------------------------------------------------------------------


@dataclass
class Report:
    migrated: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    created_from_index: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    defaults: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    created_missing: int = 0
    priority_moves: list[tuple[str, str, str, str]] = field(default_factory=list)

    def render(self) -> str:
        out = [
            "Migration report",
            f"  migrated story files:        {len(self.migrated)}",
            f"  already migrated (skipped):  {len(self.skipped_existing)}",
            f"  created from index only:     {len(self.created_from_index)}",
            f"  file-vs-index conflicts:     {len(self.conflicts)} (resolved, see below)",
            f"  defaulted fields:            {len(self.defaults)}",
            f"  created date omitted:        {self.created_missing} (no date anywhere)",
            f"  status/priority notes kept:  {len(self.notes)}",
            f"  duplicate index headings:    {len(self.duplicates)} (first one wins)",
            f"  anomalies:                   {len(self.anomalies)}",
        ]
        for title, items in (
            ("Created from index", self.created_from_index),
            ("Conflicts", self.conflicts),
            ("Defaults applied", self.defaults),
            ("Duplicate index headings", self.duplicates),
            ("Anomalies", self.anomalies),
        ):
            if items:
                out.append(f"\n{title}:")
                out.extend(f"  - {item}" for item in items)
        return "\n".join(out) + "\n"


def _first_date(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
    return match.group(0) if match else None


def _build_meta(  # noqa: C901
    story_id: str,
    header: Header,
    entry: IndexEntry | None,
    where: str,
    report: Report,
    known_ids: set[str],
    heading_emoji: str = "",
    in_done_dir: bool = False,
) -> tuple[dict[str, object], list[str]]:
    """Merge file header + index entry into front-matter ``meta`` and note lines."""
    notes: list[str] = []
    meta: dict[str, object] = {"id": story_id}

    # status
    info: StatusInfo | None = None
    if header.status_raw is not None:
        info = normalize_status(header.status_raw, where)
        if entry and entry.header.status_raw:
            idx_info: StatusInfo | None
            try:
                idx_info = normalize_status(entry.header.status_raw, where)
            except MigrationError:
                idx_info = None
            if idx_info and idx_info.status != info.status:
                evidence = in_done_dir or re.search(
                    r"merged|shipped|completed|verified", entry.header.status_raw, re.I
                )
                index_wins = (info.status == "todo" and idx_info.status != "todo") or (
                    idx_info.status == "done"
                    and info.status not in backlog.CLOSED_STATUSES
                    and bool(evidence)
                )
                verdict = "index wins (stale file marker)" if index_wins else "file wins"
                report.conflicts.append(
                    f"{story_id} status: file={info.status} index={idx_info.status} -> {verdict}"
                )
                if index_wins:
                    info = StatusInfo(
                        status=idx_info.status,
                        note=idx_info.note,
                        prs=idx_info.prs,
                        depends_on=idx_info.depends_on,
                    )
    elif entry and entry.header.status_raw is not None:
        info = normalize_status(entry.header.status_raw, f"{where} (index)")
    if info is None:
        emoji_status = status_from_emoji(heading_emoji or (entry.emoji if entry else ""))
        if emoji_status:
            info = StatusInfo(status=emoji_status)
            report.defaults.append(f"{story_id} status={emoji_status} (from heading emoji)")
        else:
            info = StatusInfo(status="todo")
            report.defaults.append(f"{story_id} status=todo (no status anywhere)")
    meta["status"] = info.status
    if info.note:
        notes.insert(0, _note("status", info.note))
        report.notes.append(story_id)

    # priority
    prio: str | None = None
    prio_leftover = ""
    if header.priority_raw is not None:
        prio, prio_leftover = normalize_priority(header.priority_raw)
        if prio is None:
            raise MigrationError(f"{where}: unrecognised priority {header.priority_raw!r}")
    index_prio: str | None = None
    if entry:
        if entry.header.priority_raw is not None:
            index_prio, idx_left = normalize_priority(entry.header.priority_raw)
            if prio is None:
                prio_leftover = idx_left
        elif entry.section in _SECTION_PRIORITY:
            index_prio = _SECTION_PRIORITY[entry.section]
    if prio and index_prio and prio != index_prio:
        report.conflicts.append(f"{story_id} priority: file={prio} index={index_prio}")
    if prio is None:
        prio = index_prio
    if prio is None:
        prio = "P3"
        report.defaults.append(f"{story_id} priority=P3 (no priority anywhere)")
    meta["priority"] = prio
    if prio_leftover:
        notes.append(_note("priority", prio_leftover))

    # size
    size: str | None = None
    size_left = ""
    raw_size = (
        header.size_raw
        if header.size_raw is not None
        else (entry.header.size_raw if entry else None)
    )
    if raw_size is not None:
        size, size_left = normalize_size(raw_size)
        if size is None:
            report.anomalies.append(f"{story_id}: unrecognised size {raw_size!r} (omitted)")
            size_left = raw_size
    if size:
        meta["size"] = size
    if size_left:
        notes.append(_note("size", size_left))

    section_prio = _SECTION_PRIORITY.get(entry.section) if entry else None
    if entry and entry.rank is not None and prio == section_prio:
        meta["rank"] = entry.rank
    if section_prio and prio != section_prio and info.status not in backlog.CLOSED_STATUSES:
        source = (
            "story file Priority line"
            if header.priority_raw is not None
            else (
                "index Priority line"
                if entry and entry.header.priority_raw is not None
                else "default"
            )
        )
        report.priority_moves.append((story_id, entry.section if entry else "", prio, source))

    created = (
        _first_date(header.created_raw)
        or _first_date(header.date_raw)
        or (_first_date(entry.header.created_raw) if entry else None)
        or (_first_date(entry.header.date_raw) if entry else None)
    )
    if created:
        meta["created"] = created
    else:
        report.created_missing += 1
    if header.created_raw and not _first_date(header.created_raw):
        notes.append(_note("created", header.created_raw))

    meta["prs"] = [] if story_id in _NO_PRS else info.prs
    meta["depends_on"] = [d for d in info.depends_on if d in known_ids and d != story_id]
    notes.extend(header.extras)
    if story_id in _EXTRA_NOTES:
        notes.append(_EXTRA_NOTES[story_id])
    return meta, notes


def rewrite_story(text: str, meta: dict[str, object], notes: list[str], removed: set[int]) -> str:
    """Drop the consumed header lines, insert ``notes`` in their place, prepend front matter."""
    lines = text.split("\n")
    first_removed = min(removed) if removed else -1
    collapsed: list[str] = []
    after_removal = False  # a removal just happened: swallow blank lines it would double up
    for idx, line in enumerate(lines):
        if idx == first_removed:
            collapsed.extend(notes)
            if notes:
                after_removal = False
        if idx in removed:
            after_removal = True
            continue
        if after_removal and not line.strip() and collapsed and not collapsed[-1].strip():
            continue
        if line.strip():
            after_removal = False
        collapsed.append(line)
    return backlog.format_front_matter(meta) + "\n" + "\n".join(collapsed)


def _slug(title: str, limit: int = 50) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > limit:
        slug = slug[:limit].rsplit("-", 1)[0] or slug[:limit]
    return slug


def migrate_story_file(
    root: Path,
    path: Path,
    index: dict[str, IndexEntry],
    known_ids: set[str],
    report: Report,
    write: bool,
) -> None:
    rel = path.relative_to(root).as_posix()
    story_id = backlog._FILENAME_ID_RE.match(path.name).group(1)  # type: ignore[union-attr]
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        report.skipped_existing.append(rel)
        return
    lines = text.split("\n")
    h1 = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), None)
    if h1 is None:
        raise MigrationError(f"{rel}: no H1 heading")
    end = next((i for i in range(h1 + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    region = lines[h1 + 1 : end]
    header, removed_rel, _ = parse_header_lines(region)
    removed = {h1 + 1 + i for i in removed_rel}
    meta, notes = _build_meta(
        story_id,
        header,
        index.get(story_id),
        rel,
        report,
        known_ids,
        in_done_dir=path.parent.name == "DONE",
    )
    if path.parent.name == "DONE" and meta["status"] != "done":
        report.anomalies.append(f"{rel}: lives in docs/DONE/ but status={meta['status']}")
    report.migrated.append(rel)
    if write:
        path.write_text(rewrite_story(text, meta, notes, removed), encoding="utf-8")


def create_index_only(
    root: Path, entry: IndexEntry, known_ids: set[str], report: Report, write: bool
) -> None:
    meta, notes = _build_meta(entry.id, Header(), entry, f"index {entry.id}", report, known_ids)
    folder = "docs/DONE" if meta["status"] == "done" else "docs/BACKLOG_STORIES"
    rel = f"{folder}/{entry.id}-{_slug(entry.title)}.md"
    body = list(entry.body)
    while body and (not body[0].strip()):
        body.pop(0)
    while body and (not body[-1].strip() or body[-1].strip() == "---"):
        body.pop()
    parts = [f"# {entry.id}: {entry.title}", ""]
    if notes:
        parts += notes + [""]
    parts += body
    content = backlog.format_front_matter(meta) + "\n" + "\n".join(parts) + "\n"
    report.created_from_index.append(f"{rel} (status={meta['status']})")
    if write:
        (root / rel).write_text(content, encoding="utf-8")


def run(root: Path, backlog_md: Path, write: bool) -> Report:
    report = Report()
    index, duplicates = parse_index(backlog_md.read_text(encoding="utf-8"))
    report.duplicates = [f"{d}: duplicate index heading ignored" for d in duplicates]
    files = backlog.story_files(root)
    file_ids = {backlog._FILENAME_ID_RE.match(p.name).group(1) for p in files}  # type: ignore[union-attr]
    index_only = sorted(set(index) - file_ids)
    known_ids = file_ids | set(index_only)
    for path in files:
        migrate_story_file(root, path, index, known_ids, report, write)
    for story_id in index_only:
        create_index_only(root, index[story_id], known_ids, report, write)
    return report


def render_priority_moves(report: Report) -> str:
    """Markdown table of open stories whose final priority differs from their index section."""
    lines = [
        "# Open stories whose priority moved in the BITB-313 migration",
        "",
        "| Story | Index section | Final priority | Winning value from |",
        "|---|---|---|---|",
    ]
    for story_id, section, prio, source in sorted(report.priority_moves):
        lines.append(f"| {story_id} | {section} | {prio} | {source} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    parser.add_argument("--root", type=Path, default=_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--backlog", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--priority-moves-md", type=Path, help="write the priority-moves table to this file"
    )
    args = parser.parse_args(argv)
    backlog_md = args.backlog or (args.root / "docs" / "BACKLOG.md")
    try:
        report = run(args.root, backlog_md, write=not args.dry_run)
    except MigrationError as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(report.render())
    if args.priority_moves_md:
        args.priority_moves_md.write_text(render_priority_moves(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
