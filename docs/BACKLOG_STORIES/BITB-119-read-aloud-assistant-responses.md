# BITB-119: Read the Answer Aloud — Speak Vox Quieta's Response (Web + Android)

**Status:** 🎯 Todo
**Priority:** P2 — new capability, not a defect; sequence after the cost decision below is made
**Size:** L (M per platform + a shared text-normalization layer; see Cost of Implementation)
**Created:** 2026-09-04
**Prompted by:** product request — "speak loudly the Vox Quieta response". Paired with BITB-120
(voice input); the two are deliberately separate stories because they share no code, no vendor
decision, and no legal footprint.

## User Story

**As** someone who came to Vox Quieta while driving, cooking, praying with eyes closed, or simply
tired of reading a screen, **I want** to press a button and hear the answer spoken, **so that** the
response reaches me the way a quiet voice would — without me having to read it.

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
options differ by ~0 vs ~real money, and by a small vs a heavy legal footprint.

### Option 1 — Platform speech synthesis, on the device (recommended for v1)

| | Web | Android |
|---|---|---|
| API | `window.speechSynthesis` (Web Speech API) | `android.speech.tts.TextToSpeech` (platform) |
| New dependency | none | none |
| New permission | none | none |
| Backend change | none | none |
| Runtime cost | **€0** | **€0** |
| Works offline | depends on OS voice | yes, once language data is installed |

**What it costs us instead:** voice quality and coverage are the *user's* device's problem, and it
varies a lot across our eleven locales (`frontend/messages/`: ar, de, en, es, fr, hi, it, ko, pt,
ru, zh). macOS/iOS and modern Android have good voices for the big languages; Windows is adequate;
desktop Linux browsers frequently have **no** voice installed at all; Arabic, Hindi and Korean
coverage is the least predictable. The feature must therefore be **feature-detected and hidden**,
per locale, rather than shown-and-broken.

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

Indicative list prices (**verify before committing — these move, and this is a pre-implementation
estimate, not a quote**):

| Vendor | Unit price | Per answer (≈1 000 chars) | Per 1 000 answers listened |
|---|---|---|---|
| Azure AI Speech, neural | ~$15–16 / 1M chars | ~$0.016 | ~$16 |
| Google Cloud TTS, Neural2 | ~$16 / 1M chars | ~$0.016 | ~$16 |
| Google Cloud TTS, Standard | ~$4 / 1M chars | ~$0.004 | ~$4 |
| OpenAI `tts-1` | ~$15 / 1M chars | ~$0.015 | ~$15 |
| ElevenLabs | ~$0.15–0.30 / 1k chars | ~$0.15–0.30 | ~$150–300 |

Answer length is bounded by `llm_max_tokens = 1024` (`api/config.py:25`) — worst case ~3–4 k
characters, typically far less. **Measure the real distribution from production before adopting any
of these numbers**; the multiplier that actually decides the bill is the *listen rate*, which we
cannot know until Option 1 ships and is instrumented.

The per-character price is not the expensive part. The expensive parts are:

- a second vendor contract, key rotation, and an outage surface the chat path does not have today;
- a cache (blob or DB) keyed by content hash, or we pay repeatedly for identical answers;
- an endpoint that, if it accepts arbitrary text, **is a free TTS API for anyone who finds it** — it
  must be bound to a `message_id` the backend itself produced, not to client-supplied text;
- audio egress and storage lifecycle;
- +1–2 s latency before playback unless synthesis is streamed.

### Recommendation

**Ship Option 1 behind a flag; treat Option 2 as a separate, later story justified by measured
demand.** Option 1 is the only version whose runtime cost is genuinely zero and whose privacy story
is "nothing left your device". If listen-rate telemetry and user feedback later show that device
voices are the limiting factor in a specific locale (Arabic and Hindi are the likely candidates),
that is the evidence that buys Option 2 — for those locales only.

## Cost of Implementation

| Piece | Where | Size |
|---|---|---|
| Speakable-text normalization (markdown → spoken words) | shared spec + per-client impl | M |
| Web: Listen control, playback state, voice/locale selection, chunking | `ChatMessage.tsx`, `ChatIsland.tsx` | M |
| Android: `TextToSpeech` lifecycle (DI singleton), audio focus, missing-language handling, Compose state | `ChatMessageItem.kt`, `ChatViewModel.kt`, new `tts/` package | M |
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
- **Backend load:** none. This story does not touch `api/`.
- **Support surface:** the failure modes are entirely client-side and therefore invisible in our
  existing telemetry unless we add events. Android has `AnalyticsHelper` (`EVENT_*` constants) —
  add `tts_started` / `tts_unavailable` with a locale parameter. The web has no product analytics
  (only `clientErrorReporter.ts`), so **web listen-rate will be unmeasurable without new work** —
  decide deliberately whether that matters before shipping, because it is the same number that
  would later justify Option 2.
- **Release testing:** a per-release manual pass on real devices across locales, because emulators
  and CI cannot tell us whether a Hindi voice exists on a real phone. This is a recurring cost of
  the feature, not a one-off.
- **Legal:** Option 1 requires **no** privacy-policy change on web (nothing leaves the browser).
  Android is a nuance, not a non-issue: the text is handed to the device's TTS engine, which is a
  third party (Google/Samsung). A one-line disclosure is prudent. Option 2 would require a policy
  update in eleven locales (`frontend/public/legal/privacy-policy.*.md`) plus a Play Data Safety
  review — count that as part of Option 2's price, not this story's.
- **Future platforms:** BITB-087 (iOS) inherits this scope — `AVSpeechSynthesizer` plus the same
  normalization rules. Cheap if the rules are specified once; a third rewrite if they are not.

## Acceptance Criteria

- [ ] A **Listen** control appears in the existing assistant-message action row on both web and
      Android — no new screen, no layout redesign
- [ ] Playback uses the platform synthesizer only; **no audio and no message text is sent to any
      Vox Quieta backend or third-party API** by this story
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
- [ ] Feature flagged, so it can be disabled without a rollback if device-voice quality proves
      embarrassing in some locale
- [ ] Changelog + What's New entries on both platforms

## Risks

- **Voice quality is not ours to control.** A bad Hindi voice reads as *our* product being bad. The
  feature flag and the per-locale hide rule are the mitigations; be prepared to disable a locale.
- **Silent divergence between clients** if normalization is re-implemented per platform — the
  BITB-059 family of stories is what that looks like a year later.
- **Scope creep toward cloud TTS mid-implementation.** If device voices disappoint during
  development, the temptation will be to "just add an endpoint". That is Option 2, with a vendor, a
  cache, an abuse surface, and eleven privacy-policy translations. It is a separate story.

## Verification

The headline demo is one tap on a real phone with the display off. The criteria that actually
protect users are the unglamorous ones: that the control is *absent* where no voice exists, that a
second tap doesn't produce two overlapping voices, and that navigating away leaves silence rather
than a disembodied reading. Test those on hardware, not in an emulator.

## Related

- **BITB-120** — voice input (the other half of the request); separate vendor, permission and legal
  footprint, deliberately not merged with this
- **BITB-087** — iOS chat parity; inherits the normalization rules
- **BITB-059 / BITB-108 / BITB-113 / BITB-114** — the verse-parser duplication family; the precedent
  for specifying shared text rules once
- Icebox: *Audio Bible Integration (read-along audio for verses)* — adjacent but distinct; that is
  recorded scripture audio, this is synthesized speech of our own answers
- `frontend/src/components/ChatMessage.tsx`, `frontend/src/app/[locale]/ChatIsland.tsx`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt`
