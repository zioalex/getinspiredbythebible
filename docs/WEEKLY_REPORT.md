# Weekly Activity Report

Automated weekly digest email covering feedback, contact submissions, and
session engagement over the last 7 days. Covers both the web app and the
Android app, since both hit the same API.

## Architecture

```
GitHub Actions cron (Sunday 18:00 UTC)
  .github/workflows/weekly-report.yml
        │  POST /api/v1/admin/weekly-report?dry_run=false
        │  Header: X-Monitor-Probe-Secret: <shared secret>
        ▼
Backend (Azure Container Apps)
  api/routes/admin.py → trigger_weekly_report
        │
        ├─ api/reports/weekly_report.py → build_weekly_report(db)
        │    Queries Postgres: feedback, contact_submissions, sessions
        │
        └─ api/utils/email_service.py → send_email(...)
             SMTP2GO → settings.weekly_report_recipient
```

Postgres cannot send email, so the schedule lives in GitHub Actions rather
than `pg_cron`; the backend (which already has DB + SMTP configured) does the
actual work.

The endpoint is internal (`include_in_schema=False`) and authenticated with
the same shared-secret probe header the production monitor uses
(`utils/monitor_probe.py`). It is fail-closed: if the secret is unset on the
server, every request gets 401.

## What's in the digest

Built by `build_weekly_report` (`api/reports/weekly_report.py`):

| Section | Source table | Contents |
| --- | --- | --- |
| Feedback | `feedback` | totals, positive/negative ratio, recent negative comments, week-over-week delta |
| Contact | `contact_submissions` | totals grouped by subject |
| Engagement | `sessions` | active/new sessions, messages, web vs. mobile split, top languages, week-over-week delta |

If the `sessions` table (or one of its analytics columns) is missing, the
digest degrades gracefully to zero engagement stats instead of failing — see
[Incident history](#incident-history) below.

## Configuration

### GitHub repository (Actions)

| Kind | Name | Purpose |
| --- | --- | --- |
| Secret | `MONITOR_PROBE_SECRET` | Shared secret; must match `settings.monitor_probe_secret` in the deployed backend (same one `prod-monitor.yml` uses) |
| Variable | `BACKEND_URL` | Backend base URL; the workflow falls back to the hardcoded production URL when unset |

### Backend settings (`api/config.py`)

| Setting | Default | Purpose |
| --- | --- | --- |
| `monitor_probe_secret` | unset (fail-closed) | Authenticates the probe header |
| `weekly_report_recipient` | `support@voxquieta.org` | Digest recipient |
| SMTP2GO settings | — | Used by `email_service` to actually send |

## Running it manually

**Actions → Weekly Report → Run workflow.** Set `dry_run=true` to compute the
digest and return it as JSON without sending an email — useful to validate
config after a deploy.

Or directly with curl:

```bash
curl -X POST \
  "https://<backend>/api/v1/admin/weekly-report?dry_run=true" \
  -H "X-Monitor-Probe-Secret: $MONITOR_PROBE_SECRET" | jq .
```

## Troubleshooting

The workflow prints the HTTP status and the response body on failure, and
writes a result table to the run's step summary.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Job fails before curl: "MONITOR_PROBE_SECRET secret is not set" | Repo secret missing | Add the secret under repo Settings → Secrets → Actions |
| HTTP 401 | Secret mismatch with `settings.monitor_probe_secret`, or unset on the backend | Align the repo secret with the deployed backend config |
| HTTP 500 | Unhandled backend exception | Check Container Apps logs (`az containerapp logs show` or Log Analytics); see incident history below |
| HTTP 000 / 502 / 503 / 504 | Backend unreachable / cold start / gateway | The workflow retries these 3× with backoff; persistent failures mean the backend is down — check `prod-monitor` |
| `email_sent != true` | SMTP disabled or misconfigured in the backend | Verify SMTP2GO settings/key in the deployed environment |
| Engagement section all zeros | `sessions` table missing or empty | Ensure migration `008_add_sessions_table.sql` has been applied |

## Incident history

**2026-06 → 2026-07: every run failed with HTTP 500.** Two stacked causes:

1. The production database predates the `sessions` table — it was only
   defined in `scripts/init.sql`, which runs solely on fresh DB
   initialization, and was never shipped as a migration. The digest's
   engagement queries (`FROM sessions`) failed with `UndefinedTable`.
   Fixed by `scripts/migrations/008_add_sessions_table.sql`.
2. The first fallback fix (PR #811) caught that error but did not roll back
   the aborted Postgres transaction, so the next query on the same session
   died with `InFailedSQLTransaction` — still a 500. Fixed by an explicit
   `db.rollback()` in the fallback path of `build_weekly_report`, with a
   real-Postgres regression test in
   `api/tests/test_weekly_report_integration.py` (mock-based tests cannot
   reproduce transaction state).

The workflow originally used `curl -f`, which discards the response body and
made every failure look identical; it now prints status + body and retries
transient errors.

## Tests

```bash
cd api
pytest tests/test_weekly_report.py               # unit (mocked DB)
pytest tests/test_weekly_report_integration.py   # real Postgres; skips if unreachable
pytest tests/test_admin_report.py                # endpoint auth/wiring
```

The integration tests run in CI (the backend-tests job provides a Postgres
service container) and exercise both the missing-table fallback and the
migration DDL.
