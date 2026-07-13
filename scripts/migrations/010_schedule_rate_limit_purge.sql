-- Migration 010: Schedule pg_cron purge for shared rate-limit tables (BITB-061)
-- Date: 2026-07-13
-- Purpose: rate_limit_hits/rate_limit_sessions (migration 009) grow forever
--          without a cleanup job. Follows the same pg_cron pattern as
--          migration 005 (blocked-sample purge).
--
-- Prerequisites (operator-level, one-time -- same as migration 005):
--   1. Add `pg_cron` to the `azure.extensions` server parameter
--      (see deployment/main.tf). Restart the Postgres flexible server.
--   2. Set the `cron.database_name` server parameter to the app database
--      (e.g. `bibledb`) so cron jobs run against the right DB. Restart.
--   3. Run this migration as a superuser (cron schema is owned by
--      `azure_pg_admin` on Azure flexible server).
--
-- Behaviour:
--   - rate_limit_hits rows only need to live one sliding window (60s by
--     default: rate_limit_requests_per_minute / rate_limit_requests_per_
--     session_minute); purge generously and keep 1 hour so a slow purge run
--     never races a live window check.
--   - rate_limit_sessions rows expire on idle past
--     `rate_limit_session_ttl_seconds` (default 3600s = 1 hour). The purge
--     horizon below is hardcoded to match that default because pg_cron
--     cannot read application config -- if that setting is ever changed,
--     this file must be updated to match (keep the purge horizon >= the app
--     TTL so cron never deletes a counter the app still considers live).
--
-- Idempotency:
--   - `CREATE EXTENSION IF NOT EXISTS` is safe to re-run.
--   - `cron.unschedule` is wrapped in a DO block so re-running this
--     migration just replaces the schedule without errors.

CREATE EXTENSION IF NOT EXISTS pg_cron;

DO $$
BEGIN
    PERFORM cron.unschedule('purge-rate-limit-hits')
    FROM cron.job
    WHERE jobname = 'purge-rate-limit-hits';

    PERFORM cron.unschedule('purge-rate-limit-sessions')
    FROM cron.job
    WHERE jobname = 'purge-rate-limit-sessions';
END
$$;

SELECT cron.schedule(
    'purge-rate-limit-hits',
    '*/10 * * * *',
    $cmd$DELETE FROM rate_limit_hits WHERE created_at < now() - interval '1 hour'$cmd$
);

SELECT cron.schedule(
    'purge-rate-limit-sessions',
    '15 * * * *',
    $cmd$DELETE FROM rate_limit_sessions WHERE last_seen < now() - interval '1 hour'$cmd$
);

-- Verify
SELECT jobid, jobname, schedule, command
FROM cron.job
WHERE jobname IN ('purge-rate-limit-hits', 'purge-rate-limit-sessions');
