# BITB-031: Follow-up — Default Verse Panel to "Referenced" (Web fix + Android parity)

**Status:** 🎯 Todo
**Priority:** P1
**Size:** S (< 4 hours)
**Created:** 2026-05-10
**Follow-up to:** PR #521 / `default-referenced-filter.md`

## Problem

PR #521 changed the web verse panel default from "All Related" to "Referenced"
by flipping `useState(false)` → `useState(true)` for `showOnlyReferenced` in
`frontend/src/app/[locale]/page.tsx`. After merge, the user reports that the
panel **still opens with "All Related" verses in focus** instead of the
"Referenced" subset — i.e., the intended behavior change is not actually
visible to end users.

In addition, the Android app currently defaults to the same noisy "All Related"
view (`VersesPanel.kt:159` — `var showReferenced by rememberSaveable {
mutableStateOf(false) }`), so the UX is inconsistent across platforms even
once the web side is fixed.

## As a / I want / So that

**As a** user reviewing verse references on web or Android,
**I want** the verse panel to default to "Referenced" verses on every fresh
session,
**so that** I see the verses the AI actually cited first and am not buried
under semantically-similar verses.

## Investigation Scope (Web)

PR #521's one-line state change is correct in isolation, so the bug must live
elsewhere. Things to verify:

- [ ] Confirm the deployed bundle actually contains the
  `useState(true)` change (rule out a stale CDN / build cache).
- [ ] Check `rememberSaveable`-style behavior — is the toggle state being
  hydrated from `localStorage`, URL param, or a parent provider that overrides
  the initial `true`?
- [ ] Inspect `displayedVerses` memo (`page.tsx:270-278`) and
  `isVerseReferenced(verse, referencedVerses)` matching logic — if
  `referencedVerses` is empty (e.g., book-name normalization mismatch between
  `versesCited` and `relevantVerses`), the "Referenced" tab will render an
  empty list and the user may perceive the panel as defaulting to "All
  Related".
- [ ] Verify `referencedVerses` is populated correctly for both streaming and
  non-streaming responses, and across all supported locales (especially CJK,
  Italian inflected forms, and `<<Book>>` guillemet syntax).
- [ ] Verify behavior on both desktop sidebar (lines 835-864) and mobile
  slide-over panel (lines 951-963).

## Functional Requirements

- [ ] On first page load (web), the "Referenced" filter is the active tab and
  the panel renders only cited verses.
- [ ] If no verses have been cited yet, the empty-state copy for "Referenced"
  is shown (not a silent fallback to "All Related").
- [ ] Users can still toggle to "All Related" and back; toggle state is
  preserved during the conversation but resets to "Referenced" on page reload.
- [ ] Android `VersesPanel` opens with `showReferenced = true` by default
  (`rememberSaveable` initial value flipped).
- [ ] Android empty state mirrors the web copy when no verses are cited.

## Non-Functional Requirements

- **Consistency:** identical default across web and Android.
- **Performance:** filter switching remains instant client-side.
- **Accessibility:** active segment has correct ARIA / Compose semantics.
- **Locales:** behavior verified in at least en, it, zh (CJK), ko (CJK).

## Acceptance Criteria

- [ ] Web: fresh load of the chat page shows "Referenced" active and the
  panel content matches the cited verses (verified by manual QA + a vitest
  assertion on initial render state).
- [ ] Web: regression test added that asserts `displayedVerses.length` equals
  the cited subset on initial render when `relevantVerses` and
  `referencedVerses` overlap.
- [ ] Web: root cause for the user-reported "didn't work" symptom is
  identified and documented in the PR description (build cache vs. matching
  bug vs. empty `referencedVerses`).
- [ ] Android: `VersesPanel` defaults `showReferenced` to `true`; existing
  unit tests updated and passing.
- [ ] Android: empty-state string is shown when "Referenced" is selected and
  no verses are cited yet (no silent fallback).
- [ ] Both platforms: manual QA performed with a CJK conversation and an
  Italian conversation to confirm citation matching works.

## Tech Constraints

- Web: change must work for both desktop sidebar and mobile slide-over panel
  (`page.tsx` lines 835 and 951).
- Android: change in `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/VersesPanel.kt:159`.
- Three verse parsers (`api/utils/verse_parser.py`, `frontend/src/lib/versePatterns.ts`,
  Android `ChatMessageItem.kt`) must remain in sync — if the root cause turns
  out to be a parser mismatch, fix in all three.
- Don't add a new persistence mechanism (no localStorage / DataStore) for the
  toggle — out of scope.

## Out of Scope

- Persisting the user's filter choice across reloads.
- Adding new filter modes beyond "Referenced" / "All Related".
- Redesigning the segment control.

## Testing Requirements

1. **Web — fresh load:** open the app, send a message with cited verses →
   "Referenced" tab is active and shows only cited verses.
2. **Web — no citations:** send a message where the AI doesn't cite verses
   → empty state is shown, not "All Related" fallback.
3. **Web — locale matrix:** repeat (1) for `en`, `it`, `zh`, `ko`.
4. **Android — fresh launch:** open verse panel after a message with citations
   → "Referenced" segment is selected.
5. **Android — toggle persistence:** switch to "All Related", rotate device →
   selection preserved (`rememberSaveable`); fully relaunch app → resets to
   "Referenced".
6. **Regression:** run existing frontend vitest suite and Android
   `testDebugUnitTest`; both must pass.

## Notes for Implementer

- Start by reproducing the web symptom in a local dev build. If `useState(true)`
  works locally, the production issue is likely a stale bundle / CDN cache and
  the fix is operational rather than code.
- If the symptom reproduces locally, instrument `referencedVerses` and
  `isVerseReferenced` to confirm whether the cited set is being populated
  correctly. The most likely code-level cause is a normalization mismatch
  between localized book names in `versesCited` (from the streaming payload)
  and the canonical form used in `relevantVerses` (from semantic search).
