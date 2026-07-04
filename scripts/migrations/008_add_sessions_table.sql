-- Migration 008: Add sessions table for usage tracking (DAU/MAU)
-- Date: 2026-07-04
-- Purpose: The sessions table was only defined in scripts/init.sql, which runs
--   solely on fresh database initialization. Databases created before the
--   table was introduced (including production) never got it, which silently
--   broke per-request session tracking (utils/session_tracker.py) and made the
--   weekly digest engagement queries fail (reports/weekly_report.py), causing
--   the Weekly Report workflow to receive HTTP 500.
--
-- DDL is copied verbatim from scripts/init.sql so fresh and migrated databases
-- end up identical.
--
-- Safe to run multiple times (idempotent)

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_token VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    language VARCHAR(10),
    user_agent TEXT,
    is_mobile BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity);
