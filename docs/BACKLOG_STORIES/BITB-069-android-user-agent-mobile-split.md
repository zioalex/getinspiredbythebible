# BITB-069: Android — Send a User-Agent so the weekly report's Web/Mobile split is correct

**Status:** 📋 To Do

## User Story

As the maintainer reading the weekly activity digest, I want Android traffic to be
counted as **mobile** in the Web/Mobile split (and to record a meaningful user-agent),
so the Engagement section reflects reality instead of attributing every Android session
to "web".

## Problem

The backend classifies a session as mobile vs. web purely from the HTTP `User-Agent`
header:

- `api/utils/session_tracker.py:56` — `_detect_mobile()` returns true only when the UA
  contains one of `mobile`, `android`, `iphone`, `ipad`.
- The value is stored on the `sessions` row and surfaced by the weekly digest's
  `Web / Mobile` line (`api/reports/weekly_report.py`).

The Android OkHttp client sets no User-Agent header
(`android/app/src/main/kotlin/org/voxquieta/app/data/remote/api/ApiClient.kt:32-40`),
so requests carry OkHttp's default `okhttp/<version>`. That matches none of the mobile
keywords, so once session tracking is active on `/chat/stream`, **every Android session
is counted as web** and `sessions.user_agent` stores `okhttp/…`.

(The `"Android/${Build.VERSION.RELEASE}"` string in `ChatViewModel.kt:1056` is sent as a
contact-form *body* field, not as the transport User-Agent header — it does not affect
session tracking.)

## Proposed Changes

Add a small interceptor in `ApiClient.create(...)` that sets a stable, descriptive
User-Agent on every request, e.g.:

```kotlin
.addInterceptor { chain ->
    val req = chain.request().newBuilder()
        .header("User-Agent", "VoxQuieta-Android/$appVersion (Android ${Build.VERSION.RELEASE})")
        .build()
    chain.proceed(req)
}
```

- Contains "Android", so `_detect_mobile()` classifies it as mobile.
- Include the app version (thread it in from `BuildConfig`) for future debugging.
- Applies to all endpoints, so contact/feedback rows also get a real UA.

No backend change required — `_detect_mobile()` already keys on "android".

## Acceptance Criteria

- [ ] Every request from the Android app carries a `User-Agent` header containing
      "Android".
- [ ] After a chat send, the corresponding `sessions` row has `is_mobile = true` and a
      non-`okhttp` `user_agent`.
- [ ] A dry-run weekly report attributes Android sessions to the Mobile column.
- [ ] Unit/instrumentation test asserts the interceptor sets the header.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/data/remote/api/ApiClient.kt` | Add a User-Agent interceptor (thread app version in from `BuildConfig`) |
| Android test (e.g. an ApiClient/interceptor test) | Assert the `User-Agent` header is present and contains "Android" |

## Out of Scope

- The backend streaming session-tracking fix (this backlog item's prerequisite; tracked
  separately).
- Reworking Android's `session_id` reset-on-new-conversation behavior (see Notes).
- Richer device analytics (model, OS API level breakdown).

## Priority

P2 — the Web/Mobile split is wrong for all mobile users until this lands. Small, isolated.

## Size

S — one interceptor + a test.

## Dependencies / Related Work

- Depends on the backend fix that makes `/chat/stream` call `track_session`.
- Related: `docs/USAGE_TRACKING.md`, `docs/WEEKLY_REPORT.md`.

## Assignee

android-expert
