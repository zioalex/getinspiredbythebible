# BITB-210: Read Aloud — Explain a Missing Voice and Offer Online Voices per Device (Web)

**Status:** 🚧 In Progress (spec confirmed 2026-10-22)
**Priority:** P1
**Size:** M
**Created:** 2026-10-22
**Prompted by:** bug report 2026-10-22 — "I cannot see the voice button in the web version although 1.57.0 is
deployed. The option flag is selected in the menu though." (Linux desktop Firefox; then "I tested also in Chrome and I don't see it either" — Linux desktop Chrome). The production `TTS_ENABLED` flag is on (Terraform default, and the Android app shows Listen against the same server).

Follow-up to BITB-119 / BITB-205.

## Bug report and root cause

The web Listen button renders only when all of these hold (`frontend/src/components/ListenButton.tsx`):
the server flag `features.tts_enabled` is not `false` (default on, `api/config.py`), the
"Show Listen button" preference is on, and `findLocalVoice(locale)` (`frontend/src/lib/speech.ts`)
returns a voice. `findLocalVoice` accepts **only** voices with `localService === true` (BITB-119's
privacy rule: no answer text leaves the device).

When no such voice exists, the button is **hidden silently** while the menu toggle still shows "on"
(`MainMenu.tsx` renders it unconditionally). Common cases:

- **Linux Firefox:** voices come from speech-dispatcher. The Snap/Flatpak builds often can't reach it,
  so `getVoices()` is empty; or no installed voice matches the UI language. Firefox has no online voices.
- **Desktop Chrome / Edge:** Google / Microsoft "online" voices are `localService === false`. Only
  OS-installed language packs are local.
- **Linux Chrome:** usually no voices at all.

The only signal today is the `tts_unavailable` client event.

## Decisions (interview 2026-10-22)

| Question | Decision |
|---|---|
| No offline voice for the language | **Ask per device**: offline voices stay the default. When none exists but the browser has an online voice for the language, offer a one-time opt-in with a short privacy note. |

## Functional requirements

1. **Availability states** per browser + UI language:
   - **local**: an offline voice exists. Behaviour unchanged (BITB-205 play/pause, rail).
   - **online-only**: no offline voice, but an online (`localService === false`) voice exists for the
     language.
   - **none**: no voice for the language at all.
2. **online-only, not yet decided:** Listen shows in the rail. The first tap opens a consent dialog
   saying that online voices send the answer text to the browser's speech service (e.g. Google,
   Microsoft or Apple, depending on the browser), and that offline voices never do.
   - **Allow** → remembered per device (localStorage, try/catch like `ttsPreference.ts`), then speaks
     immediately with the best online voice. Same ranking as `findLocalVoice`: exact tag, regional
     default, default, first.
   - **Not now** → remembered; Listen is hidden for this device, as today.
3. **online-only, allowed:** Listen works like a local voice (play/pause/resume). Native pause is used
   where supported, with the same chunk fallback as BITB-205.
4. **Menu:** under "Show Listen button", a second toggle **"Allow online voices"** appears only when
   the browser has online voices. It reflects and changes the stored consent, and turning it off stops
   any online playback. When the current state is **none**, the menu shows a one-line note under the
   toggle: "This browser has no voice for {language}." Optionally add a link to a short help section.
5. An installed offline voice always wins over an online one, even after consent.
6. Telemetry stays locale-only. Existing `tts_unavailable` is still sent for **none**. No new event
   (out of scope).

## Non-functional requirements

- **11 languages** for the dialog, toggle, note and menu strings (en, it, de, es, fr, pt, ar, ru, zh, hi, ko).
- **Privacy policy:** add a "Read aloud" section to `frontend/public/legal/privacy-policy*.md` (all 11
  locale files). It must say: offline by default; online voices only after opt-in, and then the answer
  text goes to the browser vendor's speech service under that vendor's terms; consent can be revoked in
  the menu. Bump the policy's last-updated date.
- **Accessibility:** the dialog is focus-trapped and closes on Esc (= "Not now"). The note is announced
  by screen readers. 44 px targets.
- **SSR-safe;** never touches `speechSynthesis` while the preference or the server flag is off.

## Acceptance criteria

- [ ] `speech.ts` exposes the availability state (local / online-only / none) plus online-voice selection, unit-tested with the speech mock
- [ ] Consent dialog: Allow speaks and persists; Not now persists and hides; Esc = Not now (Vitest)
- [ ] Menu toggle "Allow online voices" shows only when online voices exist, and revoking stops playback (Vitest)
- [ ] Menu note shown for **none**, naming the UI language (Vitest, cross-language)
- [ ] An offline voice is preferred over an online one even after consent (test)
- [ ] Privacy policy "Read aloud" section in all 11 locale files
- [ ] All new strings in 11 `messages/*.json`; lint, tsc, vitest and build green
- [ ] Owner check on Linux Firefox: the note explains the missing voice. Owner check on desktop Chrome: the opt-in flow works

## Out of scope

- Android app (it already hides Listen without an offline voice; an Android opt-in to network voices
  would be a separate story)
- Our own cloud TTS (BITB-119's deferred option)
- Fixing speech-dispatcher / Snap sandboxing on the user's machine

## Open questions

- Resolved 2026-10-22: for **none**, the menu note only. No disabled button on answers.

## Plan

1. `frontend/src/lib/speech.ts`
   - Factor the ranking out of `findLocalVoice` into `rankVoice(candidates, locale)`.
   - Add `findOnlineVoice(locale)` (same ranking over `localService === false` voices for the language).
   - Add `voiceAvailability(locale): "local" | "online" | "none"`. `findLocalVoice` keeps its behaviour.
2. `frontend/src/lib/onlineVoiceConsent.ts` (new): mirrors `ttsPreference.ts`.
   - Key `voxquieta.onlineVoices` with values `"granted"`, `"denied"` or unset, read in try/catch.
   - Custom change event plus `storage` sync.
   - `useOnlineVoiceConsent()` via `useSyncExternalStore` (server snapshot: unset).
   - `setOnlineVoiceConsent(value)`.
3. `frontend/src/lib/useSpeechAvailability.ts`: also return `onlineVoice` and `availability`, re-evaluated on `voiceschanged`.
4. `frontend/src/components/OnlineVoiceConsentDialog.tsx` (new): follows the existing modal pattern.
   - Look at `FeedbackModal` / `AboutIntroModal` for focus trap, Esc and `role="dialog"`.
   - Copy states that answer text goes to the browser's online speech service.
   - Buttons "Allow online voices" / "Not now".
5. `frontend/src/components/ListenButton.tsx`
   - Voice = local voice, else (consent granted) online voice.
   - Visible when local; when online and consent is not denied; never when none.
   - With online availability and consent unset, the first click opens the dialog: Allow → persist, then speak; Not now → persist denied, button hides.
   - Revoking consent mid-playback stops speech. Keep the existing `tts_unavailable` reporting for **none** only.
6. `frontend/src/components/MainMenu.tsx`
   - Under "Show Listen button", add the toggle "Allow online voices" only when availability is online (or consent granted while online voices exist).
   - When availability is none (with the preference and server flag on), add a muted note "This browser has no voice for {language}" using the existing localized language-name source (find it, e.g. the language switcher). It needs `aria-live="polite"`.
7. i18n: new `Chat` / menu keys in all 11 `frontend/messages/*.json`, with real translations.
8. Privacy policy: a "Read aloud" section in all 11 `frontend/public/legal/privacy-policy*.md`, placed after "Third-Party Services", and the last-updated date bumped (check how `privacy/page.tsx` gets its date).
9. Tests:
   - `speech.test.ts`: availability and online ranking.
   - `onlineVoiceConsent.test.ts`.
   - `ListenButton.test.tsx`: dialog flow, Esc, offline wins, revoke stops.
   - `MainMenu` tests: toggle visibility and the none-note, cross-language via a parametrized locale list.
   - Extend `src/test/speechMock.ts` for `localService: false` voices.

Verification: `cd frontend && npx vitest run && npm run lint && npx tsc --noEmit && npm run build`.
