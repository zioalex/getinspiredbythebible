#!/usr/bin/env python3
"""Guard against BITB-NNN story-ID collisions and missing backlog entries (BITB-111).

`AGENTS.md` (*Backlog Hygiene*) requires every `BITB-NNN` to be sequential and unique, and
every story file in ``docs/BACKLOG_STORIES/`` to have a matching summary entry in
``docs/BACKLOG.md``. Neither rule was being enforced, and it silently drifted: sixteen IDs
each ended up naming two to four unrelated stories (see
``docs/BACKLOG_STORIES/BITB-111-backlog-story-id-collisions.md`` for the cleanup that fixed
the existing drift). This script is the durable guard so the next collision fails CI instead
of shipping.

It checks two things over ``docs/BACKLOG_STORIES/*.md`` and ``docs/DONE/*.md``:

1. **Uniqueness** — each `BITB-NNN` extracted from a filename maps to exactly one file,
   except the deliberate companion-doc pairs listed in ``_ALLOWED_SHARED_ID_GROUPS`` below
   (e.g. an analysis doc + a resolution doc for the same story, both filed under one ID).
2. **Cross-reference** — every ``docs/BACKLOG_STORIES/*.md`` file has a real entry in
   ``docs/BACKLOG.md``: a markdown heading containing its `BITB-NNN` id, or a
   ``**Full Story:**`` link naming its filename (see ``_has_backlog_entry``). A bare
   mention of the id in another story's prose does not count. Files already moved to
   ``docs/DONE/`` are not required to pass this check here since some pre-date
   `docs/BACKLOG.md` coverage entirely (tracked separately); the live backlog is what this
   guard protects.

Files whose name does not start with ``BITB-<digits>-`` are ignored (this repo's docs
directories also hold dated session logs, PR write-ups, and other non-story docs that were
never meant to carry a unique story ID).

Usage:

    python3 scripts/check_backlog_story_ids.py

Exits 0 and prints a summary when the repo is clean. Exits 1 and prints one clearly labeled
error block per problem (every offending file named) when it is not. No flags: unlike
``generate_localized_book_map.py`` there is nothing to generate here, so failing on a
problem is simply the default (and only) behavior — suitable to run as-is in CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_STORY_DIR = _REPO_ROOT / "docs" / "BACKLOG_STORIES"
_DONE_DIR = _REPO_ROOT / "docs" / "DONE"
_BACKLOG_MD = _REPO_ROOT / "docs" / "BACKLOG.md"

_ID_FROM_FILENAME = re.compile(r"^(BITB-\d+)-")

# Deliberate exceptions: groups of files (repo-relative paths) that are allowed to share one
# BITB-NNN ID because they are companion documents for a single story, not a collision.
# Add a new entry here only with a comment explaining why the files are one story, not two —
# the default for a shared ID is still "fail".
_ALLOWED_SHARED_ID_GROUPS: tuple[frozenset[str], ...] = (
    # BITB-147: the CI/Ollama-timeout investigation was written up as a paired
    # analysis + resolution doc when it was archived to docs/DONE/, both deliberately
    # kept under the same ID as companion halves of one write-up (not a second story).
    frozenset(
        {
            "docs/DONE/BITB-147-ANALYSIS-CI-OLLAMA-TIMEOUT.md",
            "docs/DONE/BITB-147-RESOLUTION-CI-OLLAMA-TIMEOUT.md",
        }
    ),
)

# Pre-existing debt: docs/BACKLOG_STORIES/*.md files with no docs/BACKLOG.md entry, found by
# this guard's first run (BITB-111) but out of scope for the PR that added it. BITB-111 fixed
# the 16 known ID collisions and added BITB-059's entry (its own narrative had flagged that
# one specifically); a repo-wide sweep to backfill every other undocumented story file is
# unbounded and belongs in its own follow-up rather than silently expanding this PR. New
# stories must still get a BACKLOG.md entry -- CI fails on anything not already listed here.
# Remove an entry once its summary is added; never add a *new* story to this set going
# forward (that would defeat the guard).
_MISSING_BACKLOG_ENTRY_EXEMPT: frozenset[str] = frozenset(
    {
        # Pre-existing gaps unrelated to the BITB-111 renumbering (never had an entry).
        "docs/BACKLOG_STORIES/BITB-014-fix-migration-pipeline-dependency.md",
        "docs/BACKLOG_STORIES/BITB-015-consolidate-agent-configuration.md",
        "docs/BACKLOG_STORIES/BITB-019-resolve-pr208-conflicts.md",
        "docs/BACKLOG_STORIES/BITB-033-android-rename-post-send-cancel-button.md",
        "docs/BACKLOG_STORIES/BITB-034-android-compose-ui-test-tier.md",
        "docs/BACKLOG_STORIES/BITB-035-chat-interrupt-and-multiline-input.md",
        "docs/BACKLOG_STORIES/BITB-056-backend-error-alert-actionability.md",
        "docs/BACKLOG_STORIES/BITB-060-async-email-stop-blocking-event-loop.md",
        # BITB-037's *keeper* claimant (Verse Citation Panel Reliability) never had its own
        # BACKLOG.md entry either -- the only "037" entries were the other two stories that
        # used to collide on this number and are now BITB-135/BITB-136.
        "docs/BACKLOG_STORIES/BITB-037-verse-citation-panel-reliability.md",
        # The following 10 are BITB-111 renumbered files (see that story's Renumbering Log):
        # under their *old*, colliding number none of them had a BACKLOG.md entry either, so
        # there was nothing for Part 2 of that cleanup to repoint -- adding a brand-new entry
        # for each was explicitly out of scope for a renumbering pass. Same pre-existing gap,
        # just carried forward under the new number.
        "docs/BACKLOG_STORIES/BITB-130-skip-terraform-apply-when-no-changes.md",
        "docs/BACKLOG_STORIES/BITB-131-fix-contact-turnstile-token.md",
        "docs/BACKLOG_STORIES/BITB-133-translate-legal-pages.md",
        "docs/BACKLOG_STORIES/BITB-134-pipeline-path-filters.md",
        "docs/BACKLOG_STORIES/BITB-135-android-amber-quote-test-coverage.md",
        "docs/BACKLOG_STORIES/BITB-137-product-analytics-dashboard.md",
        "docs/BACKLOG_STORIES/BITB-141-modern-open-bible-translations-research.md",
        "docs/BACKLOG_STORIES/BITB-143-upstream-dependency-resilience.md",
        "docs/BACKLOG_STORIES/BITB-144-per-language-model-fallback-chain.md",
        "docs/BACKLOG_STORIES/BITB-146-menge-bibel-german-default.md",
        # Newly surfaced by tightening `_has_backlog_entry` to require a real heading or
        # **Full Story:** link (BITB-111 fix round): the old bare `\bBITB-NNN\b` substring
        # search had been falsely passing these because their ID is *mentioned in prose*
        # inside a different story's write-up (e.g. "BITB-016 chose it knowingly" inside
        # BITB-099's entry) -- not because they have an entry of their own. Same
        # pre-existing-debt category as the rest of this set, just previously masked by the
        # weaker check.
        "docs/BACKLOG_STORIES/BITB-016-fix-migration-ssl-connection.md",
        "docs/BACKLOG_STORIES/BITB-017-multilanguage-harm-detection.md",
        "docs/BACKLOG_STORIES/BITB-031-android-settings-changelog.md",
        "docs/BACKLOG_STORIES/BITB-032-route-support-emails-to-dedicated-inbox.md",
    }
)


def _relpath(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _collect_story_files(*directories: Path) -> dict[str, list[Path]]:
    """Map each BITB-NNN id to every matching file across the given directories."""
    by_id: dict[str, list[Path]] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            match = _ID_FROM_FILENAME.match(path.name)
            if not match:
                continue
            by_id.setdefault(match.group(1), []).append(path)
    return by_id


def _check_unique_ids(by_id: dict[str, list[Path]]) -> list[str]:
    errors = []
    for story_id, paths in sorted(by_id.items()):
        if len(paths) <= 1:
            continue
        rel_paths = frozenset(_relpath(p) for p in paths)

        # A fully-present allowlisted companion-doc group counts as a single claimant on
        # this id, not one claimant per file in the group -- remove it before judging
        # whether the id still has more than one real claimant. A *partially* present
        # group (one companion renamed/deleted without the other) is deliberately left in
        # `remaining` so it still fails: that is no longer the documented pair.
        #
        # Bug fixed here (found in adversarial review): removing a matched group's files
        # from `remaining` must NOT make the group disappear from the claimant count. The
        # group is still one claimant on this id -- so the total claimant count is
        # `len(remaining after subtracting matched groups) + number of groups matched`,
        # not just `len(remaining)`. Without the `+ matched_group_count` term, an
        # allowlisted pair plus exactly one unrelated rogue file sharing the same id would
        # subtract the pair down to just the rogue file (len 1) and wrongly pass, when it
        # is actually two distinct claimants (the pair, and the rogue file) and must fail.
        remaining = set(rel_paths)
        matched_group_count = 0
        for group in _ALLOWED_SHARED_ID_GROUPS:
            if group <= remaining:
                remaining -= group
                matched_group_count += 1

        if len(remaining) + matched_group_count <= 1:
            continue

        file_list = "\n".join(f"    - {p}" for p in sorted(rel_paths))
        errors.append(
            f"{story_id} maps to {len(paths)} files (must map to exactly one, unless it is "
            f"a documented companion-doc pair in _ALLOWED_SHARED_ID_GROUPS):\n{file_list}"
        )
    return errors


def _has_backlog_entry(backlog_text: str, story_id: str, filename: str) -> bool:
    """Whether ``backlog_text`` documents ``story_id`` with a real entry for ``filename``.

    A bare ``\\bBITB-NNN\\b`` substring search is too weak: it matches incidental prose
    mentions of an ID (e.g. "renumbered to `BITB-132-...md`" inside a *different* story's
    write-up) with no real entry behind them, and it can't tell two same-numbered things
    apart (a pre-existing legacy ``### ... BITB-024: ...`` heading in the Done section
    happens to share a bare number with an unrelated current BITB-024 story file). Instead
    require one of the two concrete forms this repo's real entries actually use:

    1. A markdown heading (``##``-``####``) containing the exact ``BITB-NNN`` token — this
       is how every live `docs/BACKLOG.md` section is titled, e.g.
       ``### 🚧 BITB-140: Audit & Close Bible Reference-Normalization Gaps``.
    2. A ``**Full Story:**`` link whose backtick-quoted path names this exact file, e.g.
       ``**Full Story:** \\`docs/BACKLOG_STORIES/BITB-064-browser-preflight-smoke-and-alerting.md\\```.
    """
    heading_re = re.compile(rf"^#{{2,4}}.*\b{re.escape(story_id)}\b", re.MULTILINE)
    if heading_re.search(backlog_text):
        return True
    full_story_re = re.compile(rf"\*\*Full Story:\*\*\s*`[^`]*{re.escape(filename)}`")
    return full_story_re.search(backlog_text) is not None


def _check_backlog_entries(by_id: dict[str, list[Path]]) -> list[str]:
    if not _BACKLOG_MD.is_file():
        return [f"{_relpath(_BACKLOG_MD)} does not exist — cannot verify story cross-references."]
    backlog_text = _BACKLOG_MD.read_text(encoding="utf-8")
    errors = []
    for path in sorted(_STORY_DIR.glob("*.md")):
        match = _ID_FROM_FILENAME.match(path.name)
        if not match:
            continue
        story_id = match.group(1)
        rel = _relpath(path)
        if rel in _MISSING_BACKLOG_ENTRY_EXEMPT:
            continue
        if not _has_backlog_entry(backlog_text, story_id, path.name):
            errors.append(
                f"{rel} ({story_id}) has no entry in {_relpath(_BACKLOG_MD)} — add a summary "
                "under the correct priority section (see AGENTS.md -> Backlog Hygiene). A bare "
                "mention of the ID in prose elsewhere does not count -- a real heading or "
                "**Full Story:** link is required."
            )
    return errors


def main() -> int:
    by_id = _collect_story_files(_STORY_DIR, _DONE_DIR)

    duplicate_errors = _check_unique_ids(by_id)
    missing_entry_errors = _check_backlog_entries(by_id)

    if not duplicate_errors and not missing_entry_errors:
        print(
            f"OK: {len(by_id)} distinct BITB-NNN ids across "
            f"{_relpath(_STORY_DIR)}/ and {_relpath(_DONE_DIR)}/ — each maps to one file "
            "(or a documented companion-doc pair) and every backlog story has a "
            f"{_relpath(_BACKLOG_MD)} entry."
        )
        return 0

    if duplicate_errors:
        print(
            f"FAIL: {len(duplicate_errors)} BITB-NNN id(s) map to more than one file:\n",
            file=sys.stderr,
        )
        for error in duplicate_errors:
            print(f"  * {error}\n", file=sys.stderr)

    if missing_entry_errors:
        print(
            f"FAIL: {len(missing_entry_errors)} story file(s) have no docs/BACKLOG.md entry:\n",
            file=sys.stderr,
        )
        for error in missing_entry_errors:
            print(f"  * {error}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
