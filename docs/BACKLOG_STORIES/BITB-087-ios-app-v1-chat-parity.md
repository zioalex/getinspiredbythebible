# BITB-087: iOS App v1 — SwiftUI Chat Parity, TestFlight-Ready

**Status:** 🎯 Todo (blocked on BITB-085; BITB-086 is a hard prerequisite)
**Priority:** P3
**Size:** XL (2+ weeks; re-estimate after BITB-085 picks the approach)
**Created:** 2026-07-29
**Part of:** the iOS delivery plan — Stage 3 of BITB-084 → BITB-085 → BITB-086 → **BITB-087** → BITB-088.

## User Story

**As an** iPhone user, **I want** a Vox Quieta app that opens, lets me ask a question, streams a
Scripture-grounded answer with tappable verse references, remembers my conversations, and speaks my
language, **so that** I get the same companion Android users already have.

## Definition of Done for "v1"

**v1 ends at a TestFlight build that a real person can use for a week without hitting a wall.**
It is not the App Store submission (BITB-088) and it is not full Android feature parity. Scope is
split into two tiers deliberately, because "same features as Android"
(`docs/ROADMAP.md:219`) is 21k lines of Kotlin across 144 files and is not a first release.

### Tier 1 — in v1 (the vertical slice that makes the app worth opening)

| Capability | Android reference |
|---|---|
| Streaming chat over SSE | `data/streaming/EventSourceParser.kt`, `ChatRepositoryImpl.kt` |
| Turnstile token attachment + 403 retry | `interceptors/TurnstileInterceptor.kt`, `security/TurnstileManager.kt`, `components/TurnstileWebView.kt` |
| Tappable verse citations → verse detail | `components/VerseChip.kt`, `VerseDetailBottomSheet.kt`, `InlineVerseCard.kt` |
| Verse panel (semantic + cited) | `components/VersesPanel.kt` |
| Chapter reading view | `GET /api/v1/scripture/chapter/{book}/{chapter}` |
| Translation picker | `components/TranslationPickerBottomSheet.kt`, `data/preferences/TranslationPreferences.kt` |
| UI language picker (11 locales) | `components/LanguagePickerBottomSheet.kt`, `utils/LocaleApplier.kt` |
| Conversation history, offline-readable | `data/local/*` (Room), `ConversationsScreen.kt` |
| Session message limit + friendly "take a break" | `data/preferences/SessionPreferences.kt`, BITB-023 |
| Thumbs up/down feedback | `components/FeedbackControls.kt`, `POST /api/v1/feedback` |
| Light/dark theme | `data/preferences/ThemePreferences.kt`, `presentation/theme/` |
| Settings with Privacy / Terms / About links | `SettingsScreen.kt`, `utils/LegalUrls.kt` |
| Offline/no-network handling | `utils/NetworkMonitor.kt` |
| Splash | `SplashScreen.kt` |

### Tier 2 — explicitly deferred to a follow-up story after v1 is on TestFlight

Church finder (`ChurchFinderBottomSheet.kt`, `POST /api/v1/church/search`), contact form
(`ContactFormBottomSheet.kt`), in-app changelog (`ChangelogScreen.kt`), What's New sheet
(`WhatsNewBottomSheet.kt`), About intro sheet (`AboutIntroBottomSheet.kt`, itself BITB-082 on
Android), language-mismatch switch banner (`LanguageSwitchBanner.kt`), diagnostic report
(`DiagnosticReportBottomSheet.kt`, `utils/LogCollector.kt`), suggested follow-ups (BITB-080).

**File that follow-up story when v1 lands, not now** — its scope depends on what v1 teaches.

## Architecture

Mirror the Android layering rather than inventing a new one; the port is then mechanical and
reviewable, and every question of "how should this behave?" has a Kotlin answer to read.

```text
VoxQuieta/
  Domain/        Message, Conversation, Verse, ChatRequest/Response   ← mirrors domain/models/
  Data/
    Remote/      APIClient (URLSession), endpoint enum               ← mirrors BibleApiService.kt
    Streaming/   SSE parser over URLSession.bytes                    ← mirrors EventSourceParser.kt
    Local/       SwiftData models + store                            ← mirrors data/local/ (Room)
    Prefs/       UserDefaults-backed settings                        ← mirrors data/preferences/
  Presentation/  SwiftUI views + @Observable view models             ← mirrors presentation/
  Security/      TurnstileCoordinator + WKWebView host               ← mirrors security/
  Analytics/     AnalyticsProtocol + NoOp + real impl                ← mirrors analytics/
```

Notes that matter:

- **SSE.** `URLSession.bytes(for:)` gives an `AsyncSequence` of lines; the parsing rules are already
  written down in `EventSourceParser.kt` — `data:` prefix, `[DONE]` sentinel, `type` field
  discriminating `metadata` / content / `completion`, unknown keys ignored. Match its
  lenient-parsing posture exactly; the backend adds optional fields over time on purpose
  (`api/chat/service.py:1380-1381`).
- **Turnstile is the highest-risk component, so build it first.** The full state machine, from
  `TurnstileInterceptor.kt`: header `X-Turnstile-Token` on POSTs only; tokens are **single-use** and
  consumed on every attached-token request regardless of status; on 403 reset the widget, wait
  longer (8s vs 5s), retry **exactly once**; fail open on timeout so the server's 403 surfaces
  instead of a hung UI. BITB-085 must already have proved a WKWebView can obtain a token — if it
  cannot, stop and revisit the approach rather than shipping an app whose every POST 403s.
- **No verse regex.** Citations come from BITB-086's `citations` spans; locate them by literal
  `text` + `occurrence` substring search rather than offset arithmetic (Swift `String` indexing
  makes offsets awkward, and the contract is designed to allow this). Degrade to plain text when the
  field is absent. **A hand-written `NSRegularExpression` citation grammar is a rejected design** —
  it would be the fourth dialect of audit finding A1.
- **Deployment target.** Decide and record. Default recommendation: **iOS 17.0 minimum** — SwiftData
  and the Observation framework both require 17, and going lower means CoreData plus
  `ObservableObject` for no user benefit. Android's floor is minSdk 26 / Android 8
  (`android/app/build.gradle.kts`), i.e. deliberately generous; iOS device longevity means a 17
  floor still reaches essentially every device in use.

## Localization

255 strings (`android/app/src/main/res/values/strings.xml`) × 11 languages. This is the largest
non-obvious cost in the story and the most likely place to create permanent drift.

- Reuse existing translations. Android `strings.xml` and web `frontend/messages/*.json` already
  contain almost every string this app needs, in every locale. **Write a conversion script**
  (`scripts/`) that produces `.xcstrings`/`.strings` from one of those sources rather than
  hand-copying — hand-copying 2,805 strings will produce errors and cannot be re-run when a string
  changes.
- Only translate genuinely new iOS-only strings by hand.
- Mirror the Android `translation-validation` CI job (`.github/workflows/android-ci.yml`): a missing
  key in any locale must fail CI, not surface as an English string in a Korean UI.
- RTL (`ar`) is a first-class layout requirement, not a checkbox. Use leading/trailing, never
  left/right.
- iOS gives per-app language switching for free in Settings once the app declares its
  localizations, but the app still needs its **own** in-app picker to match Android
  (`LanguagePickerBottomSheet.kt`) and to stay consistent with the language the backend is told to
  answer in.

## Analytics, Crash Reporting, and Privacy

- Mirror the Android indirection: an `AnalyticsProtocol` with a **NoOp default**
  (`analytics/AnalyticsHelper.kt` + `NoOpAnalyticsHelper.kt` + `FirebaseAnalyticsHelper.kt`), and
  disabled entirely in debug builds — Android does this via `FIREBASE_ENABLED=false` in the debug
  build type (`android/app/build.gradle.kts`).
- Whatever is chosen becomes an **App Privacy disclosure** and a `PrivacyInfo.xcprivacy` entry in
  BITB-088. Every SDK added here is a compliance obligation there, so add none casually. Shipping v1
  with **NoOp only** is a legitimate, defensible choice that keeps the first privacy label minimal.
- The app collects no location and needs no permissions beyond network — Android requests only
  `INTERNET` and `ACCESS_NETWORK_STATE` (`AndroidManifest.xml:5-6`). **Keep it that way.** Do not
  add a permission prompt to v1.

## Acceptance Criteria

- [ ] A user can ask a question and watch a streamed answer render, against **production**, on a
      physical iPhone.
- [ ] Turnstile: POSTs carry `X-Turnstile-Token`; a token is never reused; a 403 triggers one reset
      + retry; a token timeout fails open rather than hanging the UI. Covered by unit tests over the
      coordinator, mirroring the Android interceptor's tests.
- [ ] Every citation in `citations` is tappable and opens the verse; a message whose `citations` is
      absent or malformed renders as readable plain text.
- [ ] **No verse-reference regex exists anywhere in the iOS codebase** — enforced by a CI grep, not
      by reviewer diligence.
- [ ] Conversations persist across cold launch and are readable with the network off.
- [ ] The session message limit shows the same friendly "take a break" message as the other clients
      (BITB-023) and offers a new session.
- [ ] All 11 locales render, including `ar` in RTL, with no missing-key fallbacks. CI fails on a
      missing key.
- [ ] Light and dark mode both correct; Dynamic Type at the largest accessibility size does not clip
      or truncate the chat input or verse cards; VoiceOver reads messages and verse links.
- [ ] Safe areas correct on a notched device, including with the keyboard raised.
- [ ] A TestFlight build is installed and used by at least one real device for a week without a
      blocking defect.
- [ ] No donate/Ko-fi entry point ships (BITB-085's recorded decision; BITB-074 must not add one).
- [ ] No new permission prompts.
- [ ] Backend and other clients are untouched — the diff outside the iOS directory (plus the
      localization script and CI) is empty.

## Tests to Add

Per the AGENTS.md testing rule, and mirroring the Android tiering (46 JVM test files, 7 Compose UI
tests in a **separate** Gradle task — see `android/COMPOSE_TESTS.md`):

- **XCTest unit tests** for: the SSE parser (against captured real fixtures, including the
  `metadata` → content → `completion` sequence, `[DONE]`, malformed lines, and unknown fields);
  the Turnstile state machine (single-use, 403-retry-once, fail-open); citation-span rendering
  including the malformed/absent cases; the SwiftData store; preference persistence.
- **Parametrized cross-language tests** across all 11 languages for citation rendering — the
  AGENTS.md multilingual rule applies to iOS the moment it renders citations. Reuse the shared
  corpus in `tests/fixtures/` (PR #906) rather than writing an iOS-only one.
- **XCUITest UI tests as a separate, non-required CI tier initially**, exactly as
  `android/COMPOSE_TESTS.md` did for Compose — a flaky new UI tier must not block merges while it
  stabilises. Document the promotion checklist the same way.
- **A CI grep** asserting no regex literal matching chapter:verse patterns exists in the Swift
  sources. This is the guard that keeps the "no fourth parser" promise after the author who made it
  has moved on.

## Files Likely to Change

| Path | Change |
|---|---|
| `ios/` | **New** — Xcode project, mirroring the top-level `android/` convention |
| `ios/README.md` | **New** — setup, build, test, mirroring `android/README.md` |
| `scripts/generate_ios_strings.py` | **New** — `strings.xml` / `messages/*.json` → `.xcstrings` |
| `.github/workflows/ios-ci.yml` | **New** — build + unit tests on a macOS runner (BITB-088 adds publishing) |
| `docs/ios/delivery-approach.md` | Updated with what the build actually taught |
| `AGENTS.md` | Repository-layout, testing, and pitfalls sections gain the iOS client |
| `Makefile` | `ios-test` target beside `android-test` |

## Out of Scope

- App Store submission, store metadata, screenshots, privacy label — **BITB-088**.
- Tier 2 features listed above.
- **iPad-optimised layouts.** Ship iPhone-only for v1 and say so in App Store Connect; a stretched
  iPhone UI on a 13" iPad is a worse first impression than not supporting it.
- **Apple Watch, widgets, Siri/App Intents, Live Activities, push.** No push exists on any platform
  today; adding it to iOS first is a product decision (see BITB-084 *Out of Scope*).
- **An iOS equivalent of in-app updates.** `InAppUpdateManager.kt` uses the Play Core API; there is
  no iOS counterpart. If a "please update" nudge is wanted later it needs a version check against
  the backend `/config` endpoint — a separate story, not a silent addition.
- Sign in with Apple — the app has no accounts and offers no third-party login, so Guideline 4.8
  does not apply. Do not add auth to "look complete".

## Related

- **BITB-086** — the citation contract that keeps a fourth parser out of this codebase.
- **BITB-085** — the approach decision and the Turnstile feasibility proof this story assumes.
- **BITB-088** — the release pipeline that takes this to the App Store.
- **BITB-012** — the Android-to-production precedent for how this repo ships a store app.
- **BITB-023** — the session-limit UX this must match.
- **BITB-059 / audit A1** — why the no-regex constraint is non-negotiable.
