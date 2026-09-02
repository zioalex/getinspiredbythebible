# BITB-116: Bound the Remaining Unbounded Group in ChatMessageItem's Alt-1 Numbered-Prefix Branch

**Status:** 🎯 Todo
**Priority:** P3 — benchmarked and currently within budget; not an active incident, but the same
ReDoS *shape* BITB-108/BITB-114 closed elsewhere
**Size:** S
**Created:** 2026-09-02
**Found by:** BITB-114 (Android connector-group ReDoS fix), flagged as residual rather than folded in

## The Finding

BITB-114 bounded the connector-repeat group inside `BOOK_NAME` (`ChatMessageItem.kt`) and
`CITED_BOOK_NAME` (`VersesPanel.kt`) to `{0,3}`, closing the ReDoS shape audit item E13 identified
(mirroring the web fix in BITB-108).

A second, separate unbounded group survives in `ChatMessageItem.kt`'s Alt-1 (numbered-prefix)
branch of `DEFAULT_VERSE_REF_REGEX` and `buildVerseRefRegex()`, applied immediately after
`$BOOK_NAME`:

```
(?:\s+[\p{L}][\p{L}\p{M}\d]+)*
```

This exists to support 3-word Arabic numbered-book names (e.g. "1 أخبار الأيام" = "1 Chronicles").
It was exercised (not ignored) by BITB-114's adversarial-input timing tests and stayed within the
500ms budget at the tested input size, so this is not a known-broken regression — but it was never
independently bounded or benchmarked in isolation the way the connector group was, and its
worst-case behavior at larger adversarial inputs is unverified.

## Proposed Fix

Bound this group the same way: a small fixed range (start from `{0,2}`, since Arabic numbered names
need at most 2 extra words after the connector-bearing `BOOK_NAME` — verify the actual max against
`LocalizedBookToEnglish.kt` / the Arabic book-name data before picking the exact bound, the same way
BITB-114 verified its bound against real data rather than guessing). Add a dedicated adversarial
benchmark isolating this group specifically (not just incidentally covered by BITB-114's tests), plus
a cap-enforcement test proving the bound is real, mirroring BITB-108/BITB-114's two-part test
structure.

## Acceptance Criteria

- [ ] Alt-1's trailing `(?:\s+[\p{L}][\p{L}\p{M}\d]+)*` group bounded (not unbounded `*`)
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
