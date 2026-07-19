-- Migration 005: Schedule daily TTL purge for blocked_message_samples
-- Date: 2026-05-19
-- Purpose: Replace startup-only purge with a pg_cron-driven daily DELETE
--          so expired rows are reclaimed even when the API container does
--          not restart for long stretches.
--
-- Prerequisites (operator-level, one-time):
--   1. Add `pg_cron` to the `azure.extensions` server parameter
--      (see deployment/main.tf). Restart the Postgres flexible server.
--   2. Set the `cron.database_name` server parameter to the app database
--      (e.g. `bibledb`) so cron jobs run against the right DB. Restart.
--   3. Run this migration as a superuser (cron schema is owned by
--      `azure_pg_admin` on Azure flexible server).
--
-- Behaviour:
--   - The job runs daily at 03:15 UTC and deletes any row whose
--     `expires_at` is in the past. Rows live up to
--     `BLOCKED_SAMPLE_RETENTION_DAYS` (default 30) past creation.
--   - The application-side startup purge in api/main.py is kept as a
--     belt-and-braces backstop; both can run safely (DELETE is idempotent).
--
-- Idempotency:
--   - `CREATE EXTENSION IF NOT EXISTS` is safe to re-run.
--   - `cron.unschedule` is wrapped in a DO block so re-running this
--     migration just replaces the schedule without errors.
--
-- Local/CI Postgres (pgvector/pgvector image, docker-compose.yml) doesn't have
-- pg_cron installed and can't get it without a custom image. Unlike a missing
-- table, `CREATE EXTENSION pg_cron` fails outright when the extension isn't
-- installed, and any statement referencing the `cron` schema then fails to
-- even parse -- so the whole body below is gated on pg_available_extensions
-- and skips with a NOTICE when pg_cron isn't there, instead of taking the
-- migration runner down on every non-prod environment.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_cron';

        -- Drop any prior schedule with the same name before re-creating, so
        -- this migration can be re-applied to change the cadence without
        -- leaving duplicate jobs behind.
        PERFORM cron.unschedule('purge-blocked-message-samples')
        FROM cron.job
        WHERE jobname = 'purge-blocked-message-samples';

        PERFORM cron.schedule(
            'purge-blocked-message-samples',
            '15 3 * * *',
            $cron$DELETE FROM blocked_message_samples WHERE expires_at < now()$cron$
        );

        RAISE NOTICE 'Scheduled pg_cron job purge-blocked-message-samples (15 3 * * *)';
    ELSE
        RAISE NOTICE 'pg_cron extension not available -- skipping purge-blocked-message-samples schedule (expected on local/CI Postgres; api/main.py''s startup purge still runs)';
    END IF;
END
$$;
