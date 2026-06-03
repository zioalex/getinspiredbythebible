# BITB-038: Android In-App "Update Available" Prompt

**Status:** 🎯 Todo

## User Story

As an Android user with the app installed, I want the app to notice when a
newer version has been published and gently invite me to update, so that I stay
on the latest release — getting fixes and new features — without having to
remember to check the Play Store myself.

## Problem

The Android app (`org.voxquieta`, native Kotlin / Jetpack Compose) has **no
mechanism to nudge users to update**. Once the app is distributed via Google
Play (BITB-012), users can silently remain on stale versions indefinitely —
missing bug fixes and features, and making support harder ("which version are
you on?"). There is currently no "check for updates" code anywhere in the
codebase.

We want a non-intrusive in-app prompt that appears while the app is open,
inviting the user to update to the latest version.

## Approach: Google Play In-App Updates (flexible flow)

Use Google's official **Play In-App Updates** library
(`com.google.android.play:app-update` + `:app-update-ktx`) rather than a custom
version check. This is the right fit because the app ships through Play:

- **Play already knows the latest available version** on the user's track, so
  no custom `/latest-version` backend endpoint and no GitHub Releases polling
  are needed — there is nothing to keep in sync.
- The library handles version comparison, the download, and the install
  handshake for us.
- It exposes an **update priority** (set per release in Play Console) and a
  **staleness** signal so we can escalate truly important updates.

Use the **flexible** update flow as the default UX:

1. On app start, a small Hilt-injected `InAppUpdateManager` wrapper calls
   `appUpdateManager.appUpdateInfo` to query Play.
2. If `updateAvailability() == UPDATE_AVAILABLE` and
   `isUpdateTypeAllowed(FLEXIBLE)`, start the flexible flow. The update
   downloads in the background while the user keeps using the app.
3. An install-state listener watches for `InstallStatus.DOWNLOADED`. When the
   download completes, show a **Snackbar** — reusing the existing
   `snackbarHostState` pattern already wired in `ChatScreen.kt` — inviting the
   user to "Restart to update". The Snackbar action calls
   `appUpdateManager.completeUpdate()`.
4. **Escalation:** when Play reports a high `updatePriority()` or the update is
   stale beyond a threshold (e.g. `clientVersionStalenessDays`), start the
   **immediate** (full-screen blocking) flow instead.

> Note: Play In-App Updates only works for apps **installed from the Play
> Store**. This story therefore follows the Play production launch (BITB-012)
> and cannot be exercised on sideloaded/debug builds except via
> `FakeAppUpdateManager` (tests) or an internal-testing/internal-app-sharing
> build.

## Proposed Changes

### 1. Add the Play app-update dependency

In `android/app/build.gradle.kts` add:

```kotlin
implementation("com.google.android.play:app-update:2.1.0")
implementation("com.google.android.play:app-update-ktx:2.1.0")
```

(Implementer: pin to the latest stable `app-update` version at build time.)

### 2. New `InAppUpdateManager.kt` (Hilt singleton wrapper)

- Location:
  `android/app/src/main/kotlin/org/voxquieta/app/update/InAppUpdateManager.kt`.
- Wraps `AppUpdateManagerFactory.create(context)`; provided via a Hilt module
  in `android/app/src/main/kotlin/org/voxquieta/app/di/`.
- Exposes suspend/Flow APIs: `checkForUpdate()`, an `installStatus` Flow, and
  `completeFlexibleUpdate()`.
- Decides flexible vs. immediate based on `updatePriority()` /
  staleness thresholds (pure function, unit-testable).
- Registers/unregisters the `InstallStateUpdatedListener` with lifecycle so it
  doesn't leak.

### 3. Trigger the check and handle the result in `MainActivity`

- In `MainActivity.kt`, kick off `checkForUpdate()` on start (e.g. in
  `onResume`, and re-check `appUpdateInfo` on resume to resume a stalled
  flexible/immediate update).
- Register an `ActivityResultLauncher` (or use
  `startUpdateFlowForResult`) to launch the Play update activity and observe its
  result.

### 4. Surface the "restart to install" prompt

- Use the existing Material3 `SnackbarHost` / `snackbarHostState` already
  present in `ChatScreen.kt`. When `installStatus == DOWNLOADED`, show a
  Snackbar with text `update_available_message` and action
  `update_restart_action` → `completeFlexibleUpdate()`.
- Reuse the existing `AlertDialog` pattern from `SettingsScreen.kt` only if a
  confirmation dialog is preferred for the immediate-flow escalation.

### 5. Throttle the prompt with DataStore

- Persist a "last prompted / snoozed version code" (and optionally a snooze
  timestamp) in the app's existing **DataStore** preferences so the prompt is
  **not shown on every launch** and a version the user dismissed is not
  re-shown until a newer one appears.

### 6. Analytics

- Log events via the existing `analytics/AnalyticsHelper.kt`:
  `update_prompt_shown`, `update_accepted`, `update_dismissed` (release builds
  only, matching current Firebase gating).

### 7. String resources

Add to `android/app/src/main/res/values/strings.xml` and **all 10 locale
variants** (`values-de`, `values-ru`, `values-zh`, `values-hi`, `values-ar`,
`values-pt`, `values-ko`, `values-fr`, `values-it`, `values-es`):

- `update_available_message` — e.g. "A new version of Vox Quieta is ready."
- `update_restart_action` — e.g. "Restart"
- `update_immediate_title` / `update_immediate_message` — for the blocking flow
  (optional, only if escalation UI needs copy)

(CI `translation-validation` requires every key to exist in every locale.)

## Acceptance Criteria

- [ ] On launch, the app queries Play for a newer version (flexible flow) and
      keeps the app usable while any download proceeds in the background.
- [ ] When an update finishes downloading, a Snackbar invites the user to
      restart and install; the action completes the update via
      `completeUpdate()`.
- [ ] A high-priority / stale update triggers the **immediate** (blocking) flow
      instead of the flexible one.
- [ ] The prompt is throttled via DataStore — not shown on every launch, and a
      dismissed version is not re-prompted until a newer version is available.
- [ ] A flexible/immediate update interrupted by the app being backgrounded is
      resumed on the next resume.
- [ ] Analytics events are logged for prompt shown / accepted / dismissed.
- [ ] New strings exist in all 11 locales (English + 10 variants); CI
      `translation-validation` passes.
- [ ] `./gradlew assembleDebug`, `testDebugUnitTest`, and `lint` all pass.
- [ ] Update decision logic (flexible vs. immediate, throttle) is unit-tested
      using `FakeAppUpdateManager`.
- [ ] Manual QA via internal app sharing / internal-testing track: install an
      older build, publish a newer one, confirm the prompt appears and the
      update installs.

## Files to Modify

| File | Change |
|---|---|
| `android/app/build.gradle.kts` | Add `app-update` + `app-update-ktx` dependencies |
| `android/app/src/main/kotlin/org/voxquieta/app/update/InAppUpdateManager.kt` | **New** — Play update wrapper (check, listen, complete, flexible/immediate decision) |
| `android/app/src/main/kotlin/org/voxquieta/app/di/` (e.g. `UpdateModule.kt`) | Provide `AppUpdateManager` / `InAppUpdateManager` via Hilt |
| `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | Trigger check on start/resume; register activity-result launcher; resume interrupted updates |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ChatScreen.kt` | Show "restart to update" Snackbar via existing `snackbarHostState` |
| DataStore prefs (existing preferences module) | Add last-prompted / snooze version key |
| `android/app/src/main/kotlin/org/voxquieta/app/analytics/AnalyticsHelper.kt` | Add update prompt analytics events |
| `android/app/src/main/res/values/strings.xml` + 10 locale variants | Add update prompt strings |

## Out of Scope

- System / push notifications (e.g. Firebase Cloud Messaging) when the app is
  **closed** — FCM is not currently in the app; this story only covers in-app
  prompting while the app is open. A background-notification approach is a
  separate, larger story.
- Custom version-check endpoint or GitHub Releases polling — Play handles
  version comparison.
- Updating sideloaded / direct-APK installs (in-app updates require Play
  install source).
- iOS app.
- A "What's New" changelog after upgrade — already covered by BITB-031.

## Priority

**P2 — Medium.** High user value (keeps the install base current and reduces
support burden), but it only becomes meaningful **after the app is live on
Google Play**, so it is not a launch blocker and naturally follows BITB-012.
In-app updates do not function for non-Play installs.

## Size

**M (1–2 days)** — one new manager class + Hilt wiring + MainActivity result
handling + Snackbar wiring + DataStore throttle + 11 string-resource files +
unit tests with `FakeAppUpdateManager`.

## Dependencies / Related Work

- **Depends on / follows:** BITB-012 (Migrate Android App to Production /
  Play Store launch) — in-app updates only work for Play-installed apps.
- **Related:** BITB-031 (in-app changelog) — complementary: changelog shows
  *what* changed, this story prompts the user *to get* the change.
- Reuses: existing Hilt DI, DataStore preferences, Material3 Snackbar
  (`ChatScreen.kt`), `BuildConfig.VERSION_NAME`, and `AnalyticsHelper`.

## Assignee

android-expert
