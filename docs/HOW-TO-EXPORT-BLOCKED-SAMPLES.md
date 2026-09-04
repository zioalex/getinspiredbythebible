# How to Export Blocked-Message Samples

When the safety system blocks a user message, the backend can write a
privacy-minimal record into the `blocked_message_samples` table so we can
tune the filter against real traffic. This doc covers how the capture is
gated and how to retrieve the rows.

See also: [`api/feedback/blocked_samples.py`](../api/feedback/blocked_samples.py),
[`api/feedback/models.py`](../api/feedback/models.py),
the public [Privacy Policy](../frontend/public/legal/privacy-policy.md).

## What is captured

Each row is one blocked message (or a deduplicated group of identical
blocked messages):

| Column            | Meaning                                                        |
| ----------------- | -------------------------------------------------------------- |
| `id`              | Surrogate primary key.                                         |
| `created_at`      | UTC timestamp the row was written.                             |
| `expires_at`      | TTL — row is purged after this instant.                        |
| `stage`           | Which safety stage blocked: `keyword` or `content_safety`.     |
| `categories`      | Provider categories (JSON list or dict).                       |
| `severity`        | Provider severity score (when available).                      |
| `language`        | Detected ISO language code (when available).                   |
| `message_text`    | The message, **capped** at `BLOCKED_SAMPLE_MAX_CHARS` (500).   |
| `message_sha256`  | Full-message sha256, used for dedup.                           |
| `session_id_hash` | sha256 of the session id (no raw id, IP, account, or UA).      |
| `hit_count`       | Number of times this exact message has been blocked.           |
| `reviewed`        | Operator flag — set to `true` after using the row for tuning.  |

## Privacy guardrails

These are enforced in code, not just by convention:

- No raw IP, user id, or user-agent is ever stored.
- `session_id_hash` is a one-way hash.
- `message_text` is truncated to at most `BLOCKED_SAMPLE_MAX_CHARS` chars.
- Identical messages are deduplicated by sha256; repeats bump `hit_count`
  instead of writing new rows, so a single user cannot be amplified.
- Rows older than `BLOCKED_SAMPLE_RETENTION_DAYS` (default **30**) are
  deleted on app startup.
- Capture is **off by default**. Operators opt in per environment with
  `BLOCKED_SAMPLE_CAPTURE_ENABLED=true`.

## Enabling capture (operator)

Set these on the backend deployment:

```bash
BLOCKED_SAMPLE_CAPTURE_ENABLED=true     # default false
BLOCKED_SAMPLE_RETENTION_DAYS=30        # default 30
BLOCKED_SAMPLE_MAX_CHARS=500            # default 500
```

The table is created by Alembic revision `r0001` (BITB-090: schema creation
is Alembic's job, not the app's) — run `alembic upgrade head` if it's missing.

## Exporting rows

The exporter is **read-only** and connects to the same database via
`DATABASE_URL` as the API.

### With make

```bash
# Latest 100 rows as JSON to stdout
DATABASE_URL=postgresql://... make export-blocked-samples ARGS="--limit 100"

# Keyword-stage blocks since 2026-05-01, CSV to a file
DATABASE_URL=postgresql://... make export-blocked-samples \
    ARGS="--stage keyword --since 2026-05-01 --format csv --output keyword.csv"

# Italian-language blocks not yet reviewed
DATABASE_URL=postgresql://... make export-blocked-samples \
    ARGS="--language it --unreviewed"
```

### Directly

```bash
DATABASE_URL=postgresql://... \
    python scripts/export_blocked_samples.py --help
```

Filters:

| Flag                       | Meaning                                            |
| -------------------------- | -------------------------------------------------- |
| `--stage <name>`           | `keyword`, `content_safety`, …                     |
| `--language <iso>`         | e.g. `en`, `it`, `ar`.                             |
| `--since YYYY-MM-DD`       | Inclusive lower bound on `created_at`.             |
| `--until YYYY-MM-DD`       | Exclusive upper bound on `created_at`.             |
| `--reviewed` / `--unreviewed` | Filter by the `reviewed` flag.                  |
| `--limit N`                | Max rows.                                          |
| `--format json\|csv`       | Output format (default JSON).                      |
| `--output FILE`            | Write to file instead of stdout.                   |

## Marking rows as reviewed

After a row has been used for tuning, set `reviewed = true` so future
exports can skip it with `--unreviewed`. There's no admin endpoint —
do it from the database client of your choice:

```sql
UPDATE blocked_message_samples
SET reviewed = true
WHERE id IN (1, 2, 3);
```

## Operational notes

- The exporter does only `SELECT` queries. It will not modify rows or
  trigger TTL purges.
- Expired rows are deleted by a `pg_cron` job that runs daily at 03:15
  UTC (`scripts/migrations/005_schedule_blocked_samples_purge.sql`).
  The app-side startup purge in `api/main.py` is kept as a backstop so
  rows are also cleaned up after a deploy or restart.
- To force a purge between scheduled runs:

  ```sql
  DELETE FROM blocked_message_samples WHERE expires_at < now();
  ```

- The table holds at most one row per distinct message within the
  retention window, so volume is bounded by the variety of blocked
  messages, not by traffic.

## Enabling the pg_cron job (one-time, operator)

1. `deployment/main.tf` already adds `pg_cron` to the `azure.extensions`
   parameter and points `cron.database_name` at the app database.
   Apply the Terraform plan and restart the Postgres flexible server
   when prompted by Azure.
2. Run `scripts/migrations/005_schedule_blocked_samples_purge.sql` as
   a superuser to register the schedule. The migration is idempotent.
3. Verify with:

   ```sql
   SELECT jobname, schedule FROM cron.job
   WHERE jobname = 'purge-blocked-message-samples';
   ```
