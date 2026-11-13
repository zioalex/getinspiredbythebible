# BITB-057: Android — In-App Update API (Flexible Flow)

**Status:** 🚧 In Progress — [PR #863](https://github.com/zioalex/getinspiredbythebible/pull/863) open, pending CI + review
**Priority:** P1 (High) — users stuck on outdated builds get no new features or fixes
**Size:** M (1–2 days)
**Created:** 2026-07-01
**Source:** Product initiative — no Play update surface exists

## User Story

**As an** Android user,
**I want** the app to tell me when a new version is available,
**so that** I can update and get the latest features and fixes without checking the Play Store manually.

## Problem

The app has no mechanism to detect or prompt for Play Store updates. Users on outdated builds receive no signal that improvements exist. Google Play provides the In-App Update API (`com.google.android.play:app-update-ktx`) which allows apps to initiate flexible or immediate update flows without leaving the app.

## Approach

Implement the **flexible update flow** (background download, non-disruptive):

1. On every cold start, check for update availability via `AppUpdateManager`.
2. If `updateAvailability == UPDATE_AVAILABLE && clientVersionStalenessDays ≥ 3 && isUpdateTypeAllowed(FLEXIBLE)`, start the flexible flow.
3. Register `InstallStateUpdatedListener`; when `installStatus == DOWNLOADED`, show a Snackbar: "Update downloaded — tap to install" with an action that calls `appUpdateManager.completeUpdate()`.
4. In `onResume`, re-check for a previously downloaded but not yet installed update (user backgrounded the app during download).
5. Guard with `if (BuildConfig.DEBUG) return` — Play Store not available in debug builds.

## Acceptance Criteria

- [ ] `com.google.android.play:app-update-ktx` (v2.1.0) added to `libs.versions.toml` and `build.gradle.kts`
- [ ] `InAppUpdateManager.kt` wraps `AppUpdateManager`; injected as a constructor parameter so tests can substitute `FakeAppUpdateManager`
- [ ] Update check triggered on cold start in `MainActivity.onCreate()`; silent no-op in `BuildConfig.DEBUG`
- [ ] Flexible flow initiated when update is available and staleness ≥ 3 days
- [ ] Snackbar shown with "Install update" action when download completes; tapping it calls `completeUpdate()`
- [ ] `onResume` re-checks for a pending install (handles app-backgrounded-during-download case)
- [ ] Unit tests with `FakeAppUpdateManager` verify: (a) flow initiated when update available; (b) snackbar callback fires when DOWNLOADED; (c) silent no-op when no update available
- [ ] No crash in debug or on a sideloaded build (Play API errors handled gracefully)

## Files / Config

| Item | Location | Change |
|---|---|---|
| Dependency version | `android/gradle/libs.versions.toml` | Add `play-app-update = "2.1.0"` |
| Dependency declaration | `android/app/build.gradle.kts` | Add `implementation(libs.play.app.update)` |
| Update manager | `android/app/src/main/kotlin/org/voxquieta/app/InAppUpdateManager.kt` | New — wraps AppUpdateManager, exposes `checkForUpdate`, `checkForPendingInstall`, `completeUpdate` |
| Main Activity | `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | Call `checkForUpdate` in `onCreate`; call `checkForPendingInstall` in `onResume`; register/unregister `InstallStateUpdatedListener` |
| Test | `android/app/src/test/kotlin/org/voxquieta/app/InAppUpdateManagerTest.kt` | New — unit tests with `FakeAppUpdateManager` |

## Implementation Notes

```kotlin
// libs.versions.toml additions
[versions]
play-app-update = "2.1.0"

[libraries]
play-app-update = { group = "com.google.android.play", name = "app-update-ktx", version.ref = "play-app-update" }
```

```kotlin
// InAppUpdateManager.kt (skeleton)
class InAppUpdateManager(private val appUpdateManager: AppUpdateManager) {
    companion object {
        private const val DAYS_FOR_FLEXIBLE_UPDATE = 3
        private const val UPDATE_REQUEST_CODE = 1001
    }

    fun checkForUpdate(activity: Activity, onDownloaded: () -> Unit) {
        if (BuildConfig.DEBUG) return
        appUpdateManager.appUpdateInfo.addOnSuccessListener { info ->
            when {
                info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE
                    && (info.clientVersionStalenessDays() ?: 0) >= DAYS_FOR_FLEXIBLE_UPDATE
                    && info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE) ->
                    appUpdateManager.startUpdateFlowForResult(
                        info, AppUpdateType.FLEXIBLE, activity, UPDATE_REQUEST_CODE
                    )
                info.installStatus() == InstallStatus.DOWNLOADED -> onDownloaded()
            }
        }
    }

    fun checkForPendingInstall(onDownloaded: () -> Unit) {
        if (BuildConfig.DEBUG) return
        appUpdateManager.appUpdateInfo.addOnSuccessListener { info ->
            if (info.installStatus() == InstallStatus.DOWNLOADED) onDownloaded()
        }
    }

    fun completeUpdate() { appUpdateManager.completeUpdate() }
}
```

`FakeAppUpdateManager` (from `com.google.android.play:app-update-testing-ktx`) provides a fully controllable test double — no Play Store access needed.

## Testing

- Unit: `FakeAppUpdateManager.setUpdateAvailable(newVersionCode)` + staleness → assert `startUpdateFlowForResult` called
- Unit: set `installStatus = DOWNLOADED` → assert `onDownloaded` lambda fires
- Unit: no update available → assert no flow started, no crash
- Manual: sideload an older APK, trigger via testing API → verify snackbar appears

## Out of Scope

- Immediate update flow (too disruptive for this app's update cadence; flexible is sufficient)
- Tracking update funnel metrics in Firebase Analytics (follow-up)
- iOS
