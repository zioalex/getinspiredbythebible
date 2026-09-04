# BITB-121: Android Sessions Are Counted as Web in the Weekly Report

**Status:** 🚧 In Progress — code fix in PR #1038 (branch `claude/android-users-weekly-report-wt1pdm`, commit `6132d01`), CI green, awaiting review; historical backfill and the body-`language` fallback not started
**Priority:** P1
**Size:** S
**Created:** 2026-09-04
**Found by:** product owner reading the weekly digest — "I don't see any Android user in the report, just web user, and this sounds wrong"

## The Finding

The weekly digest reported **zero mobile sessions**: all traffic, Android included, showed up under
"Web sessions". The report itself was correct; the data feeding it was wrong.

**Root cause chain:**

1. `api/reports/weekly_report.py:218-223` splits engagement on `sessions.is_mobile` — nothing else.
2. `sessions.is_mobile` is derived **only** from the request's `User-Agent`, by
   `api/utils/session_tracker.py::_detect_mobile`, which matched
   `mobile` / `android` / `iphone` / `ipad`.
3. The Android app **never sent a User-Agent.** `ApiClient.kt` built a bare `OkHttpClient` with no
   UA header, so every request went out as OkHttp's default `okhttp/4.12.0`
   (version pinned at `android/gradle/libs.versions.toml:31`) — which matches none of those
   keywords.

So every Android session was stored with `is_mobile = false` and counted in the web bucket. The web
app was never affected: browsers always send a real UA.

**Two second-order defects surfaced while tracing it:**

- **Android was invisible in "Top languages" too.** `api/routes/chat.py:71-73` (and `:127-129` on
  the streaming path) derive the session language from the `Accept-Language` header, which the app
  also does not send — see the standing comment at
  `android/.../viewmodels/ChatViewModel.kt:951` ("OkHttp sends no Accept-Language"). Those sessions
  were stored with `language = NULL`.
- **`is_mobile` could silently regress to `false`.** The upsert's
  `is_mobile = COALESCE(:mobile, sessions.is_mobile)` was dead code: `track_session` computed
  `_detect_mobile(user_agent) if user_agent else False`, so the bound value was always concrete and
  the `COALESCE` never fell through. Any later request without a UA overwrote an established mobile
  session back to web. `api/tests/test_session_tracker_integration.py:136-143` had *documented this
  as known-wrong behaviour* rather than fixing it.

**Evidence (real Postgres, identical session mix, before vs. after):**

| Session | UA sent | `is_mobile` before | `is_mobile` after |
|---|---|---|---|
| Android app, current release | `VoxQuieta/1.8.0 (Android 14; Pixel 7)` | `false` | `true` |
| Android app, older install | `okhttp/4.12.0` | `false` | `true` |
| Desktop browser | `Mozilla/5.0 (Windows NT 10.0…)` | `false` | `false` |
| Mobile browser | `Mozilla/5.0 (Linux; Android 14) Mobile` | `true` | `true` |

Report line: **3 web / 1 mobile → 1 web / 3 mobile.**

## Fix

**Shipped in PR #1038 (commit `6132d01`):**

1. **`UserAgentInterceptor`** (`android/.../data/remote/interceptors/UserAgentInterceptor.kt`),
   wired through `ApiClient.kt` and `NetworkModule.kt`: stamps
   `User-Agent: VoxQuieta/<version> (Android <release>; <model>)` and `Accept-Language` on every
   request. Header values are filtered to printable ASCII — `Build.MODEL` is vendor-supplied free
   text and OkHttp rejects non-ASCII header values outright.
2. **`okhttp` / `dalvik` added as mobile markers** in `_detect_mobile`. This is the part that
   matters operationally: installs already on users' phones cannot be updated retroactively, so
   without it the report stays wrong until users update. With it, the numbers correct themselves the
   moment the API deploys.
3. **`is_mobile` bound as `NULL`** (not `FALSE`) when a request carries no UA, so the `COALESCE`
   actually retains prior detection. The insert path keeps its `FALSE` default via
   `COALESCE(:mobile, FALSE)`. The integration test now asserts retention instead of documenting the
   bug.

**The rest of the work this story tracks** (item 6 has since been closed by CI; 4 and 5 are
still not started):

4. **Prefer the request body's `language` over the `Accept-Language` header** in
   `api/routes/chat.py` (both the `chat` and `chat_stream` handlers), falling back to the header.
   `ChatRequest.language` already exists (`api/chat/service.py:105`) and the Android app **already
   populates it** (`ChatRequestDto.kt:12`, set from `currentLocale` at `ChatViewModel.kt:472`) — it
   is simply never read for session tracking. Same argument as item 2: this fixes language
   attribution for **every install already in the field**, with no app release, and it uses the
   user's explicitly chosen UI language rather than a device header. This is the higher-value half
   of the language fix; the interceptor's `Accept-Language` only helps updated installs.
5. **Backfill historical rows.** `sessions.user_agent` is retained (its `COALESCE` was never
   broken), so past Android sessions are identifiable and reclassifiable — an Alembic revision
   (`api/alembic/`, per `docs/MIGRATION_GUIDELINES.md`; `scripts/migrations/` is frozen) setting
   `is_mobile = TRUE` where the stored UA matches the marker list. Without this, week-over-week
   comparisons stay distorted and every past digest remains wrong.
   **Known limit, worth stating plainly:** historical `language` is **not** recoverable — it was
   never stored for these sessions. Item 4 fixes it going forward only.
6. ~~**Verify the Android unit tests actually compile and pass.**~~ **Done.**
   `UserAgentInterceptorTest` was written but never run locally: the environment the fix was
   authored in blocks `dl.google.com`, so the Android SDK could not be installed and Gradle could
   not configure the module. PR #1038's CI was the first thing to compile it —
   `:app:compileDebugUnitTestKotlin` and `:app:testDebugUnitTest` both pass, on the original head
   and again after the rebase onto current `main`.

## Acceptance Criteria

- [x] Android requests carry a `User-Agent` that identifies the app and contains the literal
      `Android` that backend detection keys on
- [x] Header values sanitised so a non-ASCII `Build.MODEL` cannot make every request throw
- [x] Existing installs sending OkHttp's default UA are attributed to mobile without an app release
- [x] A UA-less follow-up request no longer flips an established mobile session back to web
- [x] Backend unit + integration tests cover the app UA, the legacy `okhttp` UA, and the `NULL`
      retention path; the test that documented the `COALESCE` bug now asserts correct behaviour
- [ ] `chat.py` prefers `ChatRequest.language` over `Accept-Language` for session tracking, on both
      the streaming and non-streaming paths, with tests
- [ ] Alembic revision backfills `is_mobile` for historical sessions from the stored `user_agent`;
      rerunnable, and its effect on the last few weeks' numbers recorded in the PR
- [x] `make android-test` green in CI (`UserAgentInterceptorTest` compiles and passes)
- [ ] PR opened, merged, API deployed **before** the app release (deploy order matters — see below)
- [ ] One digest observed post-deploy showing a non-zero mobile count, to confirm end to end

## Rollout Order

Deploy **the API first**. Item 2 makes every Android install already in the field report correctly
on the next digest, so the fix is visible without waiting on Play Store rollout and user updates.
The app release then upgrades those sessions to a descriptive UA and adds `Accept-Language`.
Reversing the order delays the visible fix by however long adoption takes.

## Out of Scope

- **Firebase/GA4 in-app engagement** (screen views, verse taps, retention) — already called out as
  deliberately excluded in `api/reports/weekly_report.py`'s module docstring; needs a separate
  Google Analytics Data API integration.
- **iOS** — no app exists.
- **Splitting "mobile" into "Android app" vs. "mobile browser"** in the report. Both are genuinely
  mobile and the current two-bucket split is now correct. If the product question is specifically
  *app* adoption, that is a follow-up story: the stored `user_agent` distinguishes them, so no new
  schema is needed.

## Related

- `api/reports/weekly_report.py` (the split, and its docstring note that web/mobile depends on the
  client identifying itself), `api/utils/session_tracker.py`, `api/routes/chat.py`
- `android/app/src/main/kotlin/org/voxquieta/app/data/remote/interceptors/UserAgentInterceptor.kt`,
  `.../data/remote/api/ApiClient.kt`, `.../di/NetworkModule.kt`
- `docs/USAGE_TRACKING.md`, `docs/WEEKLY_REPORT.md`
- `scripts/migrations/008_add_sessions_table.sql` — the previous time this digest was wrong because
  of a session-tracking gap (the `sessions` table was missing in production, so the engagement
  queries 500'd; see that migration's header). Same failure mode one layer down: the report is only
  as good as what `track_session` manages to record.
