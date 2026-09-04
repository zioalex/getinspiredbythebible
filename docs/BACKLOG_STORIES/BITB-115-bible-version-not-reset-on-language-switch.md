# BITB-115: Bible Version Sticks to the Old Language After a Language Switch

**Status:** 🎯 Todo
**Priority:** P1 — user-visible correctness bug on the core product surface (wrong-language
scripture served after an explicit language change)
**Size:** S–M (web fix is small; Android needs a DTO field added first)
**Created:** 2026-09-04
**Reported by:** product owner, from real usage — "when you select to change the language inline,
like in a message, the Bible is not changed, so it stays with the previous language"
**Affects:** web (`frontend/`), Android (`android/`) — the backend behaves as designed

## User Story

**As** a reader who switches the app to another language, **I want** the Bible version to follow me
to that language's default version, **so that** the verses I am shown are in the language I just
asked to read in — instead of silently staying in the language I left.

## The Bug

Switching the UI language does not touch the persisted Bible-version preference. The preference is
stored per-device (never per-language), so it survives the switch and keeps overriding the new
locale's default version. The user gets an English UI quoting the Italian Bible (or vice versa).

Both switch paths are affected — the inline banner *and* the top-bar picker. Verified: the picker
was explicitly checked at the product owner's request and behaves identically, because both paths do
nothing but `router.replace(pathname, { locale })`.

### Why it happens (web)

1. `frontend/src/app/[locale]/ChatIsland.tsx:234` — on mount, the component restores
   `localStorage["preferredTranslation"]` into `selectedTranslation`. The key is a bare translation
   code with no record of which language it was chosen under.
2. `ChatIsland.tsx:866` (`handleLanguageSwitch`, the inline banner) and
   `frontend/src/components/LanguageSwitcher.tsx:27` (`handleChange`, the top-bar picker) both only
   call `router.replace(pathname, { locale })`. Neither clears nor re-scopes the stored version.
3. The remount re-reads the same stale key, so `selectedTranslation` comes back set to the old
   language's version.
4. `ChatIsland.tsx:512-514` then sends `preferred_translation: <stale code>` alongside
   `language: <new locale>` on the very next message.
5. `api/utils/language.py:530` (`resolve_translation`) is documented to rank an explicit user
   preference above the language default — correctly, since the client asserted a preference. The
   backend cannot tell a deliberate cross-language choice from a stale carry-over.

Net effect: the language-based default at `api/utils/language.py:19-35` (`LANGUAGE_TRANSLATIONS` —
`it → ita1927`, `de → luther1912`, `en → web`, …) is never reached after a switch, and the
Bible-version chip keeps showing the old language's version.

`detectedTranslation` is *not* the culprit: it is per-conversation state that resets on the remount.
The bug is entirely the persisted preference.

### Reproduction (verified 2026-09-04)

A throwaway vitest against the real `ChatIsland` (mocked `@/lib/api`), run locally and then deleted:

| Case | Setup | Observed |
|---|---|---|
| A | `preferredTranslation="ita1927"` in `localStorage`, render at locale `en`, send a message | `streamMessage` called with `{"preferredTranslation":"ita1927","language":"en"}` — English UI, Italian Bible |
| B | Inline banner → click **Switch** (`language_suggestion: "it"`) | `router.replace("/", {locale:"it"})` fires; `localStorage["preferredTranslation"]` still `"web"` |
| C | Top-bar `LanguageSwitcher` → pick *Italiano* | identical to B — `router.replace` fires, preference untouched |

Manual equivalent: pick a Bible version in language A, switch to language B by either path, ask a
question — the answer's verses and the version chip are still language A's version.

### Android has the same defect

`ChatViewModel.setLocale` (`android/.../presentation/viewmodels/ChatViewModel.kt:819`) persists the
new locale and recreates the Activity, but never touches `TranslationPreferences`; the send path
(`ChatViewModel.kt:464-472`) then pairs the stale `preferredTranslation` with the new `language`,
exactly as the web client does. It affects both the `LanguageSwitchBanner` and the Settings-screen
language picker. Android additionally cannot yet *tell* which language a stored version belongs to:
`TranslationDto` (`android/.../data/remote/models/TranslationDto.kt`) drops the `language_code`
field the API already returns.

## Proposed Fix

Make the stored preference **language-scoped** rather than global, so a switch stops leaking a
version across languages while a deliberate choice is still remembered per language.

Web:

- Key the preference by locale (e.g. `preferredTranslation:<locale>`, or one JSON map
  `{ "en": "kjv", "it": "ita1927" }`). Reading at mount then naturally yields nothing for a
  language the user has never chosen a version in, so the backend applies that language's default.
- Migrate the existing bare `preferredTranslation` value once: map it to the locale matching its
  `language_code` from `GET /api/v1/scripture/translations`, then drop the legacy key. A value whose
  language cannot be resolved is discarded, not carried over.
- Do not send `preferred_translation` at all when the current locale has no stored choice — that is
  what lets `resolve_translation` fall through to `LANGUAGE_TRANSLATIONS`.

Android: mirror the same scoping in `TranslationPreferences` (locale-keyed entry, or clear on
`setLocale` when the stored version's language differs), and add `language_code` to `TranslationDto`
so the client can make that comparison at all.

Explicitly **not** in scope: restricting `TranslationSwitcher` to the current locale's versions.
Choosing another language's Bible on purpose stays possible — this story only stops the *implicit*
carry-over across a language change.

Leave the backend's precedence rule (`resolve_translation`) alone: the fix belongs in the clients,
which are the only place that knows a preference is stale.

## Acceptance Criteria

- [ ] Web: switching language via the **inline banner** leaves no version preference for the new
      locale unless the user has chosen one there; the next message sends no
      `preferred_translation`, and the served verses are the new language's default version
- [ ] Web: switching via the **top-bar picker** behaves identically (same code path, same test)
- [ ] Web: a version deliberately chosen in language A is still remembered when the user returns to
      language A later
- [ ] Web: legacy bare `preferredTranslation` values are migrated once (mapped to their own
      language) or discarded — never applied to a different language
- [ ] Web: the Bible-version chip reflects the new language's version immediately after the switch,
      not the old one
- [ ] Android: same behaviour for the language banner and the Settings language picker;
      `TranslationDto` carries `language_code`
- [ ] Regression tests on both platforms covering both switch paths — the three cases in the
      reproduction table above, inverted to assert the fixed behaviour
- [ ] No backend change; `api/utils/language.py::resolve_translation` precedence stays as documented

## Related

- `frontend/src/app/[locale]/ChatIsland.tsx` (lines 212, 215-219, 234, 338-345, 512-514, 866-877)
- `frontend/src/components/LanguageSwitcher.tsx:27`, `frontend/src/components/TranslationSwitcher.tsx`
- `api/utils/language.py:19-35` (`LANGUAGE_TRANSLATIONS`), `:512-537` (`resolve_translation`)
- `android/.../presentation/viewmodels/ChatViewModel.kt:464-472, 819-827`,
  `android/.../data/preferences/TranslationPreferences.kt`,
  `android/.../data/remote/models/TranslationDto.kt`
- **BITB-071** — same "three clients diverge on one behaviour" trap, previous instance
