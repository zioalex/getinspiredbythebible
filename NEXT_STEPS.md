# 🚀 Next Steps - Multilingual Bible Support

**Date**: 2026-01-25
**Status**: Phase 1-6 Complete (40% done) ✅
**Branch**: `multiple_bible`
**Commit**: `cc064eb`

---

## ✅ What's Been Done (Autonomous Implementation)

I've completed the core infrastructure for multilingual Bible support:

### Completed

1. ✅ Database migration scripts
2. ✅ SQLAlchemy models with Translation support
3. ✅ Configuration updated for multilingual model
4. ✅ Translation configurations (Italian/German book mappings)
5. ✅ Complete rewrite of `load_bible.py` with CLI support
6. ✅ All changes committed to `multiple_bible` branch

### Files Created

- `scripts/migrations/001_add_translations.sql` - Database migration
- `scripts/run_migration.py` - Migration runner
- `scripts/translations.py` - Translation configs & book name mappings
- `MULTILINGUAL_PROGRESS.md` - Detailed progress tracking
- `NEXT_STEPS.md` - This file!

### Files Modified

- `api/config.py` - Switched to mxbai-embed-large (1024 dim)
- `api/scripture/models.py` - Added Translation model
- `scripts/load_bible.py` - Complete rewrite for multilingual

---

## 📋 What You Need to Do Next

### Step 1: Pull the Multilingual Embedding Model ⭐ **CRITICAL**

```bash
ollama pull mxbai-embed-large
```

**Why this model?**

- Supports 100+ languages (English, Italian, German)
- 1024 dimensions (vs 768 for nomic)
- Size: ~670MB (fits in your 8GB GPU)
- Excellent for cross-lingual search

**Verify it worked:**

```bash
ollama list | grep mxbai
```

### Step 2: Run the Database Migration

**⚠️ WARNING: This migration will TRUNCATE verses, passages, and topics tables!**

All Bible data will need to be reloaded with the new multilingual model.

```bash
cd scripts
python run_migration.py 001_add_translations.sql
```

**This will:**

- Create `translations` table with metadata
- Add `translation` column to `verses`
- Update constraints and indexes
- **Clear all existing verses, passages, and topics** (ready for fresh reload)

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
docker-compose up -d db
```

### Problem: "Translation already exists"

This is fine! The loader uses `ON CONFLICT` to handle duplicates.
Just re-run and it will update the verses.

### Problem: Book name mapping errors

Check `scripts/translations.py` - all Italian/German book names are mapped.
If you see "Unknown book", it means the JSON format changed.

---

## 🎯 Quick Test Plan

Once you've done Steps 1-4 above, test:

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

   Should show Genesis 1:1 in both KJV and Italian!

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
**Commit**: `cc064eb - WIP: Multilingual Bible support - Phase 1-6 complete`
**See**: `MULTILINGUAL_PROGRESS.md` for detailed status
