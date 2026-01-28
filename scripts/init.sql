-- PostgreSQL initialization script
-- Creates the pgvector extension and sets up the database schema

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable full-text search capabilities
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- Create translations table
-- ============================================================================

CREATE TABLE IF NOT EXISTS translations (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    language VARCHAR(50) NOT NULL,
    language_code VARCHAR(10) NOT NULL,
    description TEXT,
    source_url TEXT,
    license VARCHAR(100) DEFAULT 'Public Domain',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default translations
-- Keep in sync with scripts/translations.py - run: python -c "from translations import generate_translations_sql; print(generate_translations_sql())"
INSERT INTO translations (code, name, language, language_code, is_default, description) VALUES
    ('kjv', 'King James Version', 'English', 'en', TRUE, 'Classic English translation from 1611'),
    ('web', 'World English Bible', 'English', 'en', FALSE, 'Modern English, public domain'),
    ('ita1927', 'Riveduta 1927', 'Italian', 'it', FALSE, 'Italian Luzzi translation from 1927'),
    ('schlachter', 'Schlachter 1951', 'German', 'de', FALSE, 'German Schlachter translation from 1951')
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Create books table
-- ============================================================================

CREATE TABLE IF NOT EXISTS books (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    abbreviation VARCHAR(10) NOT NULL,
    testament VARCHAR(20) NOT NULL,
    position INTEGER NOT NULL
);

-- ============================================================================
-- Create chapters table
-- ============================================================================

CREATE TABLE IF NOT EXISTS chapters (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    CONSTRAINT unique_chapter UNIQUE(book_id, number)
);

-- ============================================================================
-- Create verses table with translation support
-- ============================================================================

CREATE TABLE IF NOT EXISTS verses (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    verse_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    translation VARCHAR(20) NOT NULL DEFAULT 'kjv' REFERENCES translations(code) ON DELETE CASCADE,
    embedding vector(1024),
    CONSTRAINT unique_verse_translation UNIQUE(book_id, chapter_number, verse_number, translation)
);

-- Create indexes for verses
CREATE INDEX IF NOT EXISTS idx_verses_translation ON verses(translation);
CREATE INDEX IF NOT EXISTS idx_verses_translation_book ON verses(translation, book_id);
CREATE INDEX IF NOT EXISTS idx_verse_embedding ON verses USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Create passages table
-- ============================================================================

CREATE TABLE IF NOT EXISTS passages (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    start_book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    start_chapter INTEGER NOT NULL,
    start_verse INTEGER NOT NULL,
    end_chapter INTEGER NOT NULL,
    end_verse INTEGER NOT NULL,
    text TEXT NOT NULL,
    topics VARCHAR(500),
    embedding vector(1024)
);

CREATE INDEX IF NOT EXISTS idx_passage_embedding ON passages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Create topics table
-- ============================================================================

CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    parent_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    embedding vector(1024)
);

-- ============================================================================
-- Create feedback table (user ratings on AI responses)
-- ============================================================================

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_id UUID NOT NULL,
    session_id VARCHAR(255),
    rating VARCHAR(10) NOT NULL CHECK (rating IN ('positive', 'negative')),
    comment TEXT,
    user_message TEXT,
    assistant_response TEXT,
    verses_cited JSONB,
    model_used VARCHAR(100),
    response_time_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);
CREATE INDEX IF NOT EXISTS idx_feedback_message_id ON feedback(message_id);

-- ============================================================================
-- Create contact_submissions table (general contact form)
-- ============================================================================

CREATE TABLE IF NOT EXISTS contact_submissions (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    email VARCHAR(255),
    subject VARCHAR(50) NOT NULL CHECK (subject IN ('bug', 'feature', 'feedback', 'other')),
    message TEXT NOT NULL,
    session_id VARCHAR(255),
    user_agent TEXT,
    status VARCHAR(20) DEFAULT 'new' CHECK (status IN ('new', 'read', 'replied', 'resolved'))
);

CREATE INDEX IF NOT EXISTS idx_contact_created_at ON contact_submissions(created_at);
CREATE INDEX IF NOT EXISTS idx_contact_status ON contact_submissions(status);
