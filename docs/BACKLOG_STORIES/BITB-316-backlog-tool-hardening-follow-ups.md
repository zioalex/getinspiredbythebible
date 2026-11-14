---
id: BITB-316
status: todo
priority: P3
size: S
created: 2026-11-14
---

# BITB-316: Backlog Tool Hardening — List Headroom, Clearer `check` Errors, Retire the Cutover Exemption

**Prompted by:** the second independent verification of BITB-313 (PR #1292, 2026-11-14), which
passed with these nits left open. Filed in the same PR per *Backlog Hygiene* (follow-ups at PR
creation).

## Problem

Checked against `scripts/backlog.py`, `scripts/test_backlog.py` and
`.github/workflows/backlog.yml` at PR #1292's head.

1. **The default `list` is about to pass its 12 KB agent budget.** The default (open stories)
   listing is 11,981 B for 166 stories. With the 4 todo stories from open PRs it is 12,271 B.
   The next new story pushes it over. The NFR allows growing past ~165 lines, but small/local
   models (32k context) are the reason the budget exists. Tests pin only the per-line cap
   (73 B) and a synthetic 165-story fixture, so nothing will fail. The budget just silently
   stops holding.
2. **`check` messages are unclear in three cases:**
   - A CRLF-encoded story is reported as "no front matter" instead of naming the line endings.
   - A second level-1 heading in a story is not flagged, although the title is defined as the single
     H1.
   - A bad `prs` value stops validation of that file, so its other field errors only appear
     after a fix-and-rerun cycle.
3. **`changelog --since` accepts invalid dates** (`2026-99-99`, `yesterday`), prints nothing
   and exits 0.
4. **The cutover exemption is dead code after the merge.** The `backlog-stub-guard` job
   exempts PR number 1292, which is inert once #1292 merges but stays in the workflow and
   the stub.

## Requirements

1. Keep the default view under 12 KB as the backlog grows. Pick one:
   - default `list` to P0–P2 open stories with a one-line footer
     (`… N more: --priority P3,icebox`); or
   - a default `--limit` with the same footer.

   Assert the budget on the real tree again, now that the default is bounded.
2. `check`:
   - name CRLF line endings explicitly;
   - flag a second H1;
   - report all field errors of a file in one run.
3. `changelog --since`: validate an ISO date; exit 2 with a message on a bad value.
4. Remove the PR-number exemption from `backlog.yml`, the stub text and the BITB-313
   story's deviations note; keep the `backlog-stub-edit` label exemption.
5. Tests for each item in `scripts/test_backlog.py`.

## Acceptance criteria

- [ ] Default `make backlog` output ≤ 12 KB on the real tree, asserted in a test, with a
      footer saying how to see the rest
- [ ] `check` names CRLF, flags a second H1, and reports every field error of a file in one
      run
- [ ] `changelog --since` rejects invalid dates with exit 2
- [ ] PR-number exemption removed; label exemption still tested
- [ ] `make backlog-check` and the backlog workflow green

## Out of scope

- Changing the front-matter schema.
- The open-PR cutover itself, which is done as part of BITB-313.
