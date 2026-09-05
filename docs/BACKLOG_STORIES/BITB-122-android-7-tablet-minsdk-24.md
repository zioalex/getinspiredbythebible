# BITB-122: Support Android 7.0+ Tablets (Lower minSdk 26 -> 24)

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
   dependency; retain explicit `useLegacyPackaging = false` so native libraries
   stay uncompressed and aligned, and leave `targetSdk/compileSdk 36` untouched.
3. Trust the official ISRG Root X1 certificate alongside system CAs only for
   `api.voxquieta.org`, covering Android 7.0's older trust store without changing
   trust for any other host. Source: `https://letsencrypt.org/certs/isrgrootx1.pem`;
   SHA-256: `96:BC:EC:06:26:49:76:F3:74:60:77:9A:CF:28:C5:A7:CF:E8:A3:C0:AA:E1:1A:8F:FC:EE:05:C0:BD:DF:08:C6`.
4. CI installs, launches, and exercises production TLS on API 24 and 25, and
   builds an ephemeral-signed release AAB with manifest metadata checks.

Explicitly **not** in scope: lowering `targetSdk`, multi-APK/flavors,
dropping any dependency.

## Acceptance Criteria

- [ ] `minSdk 24`, `targetSdk 36`, `compileSdk 36` in `app/build.gradle.kts`
- [ ] Desugaring enabled; release AAB builds without `MethodHandle` / desugar errors
- [ ] `lintDebug` passes with no new `NewApi` errors
- [ ] `testDebugUnitTest` passes
- [ ] Production API TLS succeeds with hostname verification on API 24 and 25
- [ ] Installs/launches on API 24/25 emulator (or documented manual tablet check);
      core flows (launch, chat, settings, locale) smoke-tested on old + new API
- [ ] Play Pre-launch + 16 KB check clean; single AAB serves both old and new devices

## Related

- `android/app/build.gradle.kts:20,66-69,138-141` (compileSdk/minSdk/targetSdk/compileOptions)
- `android/gradle/libs.versions.toml` (dependency floors)
- `android/app/src/main/kotlin/org/voxquieta/app/utils/LocaleApplier.kt:35`
  (SDK_INT guard pattern to keep for any new API calls)
- Play target API policy: new/updates must target 36 by 2026-08-31
