# BITB-120: Ask by Voice — Speak the Question Instead of Typing It (Web + Android)

**Status:** 🎯 Todo
**Priority:** P2 — new capability; heavier legal and store footprint than BITB-119, so sequence it
after that one even though the two were requested together
**Size:** L (M on web, M–L on Android because of the runtime permission and Play Data Safety work)
**Created:** 2026-09-04
**Prompted by:** product request — "input the user question via voice". The other half, speaking the
answer, is BITB-119. The stories share remote rollout/configuration and locale work but remain split
because microphone input has an independent permission, third-party audio data flow, store/legal
review and failure surface; either capability can ship without the other.

## User Story

**As** someone who finds it hard, slow or impossible to type what they are struggling with — on a
phone, one-handed, in a language whose keyboard they fight with, or simply because saying it out
loud is easier than writing it — **I want** to speak my question and see it appear in the input
field, **so that** the barrier between what I feel and what I can ask is as low as possible.

## Why This Exists

Both clients accept typed input only:

- Web: the textarea in `frontend/src/app/[locale]/ChatIsland.tsx:1186`, capped at
  `max_message_length = 500` (`api/config.py:180`).
- Android: `presentation/components/ChatInputField.kt`, same cap enforced client-side.

The people this product is for are often reaching for it at a bad moment. Typing a paragraph about
grief or fear on a phone keyboard is friction at exactly the wrong time.

### The zero-cost baseline, stated honestly

On Android, **the platform keyboard already offers dictation** (the Gboard microphone). Users can
speak their question today, with no work from us. The gap is discoverability, not capability. That
matters for prioritisation: this story buys a visible, in-app affordance and control over the
recognition language — not a new ability. On web there is no such fallback, so the gap is real
there.

## The Decision That Has to Come First: Platform Recognizer vs Our Backend

### Option 1 — Platform speech recognition (recommended for v1)

| | Web | Android |
|---|---|---|
| API | `SpeechRecognition` / `webkitSpeechRecognition` | `android.speech.SpeechRecognizer` |
| Browser/OS support | Chrome, Edge, Safari (incl. iOS 14.5+) — **not Firefox** | all, but see below |
| New permission | mic prompt (browser-managed), HTTPS required | **`RECORD_AUDIO`** runtime permission — new to `AndroidManifest.xml` |
| New dependency | none | none |
| Backend change | Remote flag in `GET /config` only; no transcription endpoint | Same |
| Runtime cost | **€0** | **€0** |

**"On-device" is not accurate, and the story must not claim it is.** Chrome's implementation streams
audio to Google's servers. On Android, `SpeechRecognizer` likewise uses the device's speech service
(Google on most devices) over the network; a genuinely on-device path exists only from **API 31**
(`createOnDeviceSpeechRecognizer`), while our `minSdk = 26` means devices on API 26–30 fall back to
the networked recognizer. So on both platforms the user's voice reaches a third party — just not
*us*. That is a disclosure obligation, and it is the single most important fact in this story.

Android must implement a capability ladder rather than treating API level as capability:

1. On API 31+, if `SpeechRecognizer.isOnDeviceRecognitionAvailable(context)` is true, use
   `createOnDeviceSpeechRecognizer(context)`.
2. Otherwise, if `SpeechRecognizer.isRecognitionAvailable(context)` is true, use the platform
   recognition service and clearly disclose that it may require a network connection and send audio
   to the service provider.
3. Otherwise, hide the in-app microphone and leave typed input and keyboard dictation available.

On Android 11+ the availability checks are also subject to package visibility. Add a `<queries>`
intent for `android.speech.RecognitionService` to `AndroidManifest.xml`; without it an installed
recognizer can be reported unavailable. Test all three ladder branches, including an API 31+ device
where on-device recognition is unavailable but a network service exists.

### Option 2 — Cloud STT through our backend (`POST /chat/transcribe`)

A cloud follow-up must attach dated vendor pricing sources and model measured question duration and
usage; this story intentionally makes no unsupported unit-price claim. The plumbing and legal
exposure, rather than an undated estimate, drive the decision:

- multipart audio upload with a hard duration and size cap (a transcription endpoint without one is
  a denial-of-wallet target), plus Turnstile and rate limiting like every other write path;
- audio buffered through our API containers — memory, timeouts and a failure mode the current
  JSON-only request path does not have;
- +1–3 s of latency *before* the chat request even starts;
- **voice recordings transiting our infrastructure.** Under GDPR this is a materially different
  posture from text: a privacy-policy rewrite in eleven locales, an explicit no-retention guarantee
  we must actually implement and be able to demonstrate, a processor agreement with the vendor, and
  a Play Data Safety declaration that says we collect audio. Self-hosting Whisper instead of using a
  vendor swaps the legal cost for a GPU/CPU cost the current small API containers cannot absorb.

Content safety is *not* a differentiator between the options: `check_content_filter` runs on the
text either way, since the transcript is what reaches `POST /chat`.

### Recommendation

**Ship Option 1 behind a remotely controlled flag on both platforms, with an explicit disclosure of
who performs recognition; do not build Option 2 unless measured accuracy complaints demand it.**
Add a non-sensitive speech-input flag to backend settings and `GET /config`, consume it in the web
config path and Android `ConfigResponseDto`, and fail closed when config is unavailable. This is a
backend configuration change, not a transcription endpoint. Option 2's primary cost is owning
users' voice recordings.

## Cost of Implementation

| Piece | Where | Size |
|---|---|---|
| Android: `RECORD_AUDIO` runtime permission flow — rationale, denied, permanently-denied, settings deep link | new; `MainActivity.kt` / Compose permission handling | M |
| Android: `SpeechRecognizer` lifecycle, partial results, cancel, error mapping (no-match, network, busy, insufficient permissions) | new `speech/` package + `ChatViewModel.kt` | M |
| Android capability discovery + package visibility | `AndroidManifest.xml`, recognizer wrapper | S |
| Android: mic button + listening state in the input field | `ChatInputField.kt` | S |
| Web: feature detection, mic button, interim results into the textarea, abort on send, unsupported-browser path (Firefox) | `ChatIsland.tsx` | M |
| Remote rollout flag: backend setting + `GET /config`, web consumer, Android DTO/state | `api/config.py`, `api/main.py`, both clients, deployment env | S |
| Enforce the 500-char cap against dictated text on both clients | both | S |
| Privacy-policy paragraph × 11 locales; Play Data Safety + permission declaration | `frontend/public/legal/privacy-policy.*.md`, Play Console | M |
| i18n strings × 11 locales × 2 platforms | `frontend/messages/*.json`, Android `values*/` | S |
| Tests: vitest with a mocked `SpeechRecognition`; Android tests with a fake recognizer, in the existing Compose tier | both | M |
| Changelog / What's New | both | S |

Recognition language must come from the **app's selected locale** (`selectedLanguage` in
`ChatViewModel`, the next-intl locale on web), not from the browser or system default — otherwise an
Italian user with an English phone dictates gibberish.

## Cost of the Run-Time Process

Assuming Option 1:

- **Money:** €0 per request. No backend call, no vendor invoice.
- **Backend load:** negligible config reads. `api/` changes only to publish the remote flag; audio is
  never uploaded. The existing session limit (BITB-024) and rate limits are unaffected — a spoken
  question is just a `POST /chat` like any other.
- **Store and release process — this is the real recurring cost.** Adding `RECORD_AUDIO` to the
  manifest changes the app's permission profile: the Play listing shows a microphone permission,
  Data Safety must be updated, and permission-adding releases attract additional review. Budget for
  a slower first release after this ships, and for the fact that **a permission can be added easily
  and removed only awkwardly** — users who see a mic permission on a Bible app will draw
  conclusions. The in-app rationale text matters as much as the code.
- **Legal:** a privacy-policy update is required even under Option 1, because the recognizer is a
  third party. Eleven locales, two surfaces (web markdown docs, Android legal URLs). This is
  unavoidable, not optional, and it is the item most likely to be forgotten until review.
- **Support surface:** microphone failures are famously environment-dependent (denied permission,
  no network for the recognizer, a device with a broken speech service, dialects). Instrument
  Android via `AnalyticsHelper` (`voice_input_started` / `voice_input_failed` with a reason and
  locale). The web has no product analytics today — accept the blind spot deliberately or close it.
- **Release testing:** a real-device pass per release across locales, plus a Firefox check on web
  that the button is simply absent rather than present-and-dead.
- **Future platforms:** BITB-087 (iOS) inherits `SFSpeechRecognizer`, `NSMicrophoneUsageDescription`
  and `NSSpeechRecognitionUsageDescription` — and Apple's review reads usage strings closely.

## Acceptance Criteria

- [ ] A microphone control appears next to the chat input on both platforms, and is **hidden** where
      recognition is unsupported (notably Firefox on web) rather than shown and inert
- [ ] Recognition uses the platform recognizer only; **no audio is uploaded to any Vox Quieta
      backend** by this story
- [ ] Android manifest declares a package-visibility `<queries>` intent for
      `android.speech.RecognitionService`, and availability detection is tested on Android 11+
- [ ] Android follows the capability ladder: API 31+ on-device recognizer when actually available;
      otherwise an available platform service with network/vendor disclosure; otherwise no control
- [ ] Recognition language follows the app's selected locale, not the system/browser default
- [ ] Interim results appear in the input field as the user speaks; the user can stop, edit and
      review before sending — dictation never auto-sends
- [ ] Dictated text is subject to the same 500-character cap as typed text
- [ ] Android: `RECORD_AUDIO` requested with an in-context rationale; denied and
      permanently-denied states both handled without a dead-end (settings deep link), and the app
      remains fully usable when the permission is refused
- [ ] Errors (no match, no network, recognizer busy, permission missing) map to distinct,
      translated user-facing messages — not a generic failure
- [ ] Privacy policy updated in all eleven locales, naming that speech recognition is performed by
      the browser/device vendor and that Vox Quieta does not receive or store audio; Play Data
      Safety updated to match
- [ ] UI strings translated in all eleven locales on both platforms
- [ ] Telemetry: Android logs start/failure with reason and locale; the web gap is closed or
      explicitly accepted in the PR description
- [ ] Tests: web unit tests against a mocked `SpeechRecognition`, including the unsupported-browser
      path; Android tests against a fake recognizer covering granted, denied and error paths
- [ ] Remotely feature flagged through backend settings and `GET /config`, with web and Android
      config consumers and deployment configuration covered; missing/failed config keeps it off
- [ ] Changelog + What's New entries on both platforms

## Risks

- **Trust.** A microphone permission on an app people bring their grief to is a bigger ask than the
  code suggests. The mitigation is disclosure that is honest and easy to find — including the part
  where the recognizer is Google's, not ours — plus never listening outside an explicit tap.
- **Accuracy across eleven locales.** Recognition quality for Arabic dialects and Hindi will be
  noticeably worse than for English. Transcripts also arrive without punctuation, which slightly
  degrades the question the LLM sees. Neither is fixable by us under Option 1; both are arguments
  people will use to push toward Option 2.
- **The permission is hard to walk back** once shipped.
- **Scope creep toward Option 2** mid-implementation, which would land voice recordings on our
  infrastructure without the legal work having been done deliberately. Separate story, separate
  decision.

## Dependencies

No implementation dependency on BITB-119. Sequence after it because read-aloud can validate demand
without microphone permission or third-party audio transfer, not because the stories share no code
or operational concerns.

## Verification

The criterion that matters most is not "it transcribes well" — it is what happens when the user says
no. Deny the permission and confirm the app is still whole; deny it permanently and confirm there is
a way forward rather than a dead button. Then open Firefox and confirm the control is simply not
there. Accuracy is the demo; the refusal paths are the product.

## Related

- **BITB-119** — speak the answer; shares rollout and locale concerns but has an independent API,
  permission/data posture and release path
- **BITB-087** — iOS chat parity; inherits the recognizer and its usage strings
- **BITB-024** — session interaction limit; unaffected, a spoken question is an ordinary message
- `frontend/src/app/[locale]/ChatIsland.tsx`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatInputField.kt`,
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt`,
  `android/app/src/main/AndroidManifest.xml`, `frontend/public/legal/privacy-policy.*.md`
