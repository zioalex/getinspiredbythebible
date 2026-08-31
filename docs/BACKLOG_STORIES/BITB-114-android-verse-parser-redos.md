# BITB-114: Close the Same ReDoS Gap on Android (`ChatMessageItem.kt` / `VersesPanel.kt`)

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-08-31
**Found by:** independent Verify pass on BITB-108 (the web-side fix for the same issue)

## The Finding

BITB-108 fixed a ReDoS-shaped gap in `frontend/src/lib/versePatterns.ts`'s multi-word book-name
"connector" branch: an unbounded repeat group let adversarial input (long chains of connector
words like "of") drive the regex engine into superlinear-time backtracking — benchmarked at ~22s on
a ~300KB adversarial string, run client-side on chat message text (model output / pasted text).

The identical construct exists, unfixed, in two Android files, both matched against the same kind
of untrusted text (chat message content rendered in the app), on Java's backtracking regex engine
(also vulnerable to this shape):

- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt:113`
  (`BOOK_NAME`): `(?:\s+(?:of|de|des|der|da|del|dei|dos|van|af|के|ال)\s+[\p{L}][\p{L}\p{M}\d]*)*`
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt:54`
  (`CITED_BOOK_NAME`): `(?:\s+(?:of|de|des|der|da|del|dei|dos|van|af)\s+[\p{Lu}\p{Lo}][\p{L}\d]*)*`

Audit item E13 (referenced by BITB-108) already named the Android re-implementation ("see A1") as
in scope; BITB-108 closed only the web side to keep that PR reviewable in one day. This story is the
Android follow-up, deliberately left out of BITB-108 rather than silently left undone.

## Proposed Fix

Same shape as the web fix: bound the connector-repeat group (currently unbounded `*`/`+`) to a small
fixed range (e.g. `{0,3}` for `BOOK_NAME`, `{0,3}` for `CITED_BOOK_NAME` — check the actual max
connector count needed against real book names before picking the exact bound; BITB-108 found `{1,3}`
sufficient on the web side's equivalent data). Benchmark before/after with a JVM microbenchmark or
plain JUnit test timing an adversarial input, the same way BITB-108's `versePatterns.redos.test.ts`
does for TypeScript.

## Acceptance Criteria

- [ ] Both `ChatMessageItem.kt::BOOK_NAME` and `VersesPanel.kt::CITED_BOOK_NAME` connector groups
      bounded (not unbounded `*`/`+`)
- [ ] Adversarial-input benchmark recorded before and after, same rigor as BITB-108 (real numbers,
      not "it felt fast")
- [ ] Regression test (JUnit/instrumented, matching the project's existing Android test conventions)
      proving the bound doesn't break real multi-word book names in any connector language, and a
      second test proving the connector-repeat cap is actually enforced (not just documented) —
      mirroring `versePatterns.redos.test.ts`'s two-part structure
- [ ] `docs/BACKLOG.md`'s BITB-108 entry updated to say the finding is now closed on both platforms

## Related

- **BITB-108** — closed the same finding on web (`frontend/src/lib/versePatterns.ts`); this is its
  Android counterpart, deliberately split out rather than bundled
- **BITB-113** — separate, unrelated follow-up (grammar unification/DRY, not safety)
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt`
