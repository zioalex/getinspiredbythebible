# Language-Mismatch Switch Suggestion (Web + Android)

**Priority:** P2 (Medium — UX/trust refinement; the urgent P0 was already fixed by PR #585)
**Size:** L (multi-PR; backend + web first, Android follow-up)
**Status:** 📝 Plan (approved 2026-05-26 — Option B, both platforms)
**Supersedes:** the silent-override approach originally drafted in PR #630

---

## User Story

**As a** user whose app/UI language differs from the language I'm typing in,
**I want** the assistant to keep replying in my current (selected) language *and*
gently let me know I can switch — with one tap — to the language I'm writing in,
**so that** the choice to change languages is deliberate and the whole interface
(UI chrome + AI responses) stays consistent, instead of the AI silently switching
mid-conversation.

## Background & Decision

PR #585 (2026-05-18) fixed the urgent P0 bug: the web frontend now omits the
`language` parameter, so the backend auto-detects the response language from the
message text. Android sends `null` by default (`LanguagePreferences.DEFAULT_LANGUAGE = ""`),
so the same auto-detection applies. **No silent-override bug exists in the default flow.**

The *only* remaining case is when a user has **explicitly selected** a UI language
(Android language picker, or a future web equivalent) and then types in a different
language. PR #630 originally tried to solve this by making detection silently win for
3+ word messages — but that reverses PR #585's deliberate "explicit choice is honored"
design and risks a jarring UX (e.g. a fully-German UI returning English answers).

**Approved approach (Option B):** when the backend detects that the message language
differs from the selected response language, it keeps responding in the selected
language but returns a structured `language_suggestion` signal. The client renders a
**dismissible banner with a one-tap "Switch" button**. Tapping it changes the UI locale
(syncing chrome + future responses). The switch is always a deliberate user action and
the GUI never silently drifts from the response language.

## Goals

- Response language always equals the selected/UI language (no silent switching).
- When a language mismatch is detected with confidence, surface a localized, dismissible
  switch suggestion with a one-tap action.
- Tapping "Switch" changes the locale so UI chrome **and** subsequent AI responses are in
  the new language — GUI stays in sync.
- Works on web and Android, across all 11 supported locales.

## Non-Goals

- No silent override of the user's explicit language choice (this replaces PR #630).
- No automatic UI locale switching without user action.
- No retroactive translation of prior messages.
- No change to the default (no-explicit-locale) flow already fixed by PR #585.

---

## Architecture Overview

```
message text ──► backend detect_language()  ─┐
                                              ├─► compare ─► language_suggestion (metadata)
selected/UI language (request.language) ──────┘
                                                         │
                              SSE "metadata" chunk ──────┘
                                                         │
                              client renders dismissible banner + [Switch]
                                                         │
                              user taps ─► set locale ─► UI + future responses in new lang
```

Key design points:

- **Backend keeps the original `effective_language` logic** (respond in `request.language`
  when present, else detected). The silent-override from PR #630 is **not** reintroduced.
- The mismatch comparison is additive metadata; it never changes what language the AI
  replies in for the current turn.
- For "GUI always in sync," the **web must resume sending its UI locale** as `request.language`
  (a deliberate, scoped partial-revert of PR #585's omission — but only to *populate the
  suggestion*, not to override detection, since detection only kicks in when language is null).

---

## Implementation Plan

### Slice 1 — Backend (1 PR)

**Files:** `api/chat/service.py`, `api/utils/language.py`, `api/tests/test_chat_coverage.py`,
`api/tests/test_language*.py`.

1. **Add a confidence-aware mismatch check.** `detect_language()` already returns `"en"` for
   short/low-confidence text. To avoid false suggestions, add a helper
   `detect_language_confident(text) -> str | None` in `utils/language.py` that returns the
   detected code only when (a) text length ≥ `min_text_length` and (b) confidence ≥ a
   threshold (reuse the existing `confidence_threshold`); otherwise `None`. This reuses the
   lingua confidence values already computed in `LinguaLanguageDetector.detect`.

2. **Compute the suggestion in both `chat()` and `chat_stream()`** (lines ~333 and ~756):

   ```python
   detected_language = detect_language(request.message)
   effective_language = request.language if request.language else detected_language  # unchanged
   confident = detect_language_confident(request.message)
   language_suggestion = (
       confident
       if (request.language and confident and confident != request.language)
       else None
   )
   ```

   Only suggest when the user **explicitly set** a language (`request.language` present),
   detection is confident, and they differ. Never suggest in the auto-detect (null) flow.

3. **Emit it in the metadata.** Add `"language_suggestion": language_suggestion` to:
   - the non-streaming `ChatResponse` model (new optional field, `str | None = None`), set in
     the three `ChatResponse(...)` build sites.
   - the streaming `"type": "metadata"` dict (lines ~852 and ~809; skip the blocked-response
     path at ~549 — no suggestion there).

4. **Tests:** unit-test `detect_language_confident` (long Italian → "it"; "Ciao" → None;
   English → "en"). Service tests: explicit `language="en"` + Italian 4-word message →
   metadata `language_suggestion == "it"`; matching language → `None`; no explicit language
   (null) → `None`.

**Acceptance for Slice 1:** metadata carries `language_suggestion` exactly when an explicit
non-matching, confident mismatch exists; response language behavior is byte-for-byte
unchanged from current main.

### Slice 2 — Web (1 PR)

**Files:** `frontend/src/lib/api.ts`, `frontend/src/app/[locale]/page.tsx`,
new `frontend/src/components/LanguageSwitchSuggestion.tsx`, `frontend/messages/*.json` (11),
plus a chat-persistence helper.

1. **Resume sending the UI locale.** In `page.tsx`, pass `language: locale` (from `useLocale()`)
   into `streamMessage(...)`. This is required so the backend can populate the suggestion.
   NOTE: with a non-null `language`, the backend responds in the UI locale — which is the
   intended "respond in selected language" behavior; detection-based auto-reply for the
   no-locale case is unaffected because every web request already carries a locale in the URL.
   ⚠️ Confirm this does not regress users who relied on PR #585's auto-detect: since the web
   URL *always* has a locale, PR #585 effectively meant "always auto-detect"; resuming the
   locale changes web behavior to "respond in URL locale + suggest switch." This is the
   explicit product intent of this story, but it IS a behavior change to call out in the PR.

2. **Plumb `language_suggestion`** through `StreamMetadata` / `StreamChunk` in `api.ts` and
   capture it in the metadata handler in `page.tsx` (~line 385).

3. **Render `LanguageSwitchSuggestion`** — a dismissible banner above the composer:
   "It looks like you're writing in *Italiano*. Switch?  [Switch] [Dismiss]". Reuse
   `localeLabels` from `LanguageSwitcher.tsx` for the language name. Localize the surrounding
   copy via a new `Chat.languageSuggestion` namespace in all 11 `messages/*.json`.

4. **Switch action + conversation preservation (KEY RISK).** The existing `LanguageSwitcher`
   does `router.replace(pathname, { locale })`, which navigates and **reloads** — and web chat
   state lives only in React `useState` (only `preferredTranslation` is persisted today). A
   naive switch would **wipe the conversation.** Mitigation: before navigating, persist the
   current messages + session to `sessionStorage` (e.g. `bitb.chat.pending`); on mount in
   `page.tsx`, rehydrate from it if present and clear it. Add tests for the round-trip.

5. **Tests:** `LanguageSwitchSuggestion` render/dismiss; page test that a metadata
   `language_suggestion` shows the banner; switch persists+restores the conversation.

**Acceptance for Slice 2:** banner appears only on a confident mismatch; "Switch" changes the
locale and the conversation survives the reload; copy is localized in all 11 locales.

### Slice 3 — Android (1 PR, follow-up)

**Files:** `data/remote/models/ChatResponseDto.kt` (`MetadataChunkDto` + `StreamChunkDto`),
`domain/models/ChatResponse.kt` (`StreamChunk`), `data/streaming/EventSourceParser.kt`,
`domain/repositories/ChatRepository.kt`, `presentation/viewmodels/ChatViewModel.kt`
(+`ChatUiState`), new `presentation/components/LanguageSwitchBanner.kt`, `ChatScreen.kt`,
`res/values*/strings.xml` (12 dirs).

1. **Wire the field:** add `@SerialName("language_suggestion") val languageSuggestion: String? = null`
   to `MetadataChunkDto`, propagate through `StreamChunk` and the repository into a new
   `ChatUiState.languageSuggestion: String?`.

2. **Render `LanguageSwitchBanner`** following the existing `ChurchFinderBanner` / `WelcomeBanner`
   pattern (already wired in `ChatScreen.kt`). Use `localeLabels`-equivalent display names.
   Add `chat_language_suggestion_*` strings to `values/` and all `values-XX/`.

3. **Switch action:** the banner's "Switch" calls `viewModel.setLocale(code)` (already exists).
   `setLocale` persists via DataStore and triggers an Activity recreate — verify the active
   conversation survives via the existing conversation-resume infrastructure
   (`LastConversationPreferences` / DataStore-backed resume from BITB-027). If it does not,
   persist the in-flight conversation before `setLocale` and resume after recreate.

4. **Dismiss:** add `dismissLanguageSuggestion()` to clear `ChatUiState.languageSuggestion`,
   mirroring `dismissChurchFinderBanner`.

5. **Tests:** parser test for the new field; a ViewModel test that a metadata suggestion sets
   `uiState.languageSuggestion` and that `setLocale` + dismiss clear it. Optionally a Compose
   test in the existing `testDebugCompose` tier for banner visibility.

**Acceptance for Slice 3:** banner shows on confident mismatch; "Switch" flips the locale and
preserves the conversation; dismiss hides it; strings localized in all 12 resource dirs.

---

## Key Risks & Decisions

1. **Web conversation loss on locale switch (highest risk).** Locale change = full navigation;
   chat is not persisted. Must add sessionStorage persist/restore (Slice 2.4) or the feature
   is a regression. Decision: implement persist/restore.

2. **Web behavior change from resuming the UI locale.** Post-#585, web always auto-detected
   (because it sent no locale). Resuming the locale makes web "respond in URL locale + suggest."
   This is the intended product behavior here, but must be explicitly documented in the Slice 2
   PR so it isn't mistaken for a regression of #585.

3. **False suggestions on short/ambiguous text.** Mitigated by `detect_language_confident`
   (length + confidence gates) so the banner never nags on greetings like "Ciao".

4. **Android Activity recreate on `setLocale`.** Must confirm conversation survives; otherwise
   persist+resume around the recreate.

5. **Suggestion fatigue.** Consider suppressing the banner for the rest of a conversation once
   dismissed for a given target language (client-side per-conversation flag). Low priority;
   include the dismiss flag in Slices 2/3.

## Rollout

- Slice 1 (backend) ships first — purely additive metadata, safe to merge alone.
- Slice 2 (web) next — gated behind the metadata; visible feature.
- Slice 3 (Android) as a follow-up PR.
- One PR per slice, one per day, each independently green.
