# User Story: Fix Verse Reference Parsing for Multi-Language Conjunctions

**As a** user reading AI responses in Italian, Spanish, German, or French
**I want** verse references like "Salmi 51:6 e 51:17" to be parsed correctly
**So that** I can click on verse references without encountering broken links

## Functional Requirements

- [ ] Verse reference parser correctly identifies Bible book names in all supported languages
- [ ] Parser excludes common conjunctions (and, e, y, und, et, o, a) from being treated as book names
- [ ] Multi-verse citations like "John 3:16 and 3:17" or "Salmi 51:6 e 51:17" parse correctly
- [ ] Clicking on a verse reference opens the correct chapter modal
- [ ] Parser works consistently in ChatMessage component and verse extraction utility

## Non-Functional Requirements

- **Correctness:** No false positives (treating conjunctions as books)
- **Correctness:** No false negatives (missing actual book names)
- **Internationalization:** Support for EN, IT, ES, DE, FR conjunctions
- **Maintainability:** Conjunction list should be easy to extend for new languages
- **Performance:** Regex updates should not impact rendering performance

## Acceptance Criteria

- [ ] "Salmi 51:6 e 51:17" does NOT create a link to "/chapter/e/51"
- [ ] "John 3:16 and 3:17" does NOT create a link to "/chapter/and/3"
- [ ] "Römer 8:28 und 8:39" does NOT create a link to "/chapter/und/8"
- [ ] "Juan 1:1 y 1:14" does NOT create a link to "/chapter/y/1"
- [ ] Valid book names still work: "Giovanni 3:16", "1 John 2:3", "Song of Solomon 1:1"
- [ ] Verse references are still clickable and highlighted correctly
- [ ] Chapter modal opens with correct book, chapter, and verse
- [ ] Fix applies to both ChatMessage highlighting AND verse extraction utility

## Tech Constraints

- Must update regex patterns in:
  - `frontend/src/components/ChatMessage.tsx` (verse highlighting)
  - `frontend/src/lib/verseExtraction.ts` (verse reference extraction)
- Regex must use Unicode support for accented characters (Italian: à è é, German: ö ü, etc.)
- Maintain backward compatibility with existing verse reference formats
- Should not break existing verse highlighting or extraction logic

## Out of Scope

- Adding support for verse ranges (e.g., "Salmi 51:6-17") — already supported
- Supporting completely new languages beyond current set
- Handling abbreviated book names (e.g., "Ps" for "Psalms")
- Parsing verse references that span multiple books

## Current Behavior

When AI response contains "Salmi 51:6 e 51:17", the parser treats "e 51:17" as a verse reference with book name "e", creating an invalid API call to `/chapter/e/51`.

## Expected Behavior

Parser should recognize "e" (Italian "and") as a conjunction and skip it, only parsing "Salmi 51:6" as a valid verse reference. Alternatively, parse it as two separate references: "Salmi 51:6" and "Salmi 51:17" (with implicit book name).

## Conjunction List (Non-Exhaustive)

- **English:** and, or
- **Italian:** e, ed, o, od, a (to)
- **Spanish:** y, e (before i-), o, u (before o-)
- **German:** und, oder
- **French:** et, ou

## Testing Requirements

1. **Italian:** "Salmi 51:6 e 51:17" → should NOT parse "e 51:17"
2. **Spanish:** "Juan 1:1 y 1:14" → should NOT parse "y 1:14"
3. **German:** "Johannes 3:16 und 3:17" → should NOT parse "und 3:17"
4. **French:** "Jean 3:16 et 3:17" → should NOT parse "et 3:17"
5. **English:** "John 3:16 and 3:17" → should NOT parse "and 3:17"
6. **Valid books:** "1 John 2:3", "Song of Solomon 1:1", "1. Mose 1:1" → should still work
7. **Edge case:** Single letter books (if any exist in translations) → verify not broken
8. **Click test:** Click each parsed reference → verify correct chapter modal opens

## Implementation Notes for Orchestrator

The regex pattern should exclude words that:

1. Are 1-3 characters long AND
2. Match known conjunction list AND
3. Are followed by a number pattern (chapter:verse)

Suggested approach: Use negative lookbehind or exclude short words from book name capture group.

---

**Priority:** High
**Effort:** Medium (regex updates + multi-language testing)
**Impact:** Fixes critical bug affecting non-English users
