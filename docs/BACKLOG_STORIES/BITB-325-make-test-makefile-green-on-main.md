---
id: BITB-325
status: in-review
priority: P2
kind: chore
size: XS
created: 2026-11-16
prs: [1302]
---

# BITB-325: `make test-makefile` Is Red on `main` (Stale Doc References, Self-Scanning Report, Hook Drift)

## Bug report

On `main`, `python3 scripts/audit_make_targets.py --check` reported 16 FAILs and
`python3 -m unittest scripts.test_make_targets` had 3 failures:
`test_docs_reference_only_existing_targets`, `test_report_is_current` and
`test_frontend_and_hook_targets`. The BITB-220 Makefile audit gate was therefore red for
every PR that ran it.

## Root causes

1. **Dead doc references.** `docs/BITB-150-postgres-cost-analysis.md` named
   `make golden-set-eval`, which never existed. The retrieval recall harness it means is
   `python scripts/run_search_eval.py --run` (BITB-139, `docs/SEARCH_EVAL_HOWTO.md`).
   `make check-llm-budget` appears only in the frozen `docs/backlog/CHANGELOG-archive.md`.
   It is a planned BITB-287 target, and that story file is already excluded from the scan.
2. **The report scanned itself.** `docs/MAKE_TARGET_AUDIT.md` lists every bad reference as
   `` `make <name>` ``. The doc scan read the report too, so every `--write` turned those
   quotes into new findings. This is why 2 real references became 14 findings.
3. **`test_report_is_current` hardcoded `refs=[]`.** The report on disk carried the reference
   list, so the test could never match it while any reference was broken. The test now builds
   the report the same way `--write` does.
4. **Hook drift.** BITB-243 added `pre-commit install --hook-type pre-push` to
   `make install-hooks`, but the test still expected two installs.
5. **Templated names (found while fixing).** BITB-319 (#1298) added
   `make az-logs-${app#bible-app-}-query` hints to `scripts/az-logs.sh`. The regex stopped at
   `${` and reported the target `az-logs` as missing.

## Fix

- BITB-150 doc points at the real eval command. No new Make target.
- `doc_references()` always skips the generated report. `doc_scan_skip` adds
  `docs/backlog/CHANGELOG-archive.md`, which is frozen history.
- `DOC_REF_RE` ignores templated or wildcard names (`-${…}`, `-*`, `<name>`, `{…}`).
- The install-hooks expectation now includes the pre-push hook.
- The report is regenerated. Defect D14 in `scripts/make_target_audit.json` records this.

## Acceptance criteria

- [x] `make test-makefile` exits 0 (95 tests, `audit_make_targets.py --check` OK)
- [x] Regression tests: report and archive excluded from the scan, templated names ignored,
      pre-push hook installed
- [x] `docs/MAKE_TARGET_AUDIT.md` regenerated with `--write`

## Out of scope

- Implementing `make check-llm-budget`. It stays with BITB-287.
