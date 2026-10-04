# BITB-119: Read the Answer Aloud — Speak Vox Quieta's Response (Web + Android)

**Status:** 🚧 In Progress
**Priority:** P2 — new capability, not a defect; sequence after the cost decision below is made
**Size:** L (M per platform + a shared text-normalization layer; see Cost of Implementation)
**Created:** 2026-09-04
**Prompted by:** product request — "speak loudly the Vox Quieta response". Paired with BITB-120
(voice input). They share rollout/configuration and some locale work, but remain separate because
output and input have independent user value, platform APIs, permissions, data flows, failure modes
and release risk; either can ship or be withdrawn without the other.

## User Story

**As** someone who came to Vox Quieta while driving, cooking, praying with eyes closed, or simply
tired of reading a screen, **I want** to press a button and hear the answer spoken, **so that** the
response reaches me the way a quiet voice would — without me having to read it.

## Specification (agreed 2026-10-04)

Decisions taken with the product owner in the Specify stage. Where this section and the older
analysis below disagree, **this section wins**.

| Decision | Choice |
|---|---|
| Engine | Option 1 — platform on-device synthesis only (no cloud TTS) |
| Verse references | Spoken as **localized words** ("John chapter 3, verse 16"), template per language in a shared fixture |
| Control | Single **Listen ↔ Stop** toggle (no pause/resume) |
| Default | **Enabled by default** whenever the prerequisites are met (flag true, local voice present, user setting on) |
| Missing `/config` | **Fail open**: only an explicit `tts_enabled: false` hides the control; unreachable/older backend → still shown if a local voice exists |
| User option | New user preference **"Show Listen button"** (default on) — Android Settings screen, web main menu |
| Web telemetry | New `POST /api/v1/client-events` sink → OTel counter `client.tts_events_total{event,locale}` (App Insights); event + locale only |
| Delivery | One PR covering backend, web, Android, shared fixture, i18n, changelog |

### Functional requirements

- **FR1 — Listen control.** Assistant messages get a Listen button in the existing action row
  (web `ChatMessage.tsx`, Android `ChatMessageItem.kt`). It shows only when the message has finished
  streaming and is non-empty. While speaking, the same button shows **Stop** (icon + label/aria
  change). Tap again → silence.
- **FR2 — Visibility rule.** Shown iff all of: (a) server flag is not explicitly `false`;
  (b) user preference "Show Listen button" is on; (c) the platform exposes speech synthesis;
  (d) at least one *local* voice matches the message language (UI locale). Otherwise hidden — never
  shown-and-broken.
- **FR3 — Local-only voices.** Web: only `SpeechSynthesisVoice` with `localService === true` whose
  `lang` primary subtag matches the locale (prefer exact region match, then `default`). Android: only
  `Voice` with `isNetworkConnectionRequired == false` and matching language; if
  `isLanguageAvailable` reports missing data, hide the control (no install prompt in v1).
- **FR4 — One voice at a time.** Starting a message stops any other message speaking. Navigating
  away, switching/starting a conversation, changing locale, backgrounding the Android activity
  (`ON_STOP`) or unmounting the chat stops playback.
- **FR5 — Speakable-text normalization**, specified once in `tests/fixtures/speakable_text.json`
  and implemented in `frontend/src/lib/speakableText.ts` and Android `tts/SpeakableText.kt`:
  1. Markdown links `[text](url)` → `text`; bare `http(s)://` URLs removed.
  2. Emphasis/code markers (`*`, `**`, `_`, `__`, `~~`, `` ` ``), heading `#`s, blockquote `>`,
     bullet markers (`-`, `*`, `+` at line start) and horizontal rules removed; numbered list
     numbers kept.
  3. Guillemets `<<Book>>` / `《Book》` → `Book`.
  4. Verse references detected with **the platform's existing verse parser** (no new regex family)
     and replaced with the locale template, keeping the book name as written:

     | lang | single verse | range | chapter only |
     |---|---|---|---|
     | en | `{book} chapter {c}, verse {v}` | `{book} chapter {c}, verses {v} to {e}` | `{book} chapter {c}` |
     | it | `{book} capitolo {c}, versetto {v}` | `{book} capitolo {c}, versetti da {v} a {e}` | `{book} capitolo {c}` |
     | de | `{book} Kapitel {c}, Vers {v}` | `{book} Kapitel {c}, Verse {v} bis {e}` | `{book} Kapitel {c}` |
     | es | `{book} capítulo {c}, versículo {v}` | `{book} capítulo {c}, versículos {v} al {e}` | `{book} capítulo {c}` |
     | fr | `{book} chapitre {c}, verset {v}` | `{book} chapitre {c}, versets {v} à {e}` | `{book} chapitre {c}` |
     | pt | `{book} capítulo {c}, versículo {v}` | `{book} capítulo {c}, versículos {v} a {e}` | `{book} capítulo {c}` |
     | ar | `{book} الإصحاح {c}، الآية {v}` | `{book} الإصحاح {c}، الآيات {v} إلى {e}` | `{book} الإصحاح {c}` |
     | ru | `{book}, глава {c}, стих {v}` | `{book}, глава {c}, стихи с {v} по {e}` | `{book}, глава {c}` |
     | zh | `{book}第{c}章第{v}节` | `{book}第{c}章第{v}至{e}节` | `{book}第{c}章` |
     | hi | `{book} अध्याय {c}, पद {v}` | `{book} अध्याय {c}, पद {v} से {e}` | `{book} अध्याय {c}` |
     | ko | `{book} {c}장 {v}절` | `{book} {c}장 {v}절부터 {e}절까지` | `{book} {c}장` |

     Templates live in the fixture (single source); clients load/mirror them and a parity test
     asserts each client's table equals the fixture.
  5. Whitespace collapsed; blank lines become sentence breaks.
- **FR6 — Chunking.** Normalized text is split at sentence boundaries (`. ! ?` + CJK `。！？`,
  Devanagari `।`, Arabic `؟`, and newlines) into chunks of **≤ 200 characters** (hard-split at the
  last space, or at 200 for CJK, if a sentence is longer). Chunks are queued in order; the whole
  answer is read. Same algorithm and fixture cases on both clients.
- **FR7 — Android audio focus.** Request transient audio focus
  (`AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK`, usage `USAGE_ASSISTANT`, content `SPEECH`) before speaking;
  stop on focus loss; abandon focus on stop/finish. `TextToSpeech` is a Hilt singleton wrapped in a
  `SpeechEngine` interface (fake in tests); shut down with the process.
- **FR8 — Server flag.** `Settings.tts_enabled: bool = True` (env `TTS_ENABLED`), published as
  `GET /config` → `features.tts_enabled`. Added to `scripts/env-manifest.yaml` and Terraform/app
  settings with default `true`. Web reads it through `serverConfig.tsx`; Android through
  `ConfigResponseDto` → `ChatViewModel` state. Absent/failed → treated as enabled (fail open).
- **FR9 — User preference.** "Show Listen button" switch, default on. Android: Settings screen,
  persisted with the existing preferences mechanism. Web: a toggle item in `MainMenu.tsx`, persisted
  in `localStorage` (try/catch; failure → default on).
- **FR10 — Telemetry.** Android: `AnalyticsHelper` events `tts_started` and `tts_unavailable`
  with `locale`. Web: `POST /api/v1/client-events` body `{event, locale}`; event whitelist
  `tts_started|tts_unavailable`, locale whitelist = the 11 supported locales (else `other`);
  rate-limited with the shared dependency; increments `client.tts_events_total`. `tts_unavailable`
  is reported at most once per locale per page load / app session, only when the flag and preference
  are on but no local voice exists. No message text, IDs or user agent recorded.
- **FR11 — Changelog.** What's New entry on web (`WhatsNewModal.tsx`) and Android
  (`WhatsNewBottomSheet.kt`), all 11 locales.

### Non-functional requirements

- **Platforms:** web (Chrome, Edge, Safari incl. iOS user-gesture start, Firefox — hidden if no
  local voice); Android `minSdk 24`+ (BITB-122): API 26 audio-focus APIs behind an SDK check, legacy `requestAudioFocus` on 24–25. iOS app out of scope (BITB-087 inherits FR5/FR6 fixture).
- **Languages:** all 11 (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) for UI strings, templates and
  fixture cases; parametrized cross-language tests on both clients.
- **Privacy:** no message text or audio leaves the device; telemetry sink accepts only whitelisted
  enums. No privacy-policy change required (verify wording in the PR).
- **Accessibility:** button has a localized accessible name that changes Listen ↔ Stop
  (`aria-pressed` on web, `contentDescription` + `stateDescription` on Android); 48 dp / 44 px
  touch target; keyboard operable on web.
- **Performance:** voice discovery happens once (web `voiceschanged`, Android `OnInitListener`);
  normalization is O(n) on ≤ ~4 k chars; no added network calls on the chat path.

### Acceptance criteria (testable)

1. [ ] `GET /config` returns `features.tts_enabled` (default `true`, `TTS_ENABLED=false` → `false`);
   pytest covers both.
2. [ ] `POST /api/v1/client-events` accepts the two events, maps unknown event → 422 or `other`
   (documented), unknown locale → `other`, increments the counter, is rate-limited; pytest covers
   happy path, whitelist and rejection of extra fields.
3. [ ] `tests/fixtures/speakable_text.json` exists with ≥ 1 normalization case per language (11),
   plus markdown/link/URL/guillemet/German-comma/numbered-book/range/fullwidth/RTL cases and
   chunking cases; vitest and JUnit parity tests consume it and pass.
4. [ ] Web: Listen button renders only when flag≠false, pref on, and a `localService` voice matches;
   hidden for remote-only voices, no `speechSynthesis`, streaming, or pref off (vitest with mocked
   `speechSynthesis`).
5. [ ] Web: clicking speaks chunks in order via `SpeechSynthesisUtterance` with the matched voice;
   clicking again calls `cancel()`; starting another message cancels the first; unmount cancels.
6. [ ] Android: same visibility rules against a fake `SpeechEngine` (network-required voices
   ignored, missing language data hides); start/stop/one-at-a-time; `ON_STOP` stops; audio focus
   requested and loss stops playback (unit + Compose tests).
7. [ ] Settings preference on both platforms toggles the control and persists.
8. [ ] Telemetry fires as FR10 on both platforms (tests assert payload contains only event+locale).
9. [ ] All new strings present in all 11 locales on both platforms (Android translation validation
   and frontend message parity tests pass).
10. [ ] What's New / changelog entries on both platforms.
11. [ ] Backend, frontend (lint, tsc, vitest, build) and Android (unit, compose, lint) suites green
    in CI.

### Out of scope

- Playback with the screen off / app in background (stops on `ON_STOP` by design) — BITB-176.
- Localized What's New text: v1 ships the English release-please entry only (decided 2026-10-04) — BITB-175.

- Cloud/neural TTS, a speech endpoint, server-side audio (Option 2 — separate story).
- Pause/resume, speed/pitch/voice pickers, highlighting the word being read, auto-read on arrival.
- Prompting Android users to install TTS language data (`ACTION_INSTALL_TTS_DATA`).
- Reading verse cards, follow-up suggestions or user messages — only the assistant answer text.
- iOS (BITB-087) and voice input (BITB-120).

### Open questions

- Real-device check of Arabic/Hindi/Korean local voice coverage is a manual release step; results
  go in the PR description.

## Implementation Plan (2026-10-04)

### Problem / why
Answers are text-only. Add an on-device Listen ↔ Stop control per the Specification above, with one
shared normalization/chunking spec so web and Android cannot drift (the BITB-059 lesson).

### Shared fixture — `tests/fixtures/speakable_text.json` (+ README section)
```jsonc
{
  "description": "BITB-119 speakable-text rules: normalization + chunking, shared by web and Android",
  "maxChunkChars": 200,
  "verseTemplates": { "en": { "verse": "{book} chapter {c}, verse {v}", "range": "{book} chapter {c}, verses {v} to {e}" }, … all 11 … },
  "normalize_cases": [ { "id", "language", "input", "expected", "origin", "skip": [], "skipReason": "" } ],
  "chunk_cases":     [ { "id", "language", "input", "expected": ["chunk1", …] } ]
}
```
- `verseTemplates` = the table in FR5 (the `chapter`-only template is **dropped**: the web parser
  only matches `chapter:verse`, so chapter-only references are left as written on both clients; the
  Android parser must skip matches without a verse number for parity).
- ≥ 1 normalize case per language (11), plus: bold reference, markdown link with verse text,
  bare URL, external link, guillemet `<<…>>`/`《…》`, German comma `Römer 13,1`, numbered book
  `1 Corinthians 13:4`, range `3:16-18`/en-dash, fullwidth/parenthesized `（约翰福音3:16）`,
  RTL Arabic, Devanagari digits, heading/list/blockquote stripping, emoji untouched.
- Chunk cases: short text → 1 chunk; multi-sentence > 200 → sentence-boundary split; single
  > 200-char sentence → hard split at last space ≤ 200; CJK (no spaces) → split at `。` / at 200;
  Hindi `।`; Arabic `؟`.
- Expected strings must be produced by running the *web* implementation and then hand-checked;
  Android must reproduce them exactly.

### Backend (`api/`)
- `config.py`: `tts_enabled: bool = True`.
- `main.py` `GET /config`: add `"features": {"tts_enabled": settings.tts_enabled}`.
- `main.py`: `POST /api/v1/client-events` (`include_in_schema=False`,
  `dependencies=[Depends(require_rate_limit)]`), body model `ClientEvent(BaseModel)` with
  `model_config = ConfigDict(extra="forbid")`, `event: Literal["tts_started","tts_unavailable"]`
  (unknown → 422), `locale: str = Field(max_length=16)` normalized to a whitelist of the 11
  locales (lower-cased primary subtag) else `"other"`. Increments
  `client_tts_events_counter.add(1, {"event", "locale"})`; no logging of IP/UA; returns
  `{"status": "ok"}`.
- `utils/metrics.py`: `client_tts_events_counter` = `client.tts_events_total`.
- `scripts/env-manifest.yaml`: `TTS_ENABLED` (required_in: none, default true). `deployment/main.tf`
  + `variables.tf`: `TTS_ENABLED = tostring(var.tts_enabled)`, variable default `true`. Run
  `scripts/validate-env.py` (or the repo's equivalent) if present.
- Tests: `api/tests/test_client_events.py` (happy path both events, locale whitelist incl. `zh-CN`
  → `zh`, unknown locale → `other`, unknown event → 422, extra field → 422, counter called with
  only event+locale) and extend `test_api.py::test_config_endpoint` (default true; monkeypatched
  false).

### Web (`frontend/`)
- `src/lib/speakableText.ts` (pure): `normalizeForSpeech(markdown, locale)` and
  `chunkForSpeech(text, max=200)`, plus `VERSE_SPEECH_TEMPLATES` table. Reference detection reuses
  `createVersePatternGlobal()` + `isKnownBook()` (+ `normalizeTraditionalToSimplified` for
  matching only, same rewind-on-reject loop as `extractVerseReferences`). Digits normalized via
  `normalizeDigits`. Strip markdown with ordered regexes (links before emphasis; strip the
  `verse://` links that `linkifyVerses` would add — normalize the **raw** `message.content`, not
  linkified text).
- `src/lib/speech.ts`: module-level singleton controller over `window.speechSynthesis`:
  `isSpeechSupported()`, `findLocalVoice(locale)` (only `localService === true`; exact
  `lang` match, then primary subtag, prefer `default`), `loadVoices()` resolving on
  `voiceschanged` (with timeout), `speak(id, chunks, voice, lang)` (cancel current, queue one
  `SpeechSynthesisUtterance` per chunk, end → idle), `stop()`, `subscribe(listener)` and
  `getSpeakingId()`. SSR-safe.
- `src/lib/useSpeechAvailability.ts` hook: returns `voice | null` for the current locale,
  recomputed on `voiceschanged`; reports `tts_unavailable` once per locale per page load when flag
  and pref are on but no voice.
- `src/lib/ttsPreference.ts`: `getShowListen()/setShowListen()` in `localStorage`
  (`voxquieta.showListen`, try/catch, default true) + `useShowListenPreference()` hook using a
  `storage`/custom event so the menu and messages stay in sync.
- `src/lib/clientEvents.ts`: `reportClientEvent(event, locale)` fire-and-forget `fetch` POST,
  never throws (mirror `clientErrorReporter.ts` style).
- `src/lib/serverConfig.tsx`: add `ttsEnabled: boolean` (default `true`; only `false` when
  `config.features.tts_enabled === false`).
- `src/components/ListenButton.tsx`: props `messageId`, `content`; uses `useLocale()`,
  `useServerConfig()`, preference, availability; renders nothing unless all prerequisites hold;
  `Volume2` / `Square` (lucide) icons, `aria-pressed`, localized `aria-label`/title; on click →
  `speak` (reports `tts_started`) or `stop`; `useEffect` cleanup stops if this message is the one
  speaking (covers conversation switch, locale change, navigation).
- `ChatMessage.tsx`: render `<ListenButton>` in the assistant action row — inside
  `FeedbackControls` `trailing` alongside `ShareMenu`, and also when there is no feedback row —
  only when `!message.isStreaming` (check the actual streaming field on `Message`) and content
  is non-empty.
- `MainMenu.tsx`: a switch-style button (`role="switch"`, `aria-checked`) "Show Listen button".
- `messages/*.json` (11): `Chat.listenAnswer`, `Chat.stopListening`, `Chat.showListenButton`.
- Tests (vitest, mocked `speechSynthesis`/`SpeechSynthesisUtterance` in the test file):
  `speakableText.crossplatform.test.ts` (fixture: templates equal, normalize + chunk cases),
  `speech.test.ts` (local-only filter, cancel-before-speak, chunk order, stop),
  `ListenButton.test.tsx` (hidden: no API / remote-only voice / pref off / flag false / streaming;
  shown with local voice; click speaks + reports event; second click cancels; second message
  cancels first; unmount cancels), `serverConfig.test.tsx` (flag parsing, fail open),
  `ttsPreference.test.ts`, `clientEvents.test.ts` (payload only event+locale), MainMenu toggle test.

### Android (`android/`)
- `tts/SpeakableText.kt` (pure, `internal`): `normalizeForSpeech(markdown, language, verseRefRegex,
  localizedToEnglish)`, `chunkForSpeech(text, max = 200)`, `VERSE_SPEECH_TEMPLATES`. Uses the
  same `verseRefRegex` that `ChatScreen` already builds and passes to `ChatMessageItem`; skip
  matches without a verse number; validate book via the existing known-book check used by
  `injectVerseLinks`.
- `tts/SpeechEngine.kt`: interface (`isReady: StateFlow<Boolean>`, `hasLocalVoice(locale)`,
  `speak(id, chunks, locale)`, `stop()`, `speakingId: StateFlow<String?>`) +
  `AndroidSpeechEngine` (`TextToSpeech` created lazily with app context; `OnInitListener`;
  local voice = `voices.any { !it.isNetworkConnectionRequired && it.locale.language == lang &&
  NOT_INSTALLED feature absent }` and `isLanguageAvailable(locale) >= LANG_AVAILABLE`; sets that
  voice; `QUEUE_FLUSH` then `QUEUE_ADD` per chunk with utterance ids; `UtteranceProgressListener`
  clears `speakingId` after the last chunk or on error; audio focus via `AudioFocusRequest`
  (API 26+) `AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK`, `AudioAttributes(USAGE_ASSISTANT,
  CONTENT_TYPE_SPEECH)`; on focus loss → `stop()`; abandon on stop/done).
- `di/SpeechModule.kt`: `@Binds`/`@Provides @Singleton SpeechEngine`.
- `data/preferences/TtsPreferences.kt`: DataStore boolean `show_listen_button` default true
  (pattern of `ThemePreferences`).
- `ConfigResponseDto.kt`: `features: ConfigFeaturesDto? = null` with
  `@SerialName("tts_enabled") ttsEnabled: Boolean? = null`.
- `ChatViewModel.kt`: inject `SpeechEngine`, `TtsPreferences`; `ChatUiState` gains
  `ttsServerEnabled = true`, `showListenButton = true`, `speakingMessageId: String?`;
  `fetchConfigWithRetry` sets `ttsServerEnabled = response.features?.ttsEnabled != false`;
  `toggleSpeak(message, language, regex, map)`, `stopSpeaking()`, `setShowListenButton()`;
  `canSpeak(language)`; logs `EVENT_TTS_STARTED` / `EVENT_TTS_UNAVAILABLE` (once per language per
  ViewModel) with `PARAM_LOCALE`; stops speaking on new conversation / conversation switch /
  `onCleared`.
- `AnalyticsHelper.kt`: `EVENT_TTS_STARTED = "tts_started"`, `EVENT_TTS_UNAVAILABLE =
  "tts_unavailable"`, `PARAM_LOCALE` (reuse if one already exists).
- `ChatMessageItem.kt`: new params `showListen: Boolean = false`, `isSpeaking: Boolean = false`,
  `onToggleListen: (() -> Unit)? = null`; IconButton (`Icons.AutoMirrored.Filled.VolumeUp` /
  `Icons.Default.Stop`) at the start of `trailingActions` when `showShare && showListen`;
  `contentDescription` Listen/Stop + `semantics { stateDescription }`.
- `ChatScreen.kt`: compute `showListen` from uiState + `canSpeak(language)`; pass `isSpeaking =
  uiState.speakingMessageId == message.id`; `DisposableEffect` on lifecycle `ON_STOP` →
  `viewModel.stopSpeaking()`, and on dispose.
- `SettingsScreen.kt`: new "Read aloud" section with a `Switch` row bound to
  `uiState.showListenButton`.
- Strings in `values/strings.xml` + all 10 `values-<locale>/strings.xml`: `action_listen`,
  `action_stop_listening`, `settings_tts_title`, `settings_tts_show_listen`,
  `settings_tts_show_listen_desc`.
- Tests: `tts/SpeakableTextParityTest.kt` (fixture via existing test resources srcDir — templates
  equal, normalize + chunk cases), `ChatViewModelTest` additions with a `FakeSpeechEngine`
  (flag parsing incl. absent → enabled, toggle/stop/one-at-a-time, conversation switch stops,
  telemetry params), `TtsPreferencesTest` if a DataStore test pattern exists, and a
  `ListenButtonComposeTest.kt` in the Compose tier (hidden/visible, content description flips,
  click callback).

### Backlog / commit
- `docs/BACKLOG.md` entry → 🚧 In Progress (→ ✅ Done with PR number once merged), `Last Updated`.
- Single commit type `feat:` (user-visible) so release-please puts it in CHANGELOG → both What's
  New surfaces (which are generated from CHANGELOG, not hand-edited).

### Verification
- `cd api && python -m pytest tests/ -x -q` (+ ruff, black, mypy on touched files)
- `cd frontend && npx vitest run && npm run lint && npx tsc --noEmit && npm run build`
- `cd android && ./gradlew testDebugUnitTest testDebugCompose lint` — likely unavailable in the
  sandbox (AGP fetch); if so, say so and gate on PR CI (`android-ci.yml`,
  `android-compose-tests.yml`).
- Manual (PR description): real-device check matrix for ar/hi/ko voices; offline test.

## Why This Exists

Today every answer is text-only on both clients:

- Web renders it as markdown in `frontend/src/components/ChatMessage.tsx`, streamed chunk by chunk
  through `streamMessage()` (`frontend/src/lib/api.ts:608`).
- Android renders it in `presentation/components/ChatMessageItem.kt`, same streaming shape via
  `data/streaming/EventSourceParser.kt`.

Both already carry a per-message action row on assistant messages (copy at
`ChatMessage.tsx:242`, copy/share/retry at `ChatMessageItem.kt:726-785`), so there is a natural,
already-designed place for a **Listen** control — no new layout, no new screen.

Note what this is *not*: screen readers (TalkBack, VoiceOver, NVDA) already read the message to
users who run them. This story serves a different need — hands-free, eyes-free listening by users
who are not running a screen reader — and it should not be justified or scoped as an accessibility
fix.

## The Decision That Has to Come First: On-Device vs Cloud

This is the whole cost question, and it is a **product decision, not a technical one** — the two
options differ by no metered vendor charge vs a metered service, and by a small vs a heavy legal
footprint.

### Option 1 — Platform speech synthesis, on the device (recommended for v1)

| | Web | Android |
|---|---|---|
| API | `window.speechSynthesis` (Web Speech API) | `android.speech.tts.TextToSpeech` (platform) |
| New dependency | none | none |
| New permission | none | none |
| Backend change | Remote flag in `GET /config` only; no speech endpoint | Same |
| Runtime cost | **€0** | **€0** |
| Local-only eligibility | `SpeechSynthesisVoice.localService === true` | `!Voice.isNetworkConnectionRequired` |

**What it costs us instead:** voice quality and coverage are the *user's* device's problem, and it
varies a lot across our eleven locales (`frontend/messages/`: ar, de, en, es, fr, hi, it, ko, pt,
ru, zh). macOS/iOS and modern Android have good voices for the big languages; Windows is adequate;
desktop Linux browsers frequently have **no** voice installed at all; Arabic, Hindi and Korean
coverage is the least predictable. The v1 privacy boundary is **local synthesis only**: web may
select only a `SpeechSynthesisVoice` whose `localService` is `true`, and Android may select only an
installed `Voice` whose `isNetworkConnectionRequired` is `false`. Unknown, remote or
network-required voices are ineligible, even if they sound better. The feature must therefore be
feature-detected and hidden per locale rather than shown-and-broken; offline behavior is verified
with networking disabled, not inferred from engine installation.

Known sharp edges to budget for, not discover later:

- Chrome cuts `speechSynthesis` off after ~15 s unless the utterance is chunked or kept alive.
- iOS Safari requires a direct user gesture to start speech; autoplay-on-arrival will not work.
- Android `TextToSpeech.speak()` caps an utterance (~4 000 chars) — chunk by sentence.
- Android may need `ACTION_INSTALL_TTS_DATA` when the locale's voice data is missing; handle the
  "engine present, language absent" state explicitly.
- Audio focus (Android) and one-utterance-at-a-time (both) — pressing Listen on a second message
  must stop the first, and navigating away must stop playback.

### Option 2 — Cloud neural TTS through our backend

A new endpoint (`POST /chat/speech`) synthesising audio server-side, protected like the other write
paths (`require_turnstile`, `require_rate_limit`), with a content-hash cache so the same answer is
never billed twice.

Answer length is bounded by `llm_max_tokens = 1024` (`api/config.py:25`) — worst case ~3–4 k
characters, typically far less. A cloud follow-up must attach dated vendor pricing sources and a
cost model based on measured production answer length and listen rate; this story does not assert an
unsupported unit price. The multiplier that actually decides the bill is the *listen rate*, which
we cannot know until Option 1 ships and is instrumented.

The per-character price is not the expensive part. The expensive parts are:

- a second vendor contract, key rotation, and an outage surface the chat path does not have today;
- a cache (blob or DB) keyed by content hash, or we pay repeatedly for identical answers;
- an endpoint that, if it accepts arbitrary text, **is a free TTS API for anyone who finds it** — it
  must be bound to a `message_id` the backend itself produced, not to client-supplied text;
- audio egress and storage lifecycle;
- +1–2 s latency before playback unless synthesis is streamed.

### Recommendation

**Ship Option 1 behind a remotely controlled flag; treat Option 2 as a separate, later story
justified by measured demand.** Add a non-sensitive TTS flag to backend settings and `GET /config`,
then consume it in the web config path and Android `ConfigResponseDto`; this is a backend config
change, but not an audio endpoint. Fail closed when config is missing or unavailable. Option 1 is
the only version whose runtime cost is genuinely zero and whose enforced privacy boundary is
"nothing left your device". If listen-rate telemetry and user feedback later show that local voices
are the limiting factor in a specific locale, that is the evidence for a separately reviewed cloud
story.

## Cost of Implementation

| Piece | Where | Size |
|---|---|---|
| Speakable-text normalization (markdown → spoken words) | shared spec + per-client impl | M |
| Web: Listen control, playback state, voice/locale selection, chunking | `ChatMessage.tsx`, `ChatIsland.tsx` | M |
| Android: `TextToSpeech` lifecycle (DI singleton), audio focus, missing-language handling, Compose state | `ChatMessageItem.kt`, `ChatViewModel.kt`, new `tts/` package | M |
| Remote rollout flag: backend setting + `GET /config`, web consumer, Android DTO/state | `api/config.py`, `api/main.py`, both clients, deployment env | S |
| i18n strings × 11 locales × 2 platforms | `frontend/messages/*.json`, `android/app/src/main/res/values*/` | S |
| Tests: vitest with a mocked `speechSynthesis` (jsdom has none), Android Compose + fake TTS engine | both | M |
| Changelog / What's New entry | `WhatsNewModal.tsx`, Android `WhatsNewBottomSheet.kt` | S |

**The normalization layer is the part that is easy to underestimate.** The raw message is markdown
containing verse references, quoted scripture, and link syntax. Spoken naively, `**John 3:16**`
becomes "asterisk asterisk John three colon sixteen". It needs a rule set — strip markdown, expand
`John 3:16` to a natural spoken form *in the message's language*, drop URLs — and that rule set will
exist in TypeScript **and** Kotlin (**and** Swift, once BITB-087 lands).

This repo has already been bitten by exactly that shape of duplication: the verse-parsing regex
lives in three languages and has generated BITB-059, BITB-108, BITB-113 and BITB-114. Do not create
a second such family. Specify the normalization once, put its cases in the shared cross-platform
fixture corpus (`tests/fixtures/`), and assert both clients against it.

## Cost of the Run-Time Process

What ongoing cost this adds *after* it ships, assuming Option 1:

- **Money:** €0 per request. No backend call, no vendor, no egress.
- **Backend load:** negligible config reads. `api/` changes only to publish the remote flag; message
  text and audio never enter the backend.
- **Support surface:** the failure modes are entirely client-side and therefore invisible in our
  existing telemetry unless we add events. Android has `AnalyticsHelper` (`EVENT_*` constants) —
  add `tts_started` / `tts_unavailable` with a locale parameter. The web has no product analytics
  (only `clientErrorReporter.ts`), so **web listen-rate will be unmeasurable without new work** —
  decide deliberately whether that matters before shipping, because it is the same number that
  would later justify Option 2.
- **Release testing:** a per-release manual pass on real devices across locales, because emulators
  and CI cannot tell us whether a Hindi voice exists on a real phone. This is a recurring cost of
  the feature, not a one-off.
- **Legal:** Option 1 requires **no** privacy-policy change on web because only `localService` voices
  qualify. Android similarly rejects voices that report a network requirement; disclose that an
  installed OS TTS engine processes text locally and verify the claim offline. Option 2 would
  require a policy update in eleven locales (`frontend/public/legal/privacy-policy.*.md`) plus a
  Play Data Safety review — count that as part of Option 2's price, not this story's.
- **Future platforms:** BITB-087 (iOS) inherits this scope — `AVSpeechSynthesizer` plus the same
  normalization rules. Cheap if the rules are specified once; a third rewrite if they are not.

## Original Acceptance Criteria (2026-09-04 — superseded by the Specification above)

- [ ] A **Listen** control appears in the existing assistant-message action row on both web and
      Android — no new screen, no layout redesign
- [ ] Playback uses the platform synthesizer only; **no audio and no message text is sent to any
      Vox Quieta backend or third-party API** by this story
- [ ] Local-only policy is enforced, not assumed: web accepts only voices with
      `localService === true`; Android accepts only voices where
      `isNetworkConnectionRequired == false`; offline tests prove playback or hide the control
- [ ] The control is **hidden** (not shown-and-broken) when no voice exists for the message's
      language; Android additionally handles "engine present, language data missing"
- [ ] Speaking a message stops any message already speaking; leaving the screen / navigating away
      stops playback
- [ ] Playback can be paused/stopped by the user from the same control
- [ ] Long answers are chunked so neither the Chrome ~15 s cutoff nor the Android per-utterance cap
      truncates the reading
- [ ] Markdown, link syntax and verse references are normalized to speakable text by a rule set
      specified **once**, with cases in the shared fixture corpus and both clients asserted against
      it
- [ ] Android requests audio focus and behaves correctly when another app takes it
- [ ] UI strings translated in all eleven locales on both platforms
- [ ] Telemetry: Android logs listen-started / voice-unavailable (with locale); the web's
      measurability gap is either closed or explicitly accepted in this story's PR description
- [ ] Tests: web unit tests against a mocked `speechSynthesis` (jsdom provides none); Android tests
      against a fake TTS engine, in the existing Compose test tier
- [ ] Remotely feature flagged through backend settings and `GET /config`, with web and Android
      config consumers and deployment configuration covered; missing/failed config keeps it off
- [ ] Changelog + What's New entries on both platforms

## Risks

- **Voice quality is not ours to control.** A poor local voice reads as *our* product being bad. The
  remote feature flag and per-locale hide rule are the mitigations; be prepared to disable it.
- **Silent divergence between clients** if normalization is re-implemented per platform — the
  BITB-059 family of stories is what that looks like a year later.
- **Scope creep toward cloud TTS mid-implementation.** If device voices disappoint during
  development, the temptation will be to "just add an endpoint". That is Option 2, with a vendor, a
  cache, an abuse surface, and eleven privacy-policy translations. It is a separate story.

## Verification

The headline demo is one tap on a real phone with the app in the foreground (v1 stops on screen-off / background by design — FR4; background playback is BITB-176). The criteria that actually
protect users are the unglamorous ones: that the control is *absent* where no voice exists, that a
second tap doesn't produce two overlapping voices, and that navigating away leaves silence rather
than a disembodied reading. Test those on hardware, not in an emulator.

## Related

- **BITB-120** — voice input (the other half of the request); shares rollout and locale concerns but
  has an independent permission, data flow and release risk
- **BITB-087** — iOS chat parity; inherits the normalization rules
- **BITB-059 / BITB-108 / BITB-113 / BITB-114** — the verse-parser duplication family; the precedent
  for specifying shared text rules once
- Icebox: *Audio Bible Integration (read-along audio for verses)* — adjacent but distinct; that is
  recorded scripture audio, this is synthesized speech of our own answers
- `frontend/src/components/ChatMessage.tsx`, `frontend/src/app/[locale]/ChatIsland.tsx`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt`
