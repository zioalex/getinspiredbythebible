-- Migration: Add multilingual translation support (Simplified)
-- Date: 2026-01-25
-- Description: Adds translations table and updates verses table to support multiple Bible translations
-- Note: This migration truncates verses, passages, and topics tables.
--       All Bible data and embeddings will be recreated using the new multilingual model.

-- ============================================================================
-- Step 1: Create translations metadata table
-- ============================================================================

CREATE TABLE IF NOT EXISTS translations (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    language VARCHAR(50) NOT NULL,
    language_code VARCHAR(10) NOT NULL,  -- ISO 639-1 (en, it, de)
    description TEXT,
    source_url TEXT,
    license VARCHAR(100) DEFAULT 'Public Domain',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial translation metadata
INSERT INTO translations (code, name, language, language_code, is_default, description) VALUES
    ('kjv', 'King James Version', 'English', 'en', TRUE, 'Classic English translation from 1611'),
    ('web', 'World English Bible', 'English', 'en', FALSE, 'Modern English, public domain'),
    ('ita1927', 'Riveduta 1927', 'Italian', 'it', FALSE, 'Italian Luzzi translation from 1927'),
    ('deu1912', 'Lutherbibel 1912', 'German', 'de', FALSE, 'Classic German Luther translation')
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Step 2: Clear existing data that needs to be recreated
-- ============================================================================

-- Truncate verses (will be reloaded with translation support)
TRUNCATE TABLE verses CASCADE;

-- Truncate passages (embeddings need to be recreated with new model)
TRUNCATE TABLE passages CASCADE;

-- Truncate topics (embeddings need to be recreated with new model)
TRUNCATE TABLE topics CASCADE;

-- ============================================================================
-- Step 3: Update verses table schema for multilingual support
-- ============================================================================

-- Drop old unique constraint if exists
ALTER TABLE verses DROP CONSTRAINT IF EXISTS unique_verse;

-- Add translation column (no default needed since table is empty)
ALTER TABLE verses
ADD COLUMN IF NOT EXISTS translation VARCHAR(20) NOT NULL DEFAULT 'kjv';

-- Add foreign key constraint
ALTER TABLE verses
DROP CONSTRAINT IF EXISTS fk_verses_translation;

ALTER TABLE verses
ADD CONSTRAINT fk_verses_translation
FOREIGN KEY (translation) REFERENCES translations(code)
ON DELETE CASCADE;

-- Add new unique constraint including translation
ALTER TABLE verses
DROP CONSTRAINT IF EXISTS unique_verse_translation;

ALTER TABLE verses
ADD CONSTRAINT unique_verse_translation
    UNIQUE(book_id, chapter_number, verse_number, translation);

-- ============================================================================
-- Step 4: Add indexes for performance
-- ============================================================================

-- Index for translation queries
CREATE INDEX IF NOT EXISTS idx_verses_translation
ON verses(translation);

-- Composite index for translation + book queries
CREATE INDEX IF NOT EXISTS idx_verses_translation_book
ON verses(translation, book_id);

-- ============================================================================
-- Verification queries (uncomment to run after migration)
-- ============================================================================

-- Verify translations table
-- SELECT * FROM translations ORDER BY is_default DESC, language_code;

-- Verify verse counts by translation (should be empty initially)
-- SELECT translation, COUNT(*) as verse_count
-- FROM verses
-- GROUP BY translation
-- ORDER BY translation;
