# BITB-192: Android Link Labels Insert a Space Between a CJK Book Name and the Chapter

**Status:** 🎯 Todo
**Priority:** P3
**Size:** XS
**Created:** 2026-10-12
**Prompted by:** BITB-179 follow-up — verifier nit, pre-existing behaviour.

## Bug Report

`injectVerseLinks` (`android/.../ChatMessageItem.kt` ~L449) rebuilds the link label as
`"$book $chapter$sep$verse"`. For CJK text written without a space (`路加福音1：79`) the label becomes
`路加福音 1：79`, so Android shows text the user or model did not write. The web keeps the original
substring (`linkifyVerses.ts`).

## Functional Requirements

- FR1 Build the label from the original matched text (as web does), keeping the separator, digits
  and spacing as written; the URL stays ASCII.

## Acceptance Criteria

- [ ] `路加福音1：79`, `约翰福音３：１６` and `John 3:16` keep their exact original text in the label
- [ ] Existing `VerseRefLinkTest` label assertions updated deliberately, not loosened
