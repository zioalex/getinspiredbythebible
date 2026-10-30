# BITB-247: Read-Aloud Telemetry — Attempts, Completions and Failures (Web + Android)

**Status:** 🚧 In Progress (spec confirmed 2026-10-27)
**Priority:** P2
**Size:** M
**Created:** 2026-10-27
**Follow-up of:** BITB-241 (PR #1203); widened on 2026-10-27 at the owner's request: "visibility on how many
users try the play button, how many fail and how many succeed", to decide on a fallback voice
(Azure Speech vs in-page Piper).

## Today

- **Web:** `POST /api/v1/client-events` (`api/main.py`) accepts only `tts_started` and
  `tts_unavailable`, with the locale, and adds them to the OpenTelemetry counter
  `client.tts_events_total` in Azure Monitor. No dashboard shows it.
- **Android:** `AnalyticsHelper` sends `tts_started` and `tts_unavailable` to Firebase only.
- **Weekly report:** `api/reports/weekly_report.py` reads Postgres only, so it can see neither source.
- **Not recorded anywhere:** success (read to the end) and failure (engine never started, or errored
  mid-reading).

## Decisions (2026-10-27)

| Question | Decision |
|---|---|
| Detail per event | Locale plus a **coarse browser family and OS family**, from two fixed lists computed on the client. No user-agent string, IP or IDs. |
| Events | Full funnel: `tts_started`, `tts_completed`, `tts_start_failed`, `tts_error`, `tts_unavailable`. Web and Android. |

## Functional requirements

1. **Event schema.** `POST /api/v1/client-events` accepts:

   | Field | Allowed values | If missing or unknown |
   |---|---|---|
   | `event` | `tts_started`, `tts_completed`, `tts_start_failed`, `tts_error`, `tts_unavailable` | — |
   | `locale` | existing normalization | — |
   | `platform` | `web`, `android` | `web` |
   | `browser` | `chrome`, `firefox`, `safari`, `edge`, `samsung`, `app`, `other` | `other` |
   | `os` | `android`, `ios`, `linux`, `windows`, `macos`, `other` | `other` |

   - Unknown events and extra fields still return 422.
   - The OTel counter gains the new attributes, all with bounded cardinality.
   - **Daily aggregate:** each event also increments a row in a new table
     `tts_event_daily (day, event, locale, platform, browser, os, count)` with an atomic upsert. A new
     Alembic revision follows `docs/MIGRATION_GUIDELINES.md`.
2. **Web client** (`frontend/src/lib/clientEvents.ts`, `speech.ts`, `ListenButton.tsx`):
   - **Browser and OS family:** derive both from `navigator.userAgentData` or the user-agent string,
     inside the browser, as enums only. "Firefox on iOS" counts as `firefox` + `ios`.
   - **When each event is sent:**
     - `tts_completed`: the last chunk ended.
     - `tts_start_failed`: the BITB-241/248 give-up fired.
     - `tts_error`: `onerror` after the reading had started.
     - `tts_started` and `tts_unavailable`: unchanged.
   - **Limits:** at most one of each event per answer. Resume does not resend `tts_started`.
3. **Android client** (`ChatViewModel.kt`, `SpeechEngine.kt`, `AnalyticsHelper.kt`):
   - **Firebase:** add `tts_completed`, `tts_start_failed` (no `onStart` within the same 3 s watchdog
     idea, *or* `speak()` refused) and `tts_error` (`UtteranceProgressListener.onError`), next to the
     existing events.
   - **Backend:** also POST the same events to `/api/v1/client-events` with `platform=android`,
     `browser=app`, `os=android`, using the existing API client, fire-and-forget and never blocking
     speech.
4. **Reporting:**
   - **Weekly report:** a "Read aloud" section with 7-day totals per event, the completion rate
     (`completed / started`), the failure rate (`(start_failed + error) / started`), and the top 3
     browser/OS pairs by failures. It reads `tts_event_daily`.
   - **Workbook:** a tile in `deployment/azure-monitor/workbook-performance-dashboard.json` querying
     `client.tts_events_total` by event, and by browser/OS for failures.
5. **Privacy policy:** one sentence in all 11 `frontend/public/legal/privacy-policy*.md` files: read-aloud
   usage is counted anonymously by language, browser family and OS family. Last-updated date bumped.

## Non-functional requirements

- No message text, voice names, user agent, IP or identifiers anywhere.
- The endpoint stays rate-limited, and the aggregate keeps cardinality bounded (enums only).
- Telemetry failures never affect playback.

## Acceptance criteria

- [ ] Backend:
  - The endpoint accepts the new events and fields, normalizes unknown values to `other`, and still
    returns 422 for unknown events or extra fields.
  - The counter attributes and the daily upsert are tested.
  - The migration round-trips (upgrade, then downgrade).
- [ ] Web: each event fires once at the right moment (Vitest with the speech mock), and the browser/OS
      family is detected for Chrome, Firefox, Safari, Edge, Samsung, iOS Firefox and Linux Firefox
      user agents
- [ ] Android: the new Firebase events plus the backend POST (ViewModel/engine tests with fakes), and
      the POST never blocks or crashes speech
- [ ] Weekly report "Read aloud" section, tested with seeded rows; workbook tile added
- [ ] Privacy policy sentence in 11 locales
- [ ] Owner: after deploy, the workbook and weekly report show non-zero counts

## Out of scope

- Fallback voices (Azure Speech or Piper): decided after this data exists
- Firebase/GA4 Android engagement beyond these events
