# BITB-051: Android In-App Update Prompt (Google Play Flexible Update)

**Status:** 🚧 In Progress
**Priority:** P2 (Medium) — UX improvement
**Size:** S (2–3 hours)
**Created:** 2026-06-16

## User Story

**As an** Android user,
**I want** the app to notify me when a newer version is available in the Play Store,
**so that** I can install the update without having to leave the app or manually check the store.

## Problem

Users on older versions have no in-app signal that new features or fixes are waiting for them.
The only discovery path is the Play Store's update badge — easily missed.
A non-intrusive snackbar at the bottom of the screen, shown only after the update has already
been downloaded in the background, surfaces the prompt naturally without interrupting the user.

## Approach

Use [Google Play In-App Update API](https://developer.android.com/guide/playcore/in-app-updates)
with the **FLEXIBLE** update type:
- Background download — user can continue using the app while the update downloads.
- A snackbar with a "Restart" action appears only after the download completes.
- User can swipe-dismiss and skip the restart; the snackbar will reappear next cold start.
- Gracefully no-ops when Play Store is absent (emulators, F-Droid, sideloaded APKs).

## Acceptance Criteria

- [ ] When a new Play Store version is available, the app starts a background flexible update.
- [ ] After download completes, a snackbar appears: "Update ready — tap Restart to apply it" / "Restart".
- [ ] Tapping "Restart" calls `completeUpdate()` and the app restarts with the new version.
- [ ] Dismissing the snackbar (swipe) leaves the app running; snackbar reappears on next cold start.
- [ ] No crash on devices without Play Store (emulators, sideloads).
- [ ] All 11 locale string files contain the two new string keys.
- [ ] `./gradlew testDebugUnitTest` passes (includes `InAppUpdateHelperTest`).
- [ ] `./gradlew assembleDebug` compiles cleanly.

## Files Changed

| File | Change |
|---|---|
| `android/gradle/libs.versions.toml` | Add `play-app-update = "2.1.0"` version + `play-app-update-ktx` library alias |
| `android/app/build.gradle.kts` | Add `implementation(libs.play.app.update.ktx)` |
| `android/app/src/main/kotlin/org/voxquieta/app/update/InAppUpdateHelper.kt` | New — wraps AppUpdateManager, exposes `updateDownloaded: StateFlow<Boolean>` |
| `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | Wire update helper; register result launcher; add snackbar overlay |
| `android/app/src/main/res/values/strings.xml` + 10 locale variants | Add `update_download_complete` and `update_action_restart` |
| `android/app/src/test/kotlin/org/voxquieta/app/update/InAppUpdateHelperTest.kt` | New — unit tests for state transitions |

## Out of Scope

- IMMEDIATE (forced) update type.
- A "what's new" dialog on first launch after update (separate story).
- Translation of changelog body text.
- iOS app.
