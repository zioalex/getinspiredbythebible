# BITB-037: Verse Citation Panel Reliability

**Priority:** P1 (High)
**Status:** ✅ Done — range-matching bug fixed (PR #650); backend-driven cited verses shipped as `resolved_verses` field (PR #654); safety net (empty-state → "Show all related") also implemented
**Size:** M (range fix: S/done · backend-driven cited verses: M)
**Created:** 2026-05-30

---

## User Story

**As a** visitor reading an answer,
**I want** the right-hand "Scripture References" panel to show the verses the
assistant actually cited,
**so that** I can read the full context of every verse it quoted instead of
seeing an empty or mismatched panel.

---

## Problem Statement

**Reported behavior:** "The reference card is empty on the web." The right-side
citation panel (`frontend/src/app/[locale]/page.tsx`, the `<aside>` sidebar and
mobile slide-over) frequently shows nothing under its default **"Cited"** filter
even though the assistant clearly quoted verses.

### How the panel works today

1. The sidebar is populated from `scripture_context.verses` — the top-K results
   of **semantic vector search** (`api/scripture/search.py`). These are stored
   in `relevantVerses`.
2. After streaming, the backend sends a `completion` event with `verses_cited`
   (`api/chat/service.py:889-922`) — the verses the **LLM actually quoted**,
   extracted via `parse_structured_citations` + `extract_all_references`
   (`api/utils/verse_parser.py`).
3. The default **"Cited"** filter (`showOnlyReferenced = true`) shows the
   **intersection**: `relevantVerses.filter(v => isVerseReferenced(v, citedSet))`
   (`page.tsx:309-318`).

### Root causes of the empty panel

- **(A) Verse-range citations only matched their first verse.** `verses_cited`
  can be a range, e.g. `"John 3:16-17"` (`VerseReference.__str__`). The old
  `isVerseReferenced` regex (`/(.+)\s+(\d+):(\d+)/`) captured only the start
  verse, so verse 17 of the range was treated as *not* cited and hidden.
  **→ Fixed in this PR** (see below).

- **(B) Architectural divergence (the deeper issue).** The sidebar is driven by
  *semantic search*, but the "Cited" filter intersects it with the *LLM's
  citations*. The LLM routinely cites verses the vector search never surfaced,
  and the vector search routinely surfaces neighbours the LLM never cited. When
  the two sets barely overlap, the intersection — and therefore the default
  panel — is **empty**, even though citations exist in the answer. The verses
  the user most wants (the cited ones) may have no card at all because no card
  was ever created for them.

---

## What this PR already does (TDD)

Fixes root cause **(A)** with a red→green test cycle:

- **Test (red):** `frontend/src/lib/verseExtraction.test.ts` →
  `describe("isVerseReferenced — cited verse ranges")` asserts every verse
  inside a cited range (start/middle/end), en-dash ranges, and correct
  rejection of out-of-range / cross-chapter verses.
- **Fix (green):** `frontend/src/lib/verseExtraction.ts` — `isVerseReferenced`
  now parses an optional range end (`-`/`–`) and matches any verse in
  `[start, end]`.
- **Integration test:** `frontend/src/app/[locale]/page.test.tsx` →
  `describe("verse citation panel — server completion event")` exercises the
  previously-untested `completion`-event path end-to-end: a cited range reveals
  all its verses, an uncited semantic neighbour stays hidden under "Cited" and
  reappears under "All Related".

---

## Proposed long-term fix (root cause B)

Make the cited verses **first-class data** rather than an accident of overlap.

### Backend (primary fix)

1. After computing `verses_cited`, **resolve each cited reference to its verse
   text** via the existing repository lookup
   (`ScriptureRepository.get_verse_by_reference` / `search.py` verse fetch),
   honouring the active translation. Expand ranges to their constituent verses.
2. Emit them in the `completion` event as a structured `cited_verses` array
   (same `VerseResult` shape: `reference`, `text`, `book`, `localized_book`,
   `chapter`, `verse`, `translation`), not just bare strings.
3. Keep `verses_cited` (strings) for backward compatibility / feedback logging.

### Frontend

4. When the `completion` event includes `cited_verses`, **merge them into
   `relevantVerses`** (deduplicating on normalized reference) so every cited
   verse has a card to display, regardless of what semantic search returned.
5. Keep the "Cited" / "All Related" toggle. With (4), the "Cited" view is now
   guaranteed non-empty whenever the answer cited a real verse.
6. **Safety net:** if `showOnlyReferenced` is true and `displayedVerses` is
   empty while `relevantVerses` is non-empty, surface a one-tap "Show all
   related" affordance (the empty-state hint already exists at
   `page.tsx:1030-1037`; wire it to flip the toggle).

### Why backend-driven

Resolving cited verses server-side reuses the canonical book-name
normalization and translation logic already in `verse_parser.py` /
`book_names.py`, avoids shipping more parsing to the client, and guarantees the
card text matches the cited translation.

---

## Acceptance Criteria

- [x] A cited range (`"John 3:16-17"`) marks **every** verse in the range as
      referenced (unit + integration tests).
- [ ] When the assistant cites a verse that semantic search did **not** return,
      that verse still appears as a card in the "Cited" panel (its text fetched
      by the backend).
- [ ] The "Cited" panel is never empty when the answer contains at least one
      valid verse citation.
- [ ] "All Related" continues to show the full semantic result set.
- [ ] Cited-verse card text respects the active/detected translation.
- [ ] No regression in the 529-test frontend suite.

---

## Test Plan

- **Unit:** `verseExtraction.test.ts` range cases (done). Add backend
  `verse_parser` range-expansion + reference-resolution tests in
  `api/tests/`.
- **Integration:** extend `page.test.tsx` "server completion event" suite with
  a `cited_verses` payload whose references are absent from
  `scripture_context.verses`, asserting the cards still render.
- **Manual (web):** run `frontend` (`npm run dev`) + API, ask a question that
  triggers a ranged or out-of-corpus citation, confirm the panel matches the
  cited verses. See `verify` / `run` skills.

---

## Files

- `frontend/src/lib/verseExtraction.ts` — `isVerseReferenced` (range fix, done)
- `frontend/src/app/[locale]/page.tsx` — `referencedVerses` / `displayedVerses`
  / completion-event handler (merge `cited_verses`, toggle safety net)
- `frontend/src/lib/api.ts` — add `cited_verses` to `StreamChunk` / completion
- `api/chat/service.py` — resolve + emit `cited_verses`
- `api/utils/verse_parser.py`, `api/scripture/search.py` — range expansion &
  reference→text resolution
