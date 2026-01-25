# 🚀 Next Steps - Multilingual Bible Support

**Date**: 2026-01-25
**Status**: Phase 1-6 Complete (40% done) ✅
**Branch**: `multiple_bible`

---

## ⚠️ IMPORTANT: Database Schema Update Required

**If you have an existing database**, you MUST update the schema before using this version.

**Quick fix for existing users**:

```bash
# Stop services
docker-compose down

# Remove old database volume (WARNING: This deletes all data!)
docker volume rm getinspiredbythebible_postgres_data

# Start fresh with new schema
docker-compose up -d
```

The new schema includes:

- `translations` table for multilingual support
- `translation` column in `verses` table
- Updated to 1024-dimension embeddings (mxbai-embed-large)

**See Step 2 below for alternative migration options.**

---

## ✅ What's Been Done (Autonomous Implementation)

I've completed the core infrastructure for multilingual Bible support:

### Completed

1. ✅ SQLAlchemy models with Translation support
2. ✅ Configuration updated for multilingual model (mxbai-embed-large)
3. ✅ Translation configurations (Italian/German book mappings)
4. ✅ Complete rewrite of `load_bible.py` with CLI support
5. ✅ Comprehensive tests (41 passing)
6. ✅ All changes committed to `multiple_bible` branch

### Files Created

- `scripts/translations.py` - Translation configs & book name mappings
- `api/tests/test_translations.py` - Translation configuration tests
- `api/tests/test_multilingual_integration.py` - Integration tests
- `TEST_COVERAGE.md` - Test documentation
- `MULTILINGUAL_PROGRESS.md` - Detailed progress tracking
- `NEXT_STEPS.md` - This file!

### Files Modified

- `api/config.py` - Switched to mxbai-embed-large (1024 dim)
- `api/scripture/models.py` - Added Translation model
- `scripts/load_bible.py` - Complete rewrite for multilingual
- `.env.example` - Updated embedding model defaults
- `docker-compose.yml` - Updated to mxbai-embed-large

---

## 📋 What You Need to Do Next

### Step 1: Update Environment Variables

The multilingual embedding model is now configured automatically!

**If using Docker**:

- The model will be pulled automatically when you run `docker-compose up`
- No manual action needed - `init-ollama.sh` will download `mxbai-embed-large`

**If running locally**:

```bash
# Update your .env file (or copy from .env.example)
EMBEDDING_MODEL=mxbai-embed-large
EMBEDDING_DIMENSIONS=1024
```

Then pull the model:

```bash
ollama pull mxbai-embed-large
```

**Why this model?**

- Supports 100+ languages (English, Italian, German)
- 1024 dimensions (vs 768 for nomic)
- Size: ~670MB (fits in your 8GB GPU)
- Excellent for cross-lingual search

### Step 2: Prepare Database Schema

The new Translation model requires schema updates. Use SQLAlchemy to create the tables:

**Option A: Drop and recreate database (recommended for development)**:

```bash
# Stop services
docker-compose down

# Remove database volume
docker volume rm getinspiredbythebible_postgres_data

# Start fresh
docker-compose up -d
```

**Option B: Manual schema update via SQL**:

```sql
-- Create translations table
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

-- Add translation column to verses
ALTER TABLE verses ADD COLUMN IF NOT EXISTS translation VARCHAR(20) DEFAULT 'kjv';
ALTER TABLE verses ADD CONSTRAINT fk_verses_translation
    FOREIGN KEY (translation) REFERENCES translations(code) ON DELETE CASCADE;

-- Update unique constraint
ALTER TABLE verses DROP CONSTRAINT IF EXISTS unique_verse;
ALTER TABLE verses ADD CONSTRAINT unique_verse_translation
    UNIQUE(book_id, chapter_number, verse_number, translation);

-- Add index
CREATE INDEX IF NOT EXISTS idx_verses_translation ON verses(translation);
```

### Step 3: Load All Bible Translations

```bash
cd scripts

# List available translations
python load_bible.py --list

# Load each translation
python load_bible.py --translation kjv      # English - King James Version
python load_bible.py --translation ita1927  # Italian - Riveduta 1927
python load_bible.py --translation deu1912  # German - Lutherbibel 1912
python load_bible.py --translation web      # English - World English Bible

# Or load all at once
python load_bible.py --all
```

**Expected output for each:**

- Downloads Bible JSON from source (~5-10 seconds)
- Loads ~31,102 verses per translation
- Maps book names for non-English translations
- Creates translation metadata automatically

### Step 4: Generate Multilingual Embeddings

```bash
cd scripts
python create_embeddings.py --translation kjv
python create_embeddings.py --translation ita1927
python create_embeddings.py --translation deu1912
python create_embeddings.py --translation web

# Or generate for all translations
python create_embeddings.py --all
```

**Note**: You'll need to update `create_embeddings.py` first (see Phase 9 below)

### Step 5: Verify Database

```bash
# Check translations table
psql -U bible -d bibledb -c "SELECT * FROM translations;"

# Check verse counts by translation
psql -U bible -d bibledb -c "SELECT translation, COUNT(*) FROM verses GROUP BY translation;"

# Check embedding coverage
psql -U bible -d bibledb -c "
SELECT translation,
       COUNT(*) as total_verses,
       COUNT(embedding) as verses_with_embeddings
FROM verses
GROUP BY translation
ORDER BY translation;
"
```

**Expected:**

- `kjv`: ~31,102 verses
- `ita1927`: ~31,102 verses
- `deu1912`: ~31,102 verses
- `web`: ~31,102 verses

---

## 🔧 Remaining Work (Phases 7-15)

Once the above steps work, here's what's left:

### Phase 7-8: Italian Bible Loading (Manual Testing)

- Test download & loading
- Verify book name mapping works
- Check verse counts

### Phase 9-10: Embeddings Generation

- Update `create_embeddings.py` for multilingual
- Generate embeddings for Italian
- Test embedding quality

### Phase 11-12: API Updates

- Update `scripture/repository.py` for translation filtering
- Update API routes with translation parameter
- Add `/translations` endpoint

### Phase 13: Cross-Lingual Search Testing

- Test English query → Italian results
- Verify semantic similarity

### Phase 14: Frontend Updates

- Create TranslationSelector component
- Add translation dropdown to UI
- Store preference in localStorage

### Phase 15: Documentation

- Update CLAUDE.md
- Update README with multilingual instructions

---

## 📖 How to Use the New Loader

```bash
# List available translations
python load_bible.py --list

# Load specific translation
python load_bible.py --translation ita1927
python load_bible.py --translation deu1912
python load_bible.py --translation web

# Load all translations at once
python load_bible.py --all

# Default (loads KJV if no args)
python load_bible.py
```

---

## 🐛 Troubleshooting

### Problem: "ollama: command not found"

```bash
# Start Ollama first
ollama serve  # In a separate terminal
```

### Problem: Database connection failed

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Or start with Docker Compose
docker-compose up -d postgres
```

### Problem: "Translation already exists"

This is fine! The loader uses `ON CONFLICT` to handle duplicates.
Just re-run and it will update the verses.

### Problem: Book name mapping errors

Check `scripts/translations.py` - all Italian/German book names are mapped.
If you see "Unknown book", it means the JSON format changed.

### Problem: "relation translations does not exist"

You need to create the database schema first (see Step 2 above).

---

## 🎯 Quick Test Plan

Once you've done Steps 1-5 above, test:

1. **List translations:**

   ```bash
   python load_bible.py --list
   ```

2. **Load Italian:**

   ```bash
   python load_bible.py --translation ita1927
   ```

3. **Verify data:**

   ```sql
   SELECT v.text, t.name
   FROM verses v
   JOIN translations t ON v.translation = t.code
   WHERE v.book_id = 1 AND v.chapter_number = 1 AND v.verse_number = 1;
   ```

   Should show Genesis 1:1 in multiple translations!

---

## 📞 Continue Implementation

When you're ready to continue, let me know and I can:

1. Update `create_embeddings.py` for multilingual
2. Update the API for translation filtering
3. Create the frontend translation selector
4. Test cross-lingual search

Just say "continue" and I'll pick up where I left off!

---

**Progress**: 6/15 phases complete (40%)
**See**: `MULTILINGUAL_PROGRESS.md` for detailed status
