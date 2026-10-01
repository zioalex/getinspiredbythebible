# BITB-166: Server `versesCited` Path Still Uses Prefix (`startsWith`) Verse Matching on Android

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-09-30
**Found by:** BITB-164

## User Story

**As** a reader of the Cited tab, **I want** only the verses the assistant actually cited to be
listed, **so that** citing John 3:16 does not also show John 3:1.

## Why This Exists

BITB-164 replaced the client-regex fallback in `referencedVerses` (VersesPanel.kt) with exact
chapter + verse + book matching. Two server-citation paths still compare with prefix matching:

- `referencedVerses`, server `versesCited` branch: `citedLower.any { it.startsWith(baseRef) }`
  where `baseRef = "book chapter:verse"` -- a server citation `john 3:16` also satisfies
  `john 3:1`.
- `ChatMessageItem.citedVerses`: same `startsWith` shape.

The prefix was meant to tolerate range suffixes (`Romans 8:28-30`), which needs an explicit
range-aware comparison, not a prefix test.

## Scope

1. Parse each server citation into book / chapter / verse-start / optional range end.
2. Match on exact equality (book case-insensitive, chapter and verse ints); decide explicitly
   whether verses inside a cited range should match.
3. Apply to both `referencedVerses` and `ChatMessageItem.citedVerses`, ideally through one shared
   helper.

## Acceptance Criteria

- [ ] Both paths match on exact chapter + verse + book (range suffixes handled explicitly)
- [ ] Regression tests: a `John 3:16` citation does not surface John 3:1; `Romans 8:28-30` still
      resolves; multi-language book names (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) unaffected

## Related

- **BITB-164** -- fixed the same bug for the client-regex fallback
