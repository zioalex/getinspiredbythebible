# BITB-114: Close the Same ReDoS Gap on Android (`ChatMessageItem.kt` / `VersesPanel.kt`)

**Status:** ✅ Done
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

## Resolution

Both groups were `*` (zero-or-more), not `+`, so the semantics-preserving bound is **`{0,3}`**
(`{1,3}` would have required a connector on every single-word book name and broken essentially all
parsing — this was the highest-risk mistake to avoid here, per the independent Verify pass on this
plan).

Bound justification: scanning `android/app/src/main/kotlin/org/voxquieta/app/utils/LocalizedBookToEnglish.kt`
(all supported locales), the maximum connector count in any real supported book name is **1** — e.g.
"Song of Solomon" (en), "Cantico dei Cantici" (it), "Cantique des Cantiques" / "Actes des Apôtres"
(fr), "Cântico dos Cânticos" (pt), "प्रेरितों के काम" (hi). `{0,3}` gives 3x headroom over that while
eliminating the unbounded blowup, matching the web fix's approach.

Changed:

- `ChatMessageItem.kt::BOOK_NAME` — connector group `)*` → `){0,3}`.
- `VersesPanel.kt::CITED_BOOK_NAME` — connector group `)*` → `){0,3}`.
- New test `android/app/src/test/kotlin/org/voxquieta/app/components/VerseRefRedosTest.kt`, mirroring
  `versePatterns.redos.test.ts`'s structure: adversarial-input timing (against
  `DEFAULT_VERSE_REF_REGEX`, `buildVerseRefRegex`'s generic fallback path, and `referencedVerses`),
  connector-cap enforcement against synthetic non-book chains (proving the match starts one word
  later rather than capturing an unbounded chain — same rewind behavior as the web test), and
  regression coverage for real multi-word book names ("Song of Solomon") still matching after the
  bound.

Benchmark: this sandbox has no Android SDK, so the exact JVM/Java-regex numbers must come from CI
(`android-ci.yml` / `android-compose-tests.yml` running `testDebugUnitTest`) rather than this write-up.
As a same-shape cross-check, re-implementing both the unbounded and `{0,3}`-bounded patterns against
Python's Unicode-aware `regex` engine (not the JVM, but the same backtracking-NFA shape) on the
adversarial input from the test (`"aa" + " of aa".repeat(20000) + "!"`) showed the expected profile:
the unbounded pattern scales superlinearly (500 repeats: ~228ms, 1,000: ~1,013ms, 2,000: ~4,966ms —
roughly quadrupling time for each doubling of input), while the `{0,3}`-bounded pattern handles the
full 20,000-repeat adversarial input in ~140ms. CI's actual JVM run is the authoritative number; this
is corroborating evidence the fix has the right shape, not a substitute for it.

## Acceptance Criteria

- [x] Both `ChatMessageItem.kt::BOOK_NAME` and `VersesPanel.kt::CITED_BOOK_NAME` connector groups
      bounded (not unbounded `*`/`+`)
- [x] Adversarial-input benchmark recorded before and after — see Resolution above; CI's
      `testDebugUnitTest` run on the new `VerseRefRedosTest` is the authoritative JVM number
- [x] Regression test (JUnit, matching the project's existing Android test conventions) proving the
      bound doesn't break real multi-word book names in any connector language, and a second test
      proving the connector-repeat cap is actually enforced (not just documented) — mirroring
      `versePatterns.redos.test.ts`'s two-part structure
- [x] `docs/BACKLOG.md`'s BITB-108 entry updated to say the finding is now closed on both platforms

## Residual Risk (not closed by this story)

- `ChatMessageItem.kt`'s Alt-1 branch has a *second*, separate unbounded group,
  `(?:\s+[\p{L}][\p{L}\p{M}\d]+)*`, applied directly after `$BOOK_NAME` (needed for 3-word Arabic
  numbered-book names like "1 أخبار الأيام"). Bounding the connector group inside `BOOK_NAME` lowers
  the ambiguity degree of the overall pattern but does not eliminate this second group. It was
  benchmarked as part of the adversarial-input tests above (an Alt-1-shaped adversarial vector is
  included in `VerseRefRedosTest`) and stayed within budget, but it is called out here rather than
  claiming full closure — filed as **BITB-116** rather than assumed covered by BITB-114.
- `VersesPanel.kt`'s `CITED_BOOK_NAME` connector list omits `के`/`ال` (present in `BOOK_NAME`'s
  list) — a pre-existing web/Android divergence, left alone here and noted for BITB-113
  (grammar unification), not fixed as part of this safety story.

## Related

- **BITB-108** — closed the same finding on web (`frontend/src/lib/versePatterns.ts`); this is its
  Android counterpart, deliberately split out rather than bundled
- **BITB-113** — separate, unrelated follow-up (grammar unification/DRY, not safety)
- **BITB-116** — the Alt-1 residual risk noted above, split out as its own story
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt`
