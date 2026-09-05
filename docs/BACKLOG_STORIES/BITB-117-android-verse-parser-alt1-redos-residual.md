# BITB-117: Bound the Remaining Unbounded Android Alt-1 Numbered-Prefix Groups

**Status:** 🎯 Todo
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

- [ ] Both Alt-1 trailing groups bounded (not unbounded `*`)
- [ ] Bound justified against real Arabic (and any other) numbered multi-word book names, not guessed
- [ ] Dedicated adversarial-input benchmark for this specific group, before and after
- [ ] Regression test proving real numbered multi-word names (e.g. "1 أخبار الأيام") still match
- [ ] Cap-enforcement test proving the bound is actually enforced, not just documented
- [ ] `docs/BACKLOG_STORIES/BITB-114-android-verse-parser-redos.md`'s "Residual Risk" section updated
      to point at this story as closing the gap it flagged

## Related

- **BITB-114** — closed the connector-group ReDoS shape on Android; flagged this as residual
- **BITB-108** — the original web-side finding and fix this whole chain follows
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt`
