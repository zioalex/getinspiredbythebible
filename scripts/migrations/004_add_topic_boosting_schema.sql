-- Migration 004: Add verse_topics junction table for topic-based search boosting
-- Date: 2026-02-24
-- PR: BITB-018.3
-- Purpose: Enable topic-based score boosting in semantic/hybrid search
--
-- Prerequisites:
--   - topics table must already exist (created in init.sql)
--   - verses table must already exist
--
-- Safe to run multiple times (idempotent)

-- Create verse_topics junction table
CREATE TABLE IF NOT EXISTS verse_topics (
    verse_id INTEGER REFERENCES verses(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (verse_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_verse_topics_verse ON verse_topics(verse_id);
CREATE INDEX IF NOT EXISTS idx_verse_topics_topic ON verse_topics(topic_id);

-- Seed initial topics (if topics table is empty or missing these entries)
-- These match the TOPIC_KEYWORD_MAP in api/chat/topics.py
INSERT INTO topics (name, description) VALUES
    ('anxiety',     'Worry, stress, fear about the future'),
    ('peace',       'Calm, rest, tranquility, God''s peace'),
    ('forgiveness', 'Mercy, pardon, reconciliation'),
    ('anger',       'Rage, frustration, managing emotions'),
    ('loneliness',  'Isolation, feeling alone, abandoned'),
    ('trust',       'Faith, belief, confidence in God'),
    ('fear',        'Terror, being afraid, finding courage'),
    ('hope',        'Expectation, optimism, future confidence'),
    ('love',        'God''s love, loving others, compassion'),
    ('grief',       'Sorrow, mourning, loss, depression'),
    ('guidance',    'Direction, wisdom, decision-making'),
    ('patience',    'Endurance, waiting, perseverance'),
    ('joy',         'Happiness, gladness, rejoicing, blessings')
ON CONFLICT (name) DO NOTHING;

-- Verify
-- SELECT COUNT(*) FROM topics;              -- Should be >= 13
-- SELECT COUNT(*) FROM verse_topics;        -- 0 initially (populated by curation scripts)
-- \d verse_topics                           -- Should show columns and FK constraints
