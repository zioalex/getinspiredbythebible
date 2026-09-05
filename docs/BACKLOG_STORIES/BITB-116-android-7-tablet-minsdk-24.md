# BITB-116: Support Android 7.0+ Tablets (Lower minSdk 26 -> 24)

**Status:** 🚧 In Progress
**Priority:** P1 — user-visible install failure on a real device (Android 7.1.1 tablet, API 25)
**Size:** S (config + desugaring, emulator/API-matrix verification)
**Created:** 2026-09-05
**Reported by:** product owner — app does not work on old Android tablet (7.1.1)
**Affects:** Android (`android/`) only — backend/frontend untouched

## User Story

**As** a user on an Android 7.x tablet (API 24-25),
**I want** to install and use the app from the same Play listing,
**so that** I am not blocked by the recent targetSdk 36 update.

## Context

- `android/app/build.gradle.kts:68-69`: `minSdk 26` (Android 8.0), `targetSdk 36`.
- Android 7.1.1 is API 25 < 26, so Play filters the app and sideload fails
  `INSTALL_FAILED_OLDER_SDK`. `targetSdk 36` is unrelated and must stay for
  Play compliance (new/updates must target 36 by 2026-08-31, ext. Nov 1).
- Decision (2026-09-05): single AAB with `minSdk 24` (Android 7.0), not
  multi-APK. `24` covers all Nougat for the same cost as `25`; dependency
  floors (Room 2.8.x >= 23, core-ktx/appcompat/Compose/DataStore/Firebase)
  all support 24.

## Changes

1. `android/gradle/libs.versions.toml` — add `desugarJdkLibs = "2.0.3"` +
   `desugar-jdk-libs` library entry.
2. `android/app/build.gradle.kts` — `minSdk 26 -> 24`; `compileOptions`
   `isCoreLibraryDesugaringEnabled = true`; `coreLibraryDesugaring(...)`
   dependency; keep `useLegacyPackaging = false` (mandatory below 26 for
   16 KB page-size compliance) and `targetSdk/compileSdk 36` untouched.

Explicitly **not** in scope: lowering `targetSdk`, multi-APK/flavors,
dropping any dependency.

## Acceptance Criteria

- [ ] `minSdk 24`, `targetSdk 36`, `compileSdk 36` in `app/build.gradle.kts`
- [ ] Desugaring enabled; release AAB builds without `MethodHandle` / desugar errors
- [ ] `lintDebug` passes with no new `NewApi` errors
- [ ] `testDebugUnitTest` passes
- [ ] Installs/launches on API 24/25 emulator (or documented manual tablet check);
      core flows (launch, chat, settings, locale) smoke-tested on old + new API
- [ ] Play Pre-launch + 16 KB check clean; single AAB serves both old and new devices

## Related

- `android/app/build.gradle.kts:20,66-69,138-141` (compileSdk/minSdk/targetSdk/compileOptions)
- `android/gradle/libs.versions.toml` (dependency floors)
- `android/app/src/main/kotlin/org/voxquieta/app/utils/LocaleApplier.kt:35`
  (SDK_INT guard pattern to keep for any new API calls)
- Play target API policy: new/updates must target 36 by 2026-08-31
