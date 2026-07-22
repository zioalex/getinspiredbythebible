-- Migration 009: Shared rate-limit counters (BITB-061 phase 3)
-- Date: 2026-07-13
-- Purpose: api/utils/rate_limiter.py was an in-memory, per-process limiter.
--   Production runs up to 2 replicas, so IP/session-per-minute limits were
--   effectively 2x the configured value, and every deploy/restart reset all
--   counters -- including the 10-message session lifetime cap that is meant
--   to survive the whole session. Moving the counters into Postgres (already
--   the one datastore every replica shares) closes both gaps.
--
-- Two tables because the semantics genuinely differ:
--   - rate_limit_hits: sliding-window event log (one row per allowed
--     request), used for the per-minute IP and per-session limits. Rows are
--     short-lived; see migration 010 for the pg_cron purge.
--   - rate_limit_sessions: durable per-session lifetime counter. Must survive
--     window cleanup and deploys -- that durability is the whole point of
--     this migration.
--
-- Safe to run multiple times (idempotent).

CREATE TABLE IF NOT EXISTS rate_limit_hits (
    id         BIGSERIAL PRIMARY KEY,
    -- 'ip:<addr>' or 'session:<id>' -- both share this table.
    limit_key  TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Supports both the windowed COUNT (key, recent-first) and the cron purge
-- (age-only scan).
CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_key_time
    ON rate_limit_hits (limit_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_created_at
    ON rate_limit_hits (created_at);

CREATE TABLE IF NOT EXISTS rate_limit_sessions (
    session_id     TEXT PRIMARY KEY,
    total_requests INTEGER NOT NULL DEFAULT 0,
    last_seen      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_sessions_last_seen
    ON rate_limit_sessions (last_seen);
