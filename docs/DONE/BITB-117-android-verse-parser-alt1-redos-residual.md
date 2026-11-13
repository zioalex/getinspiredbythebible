# BITB-117: Bound the Remaining Unbounded Android Alt-1 Numbered-Prefix Groups

**Status:** ✅ Done
**Priority:** P3 — no active incident, but the same ReDoS *shape* BITB-108/BITB-114 closed elsewhere
**Size:** S
**Created:** 2026-09-02
**Found by:** BITB-114 (Android connector-group ReDoS fix), flagged as residual rather than folded in

## The Finding

BITB-114 bounded the connector-repeat group inside `BOOK_NAME` (`ChatMessageItem.kt`) and
`CITED_BOOK_NAME` (`VersesPanel.kt`) to `{0,3}`, closing the ReDoS shape audit item E13 identified
(mirroring the web fix in BITB-108).

Separate unbounded groups survive in both Android Alt-1 (numbered-prefix) branches:

- `ChatMessageItem.kt`'s `DEFAULT_VERSE_REF_REGEX` and `buildVerseRefRegex()`, immediately after
  `$BOOK_NAME`: `(?:\s+[\p{L}][\p{L}\p{M}\d]+)*`
- `VersesPanel.kt`'s `CITED_VERSE_REF_REGEX`, immediately after `$CITED_BOOK_NAME`:
  `(?:\s+[\p{Lu}\p{Lo}][\p{L}\d]+)*`

These support numbered multi-word names, including 3-word Arabic names (e.g. "1 أخبار الأيام" =
"1 Chronicles"). Both now have dedicated numbered-prefix timing guards with a 500ms budget in
BITB-114's tests. This environment has no JDK, so the authoritative JVM result must come from CI;
the tests do not establish a before/after scaling curve. Neither group is bounded or benchmarked
across input sizes in isolation the way the connector groups were, and their worst-case behavior at
larger adversarial inputs remains unverified.

## Proposed Fix

Bound both groups the same way: a small fixed range (start from `{0,2}`, since Arabic numbered names
need at most 2 extra words after the connector-bearing `BOOK_NAME` — verify the actual max against
`LocalizedBookToEnglish.kt` / the Arabic book-name data before picking the exact bound, the same way
BITB-114 verified its bound against real data rather than guessing). Add a dedicated adversarial
benchmark isolating this group specifically (not just incidentally covered by BITB-114's tests), plus
a cap-enforcement test proving the bound is real, mirroring BITB-108/BITB-114's two-part test
structure.

## Acceptance Criteria

- [x] Both Alt-1 trailing groups bounded (not unbounded `*`)
- [x] Bound justified against real Arabic (and any other) numbered multi-word book names, not guessed
- [x] Dedicated adversarial-input benchmark for this specific group, before and after
- [x] Regression test proving real numbered multi-word names (e.g. "1 أخبار الأيام") still match
- [x] Cap-enforcement test proving the bound is actually enforced, not just documented
- [x] `docs/BACKLOG_STORIES/BITB-114-android-verse-parser-redos.md`'s "Residual Risk" section updated
      to point at this story as closing the gap it flagged

## Related

- **BITB-114** — closed the connector-group ReDoS shape on Android; flagged this as residual
- **BITB-108** — the original web-side finding and fix this whole chain follows
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt`

## Completion Note (2026-09-07)

Bounded both Alt-1 numbered-prefix trailing-word groups to `{0,3}`, mirroring BITB-114's own bound
and headroom philosophy exactly:

- **`ChatMessageItem.kt`:** `(?:\s+[\p{L}][\p{L}\p{M}\d]+)*` → `{0,3}` in both
  `DEFAULT_VERSE_REF_REGEX` and `buildVerseRefRegex()`.
- **`VersesPanel.kt`:** `(?:\s+[\p{Lu}\p{Lo}][\p{L}\d]+)*` → `{0,3}` in `CITED_VERSE_REF_REGEX`.
- **Bound justification:** grepped every numbered-prefix entry (`"1 ...`, `"2 ...`, `"3 ...`,
  `"1. ...`, `"1-я ...`, etc.) in `LocalizedBookToEnglish.kt` across all locales. The real maximum
  is exactly 1 trailing word — e.g. Arabic `"1 أخبار الأيام"` ("1 Chronicles"): `أخبار` is the
  first word (matched by `BOOK_NAME`/`CITED_BOOK_NAME`), `الأيام` is the one trailing word this
  group must still match. No numbered book name in any locale needs more than that. `{0,3}` was
  chosen over the story's initial `{0,2}` guess to match BITB-114's own bound exactly (same real
  max of 1, same 3x-headroom philosophy), keeping the codebase's two ReDoS fixes consistent.
- **Tests** (`android/app/src/test/kotlin/org/voxquieta/app/components/VerseRefRedosTest.kt`):
  the two existing placeholder timing guards (`ChatMessageItem`/`VersesPanel` "numbered-prefix
  branch handles adversarial trailing words within budget") were bumped from `.repeat(500)` to
  `.repeat(20000)` to match the scale of the connector-group adversarial tests, and their comments
  updated to say the group is now bounded rather than deferred. Four new cap-enforcement tests
  prove the `{0,3}` bound is actually enforced (not just documented) for both
  `DEFAULT_VERSE_REF_REGEX` and `CITED_BOOK_NAME`/`referencedVerses` — a 4-trailing-word input
  fails to match as a single Alt-1 phrase and falls through to Alt 2's shorter match, while a
  3-trailing-word input still matches fully. Two new regression tests
  (`referencedVerses`/`injectVerseLinks`) prove the real 3-word Arabic name `"1 أخبار الأيام"`
  still matches end-to-end after the bound.
- **Sandbox limitation:** no Android SDK is available in this sandbox (`ANDROID_HOME` unset, no
  `local.properties`), so Gradle/`testDebugUnitTest` could not be run. A JDK 21 *is* present,
  though, and an independent verify pass used it directly: it re-implemented every changed regex
  from the literal committed source and executed all 6 new assertions against real
  `java.util.regex` (not a trace, not a Node.js cross-check) — every one matched exactly as
  written. It also timed the pre-fix unbounded pattern on the same adversarial input: at n≥2000 it
  doesn't just get slow, it crashes with `StackOverflowError` in `Pattern$Loop.match` (recursive
  backtracking), while the `{0,3}`-bounded pattern handles n=20000 in ~24ms. **CI must still
  confirm** the Kotlin unit tests compile and pass through Gradle, but the regex behavior itself is
  now verified on a real JVM, not just traced.
