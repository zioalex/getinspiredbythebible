# Multilingual Bible Embedding Extension

## Task: Add Italian, German, and Modern English Bible Translations

This section provides instructions for extending the Bible embedding system to support multiple languages.

---

## Quick Reference: Translations to Add

| Language | Translation | Code | Source | License |
|----------|-------------|------|--------|---------|
| Italian | Riveduta 1927 | `ita1927` | getBible API / scrollmapper | Public Domain |
| German | Luther 1912 | `deu1912` | getBible API / scrollmapper | Public Domain |
| English | World English Bible | `web` | eBible.org / scrollmapper | Public Domain |

**All translations are public domain - no licensing concerns.**

---

## Implementation Steps

### Phase 1: Database Schema Changes

1. **Add `translation` column to verses table:**

```sql
ALTER TABLE verses ADD COLUMN translation VARCHAR(20) DEFAULT 'kjv';
ALTER TABLE verses DROP CONSTRAINT unique_verse;
ALTER TABLE verses ADD CONSTRAINT unique_verse_translation
    UNIQUE(book_id, chapter_number, verse_number, translation);
```

1. **Create translations metadata table:**

```sql
CREATE TABLE translations (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    language VARCHAR(50) NOT NULL,
    language_code VARCHAR(10) NOT NULL,
    is_default BOOLEAN DEFAULT FALSE
);
```

1. **Update `models.py`** - Add Translation model and update Verse model with translation FK.

### Phase 2: Download Bible Data

**Primary source**: `https://github.com/scrollmapper/bible_databases` (MIT license)

Files needed from scrollmapper repo:

- `json/ita1927.json` - Italian Riveduta 1927
- `json/deu1912.json` - German Luther 1912
- `json/web.json` - World English Bible

**Alternative API**: getBible API (no auth required)

```plaintext
https://api.getbible.net/v2/ita1927.json
https://api.getbible.net/v2/deu1912.json
https://api.getbible.net/v2/web.json
```

### Phase 3: Update load_bible.py

Key changes:

1. Accept `--translation` CLI argument (default: all)
2. Load translation metadata first
3. Download JSON for each translation
4. Insert verses with translation code
5. Handle book name mapping (Italian/German book names → standard IDs)

### Phase 4: Update create_embeddings.py

Key changes:

1. Generate embeddings per-translation
2. Include translation context in embedding text:

   ```python
   f"[{translation}] {book_name} {chapter}:{verse} - {text}"
   ```

3. Consider multilingual embedding model (e.g., `multilingual-e5-large` for better cross-lingual search)

### Phase 5: Update API & Frontend

1. **API changes (`scripture/repository.py`):**
   - Add `translation` filter to search queries
   - Default to user's preferred translation
   - Support cross-translation search

2. **Frontend changes:**
   - Add translation selector dropdown
   - Store preference in localStorage
   - Display translation badge on verses

---

## Book Name Mapping

The Italian and German translations use localized book names. Map them to standard book IDs:

```python
BOOK_NAME_MAPPINGS = {
    "ita1927": {
        "Genesi": "Genesis",
        "Esodo": "Exodus",
        "Matteo": "Matthew",
        "Giovanni": "John",
        # ... full mapping in docs/BIBLE_EMBEDDING_PLAN.md
    },
    "deu1912": {
        "1. Mose": "Genesis",
        "2. Mose": "Exodus",
        "Matthäus": "Matthew",
        "Johannes": "John",
        # ... full mapping in docs/BIBLE_EMBEDDING_PLAN.md
    }
}
```

---

## Testing Checklist

- [ ] Schema migration runs without data loss
- [ ] All 66 books load for each translation
- [ ] Verse counts match expected (~31,102 per translation)
- [ ] Embeddings generate successfully
- [ ] Semantic search returns relevant results in each language
- [ ] Cross-language search works (query in English, find Italian verse)
- [ ] API filters by translation correctly
- [ ] Frontend translation selector works

---

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `api/scripture/models.py` | Modify | Add Translation model, update Verse |
| `scripts/load_bible.py` | Major | Multi-translation support |
| `scripts/create_embeddings.py` | Modify | Per-translation embedding |
| `api/scripture/repository.py` | Modify | Translation filter |
| `api/routes/scripture.py` | Modify | Translation parameter |
| `frontend/src/components/` | New | TranslationSelector component |
| `data/bible/` | New files | `ita1927.json`, `deu1912.json`, `web.json` |
| `docs/BIBLE_EMBEDDING_PLAN.md` | New | Detailed reference (see below) |

---

## Reference Documentation

See `docs/BIBLE_EMBEDDING_PLAN.md` for:

- Complete book name mappings (Italian/German)
- Detailed JSON format specifications
- Alternative data sources
- Multilingual embedding model options
- Error handling for missing verses
