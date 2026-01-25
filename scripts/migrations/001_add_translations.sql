-- Migration: Add multilingual translation support
-- Date: 2026-01-25
-- Description: Adds translations table and updates verses table to support multiple Bible translations

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
-- Step 2: Add translation column to verses table
-- ============================================================================

-- Add column with default value
ALTER TABLE verses
ADD COLUMN IF NOT EXISTS translation VARCHAR(20) DEFAULT 'kjv';

-- Backfill existing verses with 'kjv'
UPDATE verses SET translation = 'kjv' WHERE translation IS NULL;

-- Make translation NOT NULL after backfill
ALTER TABLE verses ALTER COLUMN translation SET NOT NULL;

-- Add foreign key constraint
ALTER TABLE verses
DROP CONSTRAINT IF EXISTS fk_verses_translation;

ALTER TABLE verses
ADD CONSTRAINT fk_verses_translation
FOREIGN KEY (translation) REFERENCES translations(code)
ON DELETE CASCADE;

-- ============================================================================
-- Step 3: Update unique constraints
-- ============================================================================

-- Drop old unique constraint (book_id, chapter_number, verse_number)
ALTER TABLE verses DROP CONSTRAINT IF EXISTS unique_verse;

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

-- Composite index for translation + embedding queries (semantic search)
CREATE INDEX IF NOT EXISTS idx_verses_translation_embedding
ON verses(translation)
WHERE embedding IS NOT NULL;

-- Index for book queries within a translation
CREATE INDEX IF NOT EXISTS idx_verses_translation_book
ON verses(translation, book_id);

-- ============================================================================
-- Verification queries
-- ============================================================================

-- Verify translations table
-- SELECT * FROM translations ORDER BY is_default DESC, language_code;

-- Verify verse counts by translation
-- SELECT translation, COUNT(*) as verse_count
-- FROM verses
-- GROUP BY translation
-- ORDER BY translation;

-- Verify embedding coverage by translation
-- SELECT translation,
--        COUNT(*) as total_verses,
--        COUNT(embedding) as verses_with_embeddings,
--        ROUND(100.0 * COUNT(embedding) / COUNT(*), 2) as coverage_percent
-- FROM verses
-- GROUP BY translation
-- ORDER BY translation;
