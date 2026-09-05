# BITB-121: Android Sessions Are Counted as Web in the Weekly Report

**Status:** 🚧 In Progress - implementation in PR #1038; rollout verification pending
**Priority:** P1
**Size:** S
**Created:** 2026-09-04

## User Story

As the maintainer reading the weekly digest, I want requests from the Android
app to carry a reliable app/OS identifier, so those sessions participate in the
existing mobile-device bucket instead of being indistinguishable from generic
JVM clients.

## Semantics

The digest reports a **web vs. mobile-device** heuristic based on
`sessions.is_mobile`. It does not report Android-app adoption separately.
Mobile browsers and explicit Android/Dalvik clients share the mobile bucket.
Android-app-specific counts require querying the stored app UA.

A bare `okhttp/<version>` UA is not reliable evidence of Android: OkHttp is a
general-purpose JVM client. Existing app versions that expose only that UA
cannot be safely reclassified or backfilled as Android. This story supersedes
the deleted orphan `BITB-069-android-user-agent-mobile-split.md`; BITB-069
remains the completed splash-screen hydration story.

## Root Cause

The Android client did not set an identifying transport UA, so OkHttp supplied
its generic default. `_detect_mobile` correctly had no reliable platform signal
and stored those requests in the non-mobile bucket. The app also omitted
`Accept-Language`, even though chat request bodies already contain the user's
selected language.

Blank/whitespace UAs exposed another issue: classification and persistence
could disagree about whether a meaningful value existed, and a later missing
UA could overwrite an established classification unless the upsert received
`NULL`.

## Fix

1. The Android app sends `VoxQuieta/<version> (Android <release>)` on every API
   request. It deliberately omits `Build.MODEL` to avoid unnecessary device
   fingerprinting.
2. Mobile detection retains reliable explicit markers, including `android`
   and `dalvik`, but does not classify generic `okhttp` traffic as mobile.
3. Session tracking trims the UA once and uses the same normalized value for
   both classification and storage. Missing/blank UAs bind `NULL`, preserving
   an existing classification through `COALESCE`.
4. Both chat handlers prefer the supported base language from
   `ChatRequest.language`, then fall back to normalized `Accept-Language`.
5. Unit, route, integration, and Android wiring tests cover these boundaries.

## Acceptance Criteria

- [x] Android requests carry an app-identifying UA containing `Android`
- [x] The UA includes app/Android versions but no device model
- [x] Explicit Android and Dalvik UAs are mobile; generic OkHttp UAs are not
- [x] Blank/missing UAs are consistently stored and classified as absent
- [x] A UA-less follow-up does not flip an established mobile session
- [x] Both chat handlers prefer normalized, supported request-body language
- [x] Android production service wiring applies the interceptor
- [x] BITB-121 reconciles and supersedes the duplicate orphan BITB-069 story
- [ ] API and app release deployed
- [ ] A post-release digest confirms Android app requests enter the mobile bucket

## Historical Data

Rows with explicit Android or Dalvik UAs can be identified from
`sessions.user_agent`. Bare OkHttp rows cannot safely be attributed to Android,
so no broad OkHttp backfill should be performed. Historical language is not
recoverable where it was never recorded.

## Related

- `api/utils/session_tracker.py`
- `api/routes/chat.py`
- `api/reports/weekly_report.py`
- `android/app/src/main/kotlin/org/voxquieta/app/data/remote/interceptors/UserAgentInterceptor.kt`
- `docs/USAGE_TRACKING.md`
- `docs/WEEKLY_REPORT.md`
