# BITB-041: Verse Detail Never Loads — Add Timeout, Error/Retry, and Monitoring

**Status:** 🎯 Todo
**Priority:** P1 (High) — broken feature with no error path and a monitoring blind spot
**Size:** M (1-2 days)
**Created:** 2026-06-04

## User Story

As a user who taps a Bible verse, I want the verse text to either load promptly or
fail with a clear, retryable error, so that I never stare at a garbled placeholder
(`////`) and a spinner that never stops — and as the operator, I want this failure
to be monitored and alerted so I learn about it before users report it.

## Problem

Tapping a verse in **Italian (ITA1927)** sometimes shows a `////` placeholder and a
spinner that never resolves and never errors. **English and German load.** (See first
screenshot in the bug report.) When this load failure happens it also leaves the
header in English — but the English-header defect (**BITB-040**) is a separate, general
bug that occurs across all non-English locales even when loading succeeds. This story
covers the **load failure, resilience, and monitoring**; BITB-040 covers the header.

### Root causes

**Android — no timeout, empty text rendered, no terminal state:**

- `ChatViewModel.loadChapter()` has **no timeout**
  (`android/app/src/main/kotlin/.../viewmodels/ChatViewModel.kt:811-828`). If
  `bibleApiService.getChapter()` hangs, the state stays `Loading` forever — it never
  reaches `Success` or `Error`, so the sheet spins indefinitely.
- While loading, `buildSyntheticVerse()` sets `text = ""`
  (`ChatMessageItem.kt:753-770`), and the sheet renders `"\"${verse.text}\""`
  (`VerseDetailBottomSheet.kt:135`) → empty/garbled quoted content (the `////`).
- The `Error` branch (`VerseDetailBottomSheet.kt:166-180`) is only reached if the
  call throws; a silent hang bypasses it entirely.

**Backend — no query timeout, failures aren't alertable:**

- `ScriptureRepository.get_verse` / chapter queries have **no per-query timeout**
  (`api/scripture/repository.py:109-136`); a slow/stalled PostgreSQL call blocks
  instead of failing fast. (Health checks *do* use `asyncio.wait_for`, so the
  service looks healthy while verse queries hang — `api/routes/health.py:49-76`.)
- The chapter route has no error handling for repo exceptions
  (`api/routes/scripture.py:122-167`) — a failure becomes a generic 500.

**Italian-specific trigger (must be diagnosed):** since en/de work and it/ITA1927
fails, confirm whether the `////` is (a) the Android empty-synthetic-text rendering
or (b) **actual ITA1927 source data** (missing/placeholder verses) returned by the
backend. Inspect the `verses` rows for the affected references in `ita1927` and
repair the data load if corrupt (`scripts/load_bible.py`, `data/bible/`).

### Monitoring gap

`deployment/monitoring.tf` alerts on backend availability, container restarts, and
error-shaped logs only. There is **no alert** on verse/chapter fetch latency or
error rate. Metrics exist (`db.query.duration_ms` histogram, `db.slow_queries`
counter — `api/utils/metrics.py`) but nothing fires on them. A hung query that
returns a bad 200 or 500 is invisible to current uptime checks.

## Proposed Changes

### 1. Android resilience
- Wrap `loadChapter()` in `withTimeoutOrNull(...)` (e.g. 10s); on timeout set
  `ChapterSheetState.Error` with a friendly, **retryable** message
  (`mapExceptionToMessage` already maps `SocketTimeoutException`).
- Never render empty/garbled verse text: while loading show a loading state in the
  text area (not empty quotes); on error show the error + a **Retry** action that
  re-invokes `loadChapter()`.
- Ensure the OkHttp/Retrofit client has a sane call timeout so the network layer
  also fails fast.

### 2. Backend resilience
- Add a per-query timeout (`asyncio.wait_for`) to the verse/chapter repository
  reads; on timeout return **504** (not a hang) so the client and alerts can react.
- Add error handling on the chapter route so repo failures return a clear status,
  not a bare 500.
- Guard against empty/placeholder verse text (e.g. `////`) — treat as a data error
  rather than serving it as a valid verse.

### 3. Monitoring & alerting (the "should be monitored and alerted" requirement)
- Instrument verse/chapter fetch with a success/empty-result and latency signal
  (reuse the existing `get_verse` span and `db.query.duration_ms` histogram,
  tagged by operation + translation).
- Add a Terraform alert in `deployment/monitoring.tf` for verse/chapter fetch
  **error rate** and **p95 latency / timeout count** (e.g. p95 > 2s sustained 5m,
  or any 504s), notifying the existing email action group.
- Enable PostgreSQL slow-query logging threshold already configured
  (`slow_query_threshold_ms = 100`, `api/config.py:127`) to surface slow verses.

### 4. Diagnose & repair Italian data
- Verify ITA1927 rows for the reported references; if `////`/empty, fix the loader
  and reload (`scripts/load_bible.py`). Add a data-integrity check for empty verse
  text per translation.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/.../viewmodels/ChatViewModel.kt` | `withTimeoutOrNull` around `loadChapter`; map timeout → retryable `Error` |
| `android/app/src/main/kotlin/.../components/VerseDetailBottomSheet.kt` | Loading state for text area; Error + Retry action; stop rendering empty quotes |
| `android/app/src/main/kotlin/.../components/ChatMessageItem.kt` | Don't surface empty synthetic text as a "loaded" verse |
| `api/scripture/repository.py` | Per-query timeout on verse/chapter reads → 504 |
| `api/routes/scripture.py` | Error handling + empty-text guard on chapter/verse routes |
| `deployment/monitoring.tf` | Alert on verse/chapter fetch error-rate and p95 latency/timeouts |
| `scripts/load_bible.py` / `data/bible/` | Fix/reload ITA1927 data if corrupt; add empty-text integrity check |

## Test Gaps to Close

The suite let this ship because of **integration/resilience gaps** (the flow's
happy path is unit-tested with mocks; failures and the UI are not):

- Android `ChatViewModelTest.kt:718-860` tests `loadChapter` only for `IOException` —
  no `SocketTimeoutException`, no **timeout/hang** simulation.
- No Compose UI test for `VerseDetailBottomSheet` (loading/error/retry untested).
- Backend `test_routes_main_coverage.py:928-974` covers only 200/404 for chapter —
  no timeout/DB-error/empty-text cases.

Add:

- [ ] Android: `loadChapter` test where the API stalls past the timeout → state
      becomes `Error` (not stuck `Loading`); test `SocketTimeoutException` mapping.
- [ ] Android Compose UI test (BITB-034 tier): sheet shows loading, then error +
      working **Retry**; empty text is never shown as a quoted verse.
- [ ] Backend: chapter/verse route tests for repo timeout → 504, DB error, and
      empty/placeholder verse text → error (not a 200 with `////`).

## Acceptance Criteria

- [ ] When the chapter fetch is slow/unreachable, the sheet shows a clear error with
      a working **Retry** within a bounded time — never an infinite spinner.
- [ ] The verse text area never displays `////` or empty quotes; it shows loading,
      then the verse or an error.
- [ ] Backend verse/chapter reads time out to **504** instead of hanging.
- [ ] Italian (ITA1927) verse detail loads correctly for the reported references; if
      the data was corrupt it is repaired and an integrity check guards against empty text.
- [ ] A monitoring alert fires on elevated verse/chapter fetch error-rate or p95
      latency/timeouts, notifying the existing action group.
- [ ] New Android and backend tests cover timeout, error, retry, and empty-text paths.

## Out of Scope

- The localized-book-name header fix — tracked in **BITB-040** (shared root cause).
- Reworking semantic search or the navigation graph.

## Related

- **BITB-040** — localized book name in the same sheet (independent, general bug)
- BITB-013 / BITB-021 — performance metrics + dashboard (reuse the metrics/alert plumbing)
- BITB-034 — Android Compose UI test tier (use it for the sheet tests)

## Assignee

fullstack-expert
