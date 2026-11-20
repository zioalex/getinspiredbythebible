---
id: BITB-352
status: todo
priority: P3
size: S
created: 2026-11-20
---

# BITB-352: `page.test.tsx` Tests Depend on Execution Order — `--sequence.shuffle` Fails 1–4 Tests

**Prompted by:** BITB-340 build (follow-up).

## Problem

Running `cd frontend && npx vitest run 'src/app/[locale]/page.test.tsx' --sequence.shuffle`
fails 1 to 4 tests per run, even on unmodified `main` (checked during the BITB-340 build with
that story's changes stashed). In file order, all tests pass. So some tests rely on state left
behind by earlier tests: mock implementations set with `mockImplementation` (not `Once`) that
outlive their test, `localStorage`/`sessionStorage` contents, or module-level state in the
mocked `@/lib/api`.

This has two costs. A latent order dependence can surface as an unrelated red CI run when a
test is added or moved. It also makes the shuffle technique unusable for finding teardown races
like BITB-340.

## Acceptance criteria

- [ ] Identify the tests that fail under `--sequence.shuffle` and the shared state each depends on
- [ ] Each `describe`'s `beforeEach` fully resets the mocks it relies on (e.g. `vi.resetAllMocks()` plus re-applying the defaults) and clears web storage
- [ ] 10 consecutive `--sequence.shuffle` runs of `page.test.tsx` pass
- [ ] No test is skipped or quarantined to get there

## Related

BITB-340 (teardown race in the same file).
