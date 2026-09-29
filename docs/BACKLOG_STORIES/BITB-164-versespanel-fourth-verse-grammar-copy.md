# BITB-164: `VersesPanel.kt` Is a Fourth, Already-Drifted Copy of the Verse-Reference Grammar

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-09-26
**Found by:** BITB-113's Verify stage, while confirming that story's grammar-unification refactor
covered every hand-written copy of the verse-reference grammar.

## User Story

**As** a maintainer fixing a citation-parsing bug, **I want** every hand-written copy of the
verse-reference grammar accounted for, **so that** a fix doesn't silently miss a fourth copy that
was never on anyone's list.

## Why This Exists

BITB-059/BITB-113 named exactly three verse-citation parsers to keep in sync: the backend
(`api/utils/verse_parser.py`), the frontend (`frontend/src/lib/versePatterns.ts`), and Android's
`ChatMessageItem.kt`. BITB-113's independent Verify pass found a **fourth** hand-written copy:
`android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt` (around
lines 59-75) defines its own `CITED_BOOK_NAME` and `CITED_VERSE_REF_REGEX`, referenced by
`VerseRefRedosTest.kt`'s own comments — so its existence was already known to at least one test
file, just never tracked as a grammar copy to keep synchronized.

It has already drifted from the other three:

- Missing the Hindi/Arabic connector words (के / ال) `ChatMessageItem.kt` and `versePatterns.ts`
  both support.
- Accepts only `:` as the chapter/verse separator — no `,` (breaks German/French/Italian-style
  comma citations, e.g. `Johannes 3,16`, that the other three parsers handle).
- No en-dash range support (`3:16–18`) — hyphen-only, if that.
- ASCII-only `\d` — no Devanagari (`०-९`) or Eastern Arabic-Indic (`٠-٩`) digit support.

## Scope

1. Confirm what `VersesPanel.kt` actually uses this pattern for (read the file — is it rendering a
   citation list, matching against already-known references, or independently detecting new ones
   from free text? The fix differs depending on which).
2. If it's independently detecting references (same job as the other three parsers): bring it onto
   the same generated grammar this story's sibling (BITB-113) introduced —
   `android/app/src/main/kotlin/org/voxquieta/app/utils/VerseGrammar.kt` — the same way
   `ChatMessageItem.kt` now does, so a future grammar fix reaches all copies Android ships, not
   just one.
3. If it's doing something narrower (e.g. matching only references already known to be valid,
   where the missing separators/digits/connectors genuinely can't occur), document why its
   grammar is intentionally narrower instead of leaving the drift unexplained.
4. Add/extend a test so a future drift between this file and the canonical grammar fails CI,
   mirroring `VerseGrammarTest.kt`.
5. Update `docs/AUDIT_PLAYBOOK.md`'s verse-reference-regex row to list this as a fourth tracked
   copy (or explain why it's exempt), so the next audit doesn't have to rediscover it.

## Acceptance Criteria

- [ ] `VersesPanel.kt`'s actual role (independent detector vs. narrower re-match) is established
      and recorded
- [ ] Either migrated onto the shared `VerseGrammar` source, or its narrower scope is documented
      with a reason
- [ ] A test guards against future silent drift for whichever outcome above
- [ ] `docs/AUDIT_PLAYBOOK.md` accounts for this as a fourth copy (tracked or explained)
- [ ] Multilingual test coverage (per AGENTS.md's verse-parsing rule) if this file turns out to be
      an independent detector reachable from user-facing text in non-English locales

## Related

- **BITB-113** — the sibling story whose Verify pass found this
- **BITB-059** — original single-source-of-truth goal for verse parsing
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt`
- `android/app/src/test/kotlin/org/voxquieta/app/components/VerseRefRedosTest.kt` (already
  references `VersesPanel.kt`'s pattern in its comments)
