---
id: BITB-356
status: todo
priority: P3
size: XS
created: 2026-11-21
depends_on: [BITB-322]
---

# BITB-356: Reconcile the Make-Target Audit Once PR #1302 and PR #1325 Have Both Merged

**Prompted by:** BITB-322 follow-ups (PR #1325). Two open PRs rewrite the same generated audit.

## Problem

PR #1325 (BITB-322) adds the `safety-golden-set` make target: a classification entry in
`scripts/make_target_audit.json`, two sandbox tests in `scripts/test_make_targets.py`, and a
regenerated `docs/MAKE_TARGET_AUDIT.md`. Open PR #1302 (BITB-325) independently rewrites
`scripts/audit_make_targets.py` (the doc-reference regex and the report self-scan exclusion) and
regenerates the same report from that scanner state.

Whichever merges second lands on a textual conflict in those three files, and neither PR's version
of the generated report is valid for the merged state — it must be regenerated. On top of that,
`test_make_targets.py` is red on `main` today (stale report plus doc-reference findings), which is
PR #1302's job to fix; after both PRs merge, the suite must be fully green, including
`InventoryTests.test_report_is_current` and `test_docs_reference_only_existing_targets`.

## Acceptance criteria

- [ ] After both #1302 (BITB-325) and #1325 merge: re-run `python3 scripts/audit_make_targets.py
      --write` on fresh `main` and commit `docs/MAKE_TARGET_AUDIT.md` from that state.
- [ ] `make test-makefile` fully green on `main` (unittest `scripts.test_make_targets` +
      `scripts.test_az_logs`, plus `audit_make_targets.py --check`).
- [ ] No doc-reference findings remain: the scan (with #1302's regex fix for templated target names
      and its report self-scan exclusion) reports nothing on the merged state.

## Related

BITB-322, BITB-325 (PR #1302), BITB-220.
