# Bible Embedding Extension Plan: Multilingual Support

## Overview

This document provides comprehensive instructions for extending the Bible embedding system to
support Italian, German, and modern English translations alongside the existing KJV.

**Goal**: Enable users to search and read scripture in their preferred language while maintaining
semantic search quality across all translations.

---

## 1. Translation Selection

### Recommended Translations (All Public Domain)

| Language | Translation | Code | Year | Notes |
|----------|-------------|------|------|-------|
| **Italian** | Riveduta 1927 (Luzzi) | `ita1927` | 1927 | Most readable public domain Italian translation |
| **German** | Lutherbibel 1912 | `deu1912` | 1912 | Classic Luther translation, widely recognized |
| **English** | World English Bible | `web` | 2000 | Modern English, fully public domain |
| **English** | American Standard Version | `asv` | 1901 | Accurate, formal English (optional) |

### Why These Translations?

1. **Riveduta 1927** - Preferred over Diodati (1649) because:
   - More modern Italian vocabulary
   - Better readability for contemporary users
   - Still public domain (translator Giovanni Luzzi died 1948, 70+ years ago)

2. **Luther 1912** - Preferred over older Luther versions because:
   - Uses updated German spelling
   - Maintains classic Luther language feel
   - Public domain (70+ years since translation team's work)

3. **World English Bible** - Preferred over KJV for modern English because:
   - Contemporary vocabulary
   - No archaic "thee/thou" language
   - Explicitly public domain (not just expired copyright)

### Translations to AVOID (Copyright Protected)

| Translation | Issue |
|-------------|-------|
| CEI (Italian) | © Conferenza Episcopale Italiana |
| Nuova Riveduta 2006 | © Società Biblica di Ginevra |
| Luther 2017 | © Deutsche Bibelgesellschaft |
| NIV | © Biblica - strict usage limits |
| ESV | © Crossway - requires licensing |

---

## 2. Data Sources

### Primary Source: scrollmapper/bible_databases (Recommended)

**Repository**: `https://github.com/scrollmapper/bible_databases`
**License**: MIT
**Format**: JSON, CSV, SQL, XML

This is the most comprehensive source with 140+ translations.

**Download specific files:**

```bash
# Create data directory
mkdir -p data/bible/translations

# Download from scrollmapper (raw GitHub URLs)
curl -o data/bible/translations/ita1927.json \
  "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/json/ita1927.json"

curl -o data/bible/translations/deu1912.json \
  "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/json/deu1912.json"

curl -o data/bible/translations/web.json \
  "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/json/web.json"
```

**JSON Format (scrollmapper):**

```json
{
  "translation": "ita1927",
  "books": [
    {
      "name": "Genesi",
      "chapters": [
        {
          "chapter": 1,
          "verses": [
            {"verse": 1, "text": "Nel principio Iddio creò i cieli e la terra."},
            {"verse": 2, "text": "E la terra era informe e vuota..."}
          ]
        }
      ]
    }
  ]
}
```

### Alternative Source: getBible API

**Base URL**: `https://api.getbible.net/v2/`
**Auth**: None required
**Rate Limit**: Reasonable for batch downloads

**API Endpoints:**

```bash
# Full translation
GET https://api.getbible.net/v2/{translation}.json

# Single book
GET https://api.getbible.net/v2/{translation}/{book_number}.json

# Single chapter
GET https://api.getbible.net/v2/{translation}/{book_number}/{chapter}.json
```

**Available Translation Codes:**

- `ita1927` - Italian Riveduta 1927
- `giovanni` - Italian Diodati (alternative)
- `deu1912` - German Luther 1912
- `schlachter` - German Schlachter 1951
- `web` - World English Bible
- `asv` - American Standard Version

### Alternative Source: thiagobodruk/bible

**Repository**: `https://github.com/thiagobodruk/bible`
**License**: CC BY-NC (non-commercial only - check if acceptable)

This is the source your current KJV came from (`en_kjv.json`).

**Available files:**

- `json/it_diodati.json` - Italian Diodati
- `json/de_schlachter.json` - German Schlachter

**JSON Format (thiagobodruk):**

```json
[
  {
    "abbrev": "gn",
    "chapters": [
      ["Nel principio Iddio creò i cieli e la terra.", "E la terra era informe..."],
      ["chapter 2 verses..."]
    ]
  }
]
```

Note: This format matches your current `load_bible.py` structure.

---

## 3. Database Schema Changes

### 3.1 Create Migration Script

Create `scripts/migrations/001_add_translations.sql`:

```sql
-- Add translations metadata table
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

-- Insert translation metadata
INSERT INTO translations (code, name, language, language_code, is_default) VALUES
    ('kjv', 'King James Version', 'English', 'en', TRUE),
    ('web', 'World English Bible', 'English', 'en', FALSE),
    ('asv', 'American Standard Version', 'English', 'en', FALSE),
    ('ita1927', 'Riveduta 1927', 'Italian', 'it', FALSE),
    ('deu1912', 'Lutherbibel 1912', 'German', 'de', FALSE)
ON CONFLICT (code) DO NOTHING;

-- Add translation column to verses
ALTER TABLE verses
ADD COLUMN IF NOT EXISTS translation VARCHAR(20) DEFAULT 'kjv';

-- Update existing verses
UPDATE verses SET translation = 'kjv' WHERE translation IS NULL;

-- Make translation NOT NULL after backfill
ALTER TABLE verses ALTER COLUMN translation SET NOT NULL;

-- Add foreign key constraint
ALTER TABLE verses
ADD CONSTRAINT fk_verses_translation
FOREIGN KEY (translation) REFERENCES translations(code);

-- Update unique constraint to include translation
ALTER TABLE verses DROP CONSTRAINT IF EXISTS unique_verse;
ALTER TABLE verses DROP CONSTRAINT IF EXISTS unique_verse_translation;
ALTER TABLE verses ADD CONSTRAINT unique_verse_translation
    UNIQUE(book_id, chapter_number, verse_number, translation);

-- Add index for translation queries
CREATE INDEX IF NOT EXISTS idx_verses_translation ON verses(translation);

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_verses_translation_embedding
ON verses(translation)
WHERE embedding IS NOT NULL;
```

### 3.2 Update SQLAlchemy Models

Update `api/scripture/models.py`:

```python
class Translation(Base):
    """Bible translation metadata."""

    __tablename__ = "translations"

    code = Column(String(20), primary_key=True)
    name = Column(String(100), nullable=False)
    language = Column(String(50), nullable=False)
    language_code = Column(String(10), nullable=False)  # ISO 639-1
    description = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    license = Column(String(100), default="Public Domain")
    is_default = Column(Boolean, default=False)

    # Relationships
    verses = relationship("Verse", back_populates="translation_rel")

    def __repr__(self):
        return f"<Translation(code='{self.code}', name='{self.name}')>"


class Verse(Base):
    """Individual Bible verse with embedding for semantic search."""

    __tablename__ = "verses"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    verse_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    translation = Column(String(20), ForeignKey("translations.code"), nullable=False, default="kjv")

    # Vector embedding for semantic search
    embedding = Column(Vector(settings.embedding_dimensions), nullable=True)

    # Relationships
    book = relationship("Book", back_populates="verses")
    chapter = relationship("Chapter", back_populates="verses")
    translation_rel = relationship("Translation", back_populates="verses")

    __table_args__ = (
        UniqueConstraint("book_id", "chapter_number", "verse_number", "translation",
                        name="unique_verse_translation"),
        Index("idx_verse_embedding", "embedding", postgresql_using="ivfflat"),
        Index("idx_verses_translation", "translation"),
    )
```

---

## 4. Book Name Mappings

### Italian Book Names (Riveduta 1927)

```python
ITALIAN_BOOK_NAMES = {
    # Old Testament
    "Genesi": "Genesis",
    "Esodo": "Exodus",
    "Levitico": "Leviticus",
    "Numeri": "Numbers",
    "Deuteronomio": "Deuteronomy",
    "Giosuè": "Joshua",
    "Giudici": "Judges",
    "Rut": "Ruth",
    "1 Samuele": "1 Samuel",
    "2 Samuele": "2 Samuel",
    "1 Re": "1 Kings",
    "2 Re": "2 Kings",
    "1 Cronache": "1 Chronicles",
    "2 Cronache": "2 Chronicles",
    "Esdra": "Ezra",
    "Neemia": "Nehemiah",
    "Ester": "Esther",
    "Giobbe": "Job",
    "Salmi": "Psalms",
    "Proverbi": "Proverbs",
    "Ecclesiaste": "Ecclesiastes",
    "Cantico dei Cantici": "Song of Solomon",
    "Isaia": "Isaiah",
    "Geremia": "Jeremiah",
    "Lamentazioni": "Lamentations",
    "Ezechiele": "Ezekiel",
    "Daniele": "Daniel",
    "Osea": "Hosea",
    "Gioele": "Joel",
    "Amos": "Amos",
    "Abdia": "Obadiah",
    "Giona": "Jonah",
    "Michea": "Micah",
    "Naum": "Nahum",
    "Abacuc": "Habakkuk",
    "Sofonia": "Zephaniah",
    "Aggeo": "Haggai",
    "Zaccaria": "Zechariah",
    "Malachia": "Malachi",
    # New Testament
    "Matteo": "Matthew",
    "Marco": "Mark",
    "Luca": "Luke",
    "Giovanni": "John",
    "Atti": "Acts",
    "Romani": "Romans",
    "1 Corinzi": "1 Corinthians",
    "2 Corinzi": "2 Corinthians",
    "Galati": "Galatians",
    "Efesini": "Ephesians",
    "Filippesi": "Philippians",
    "Colossesi": "Colossians",
    "1 Tessalonicesi": "1 Thessalonians",
    "2 Tessalonicesi": "2 Thessalonians",
    "1 Timoteo": "1 Timothy",
    "2 Timoteo": "2 Timothy",
    "Tito": "Titus",
    "Filemone": "Philemon",
    "Ebrei": "Hebrews",
    "Giacomo": "James",
    "1 Pietro": "1 Peter",
    "2 Pietro": "2 Peter",
    "1 Giovanni": "1 John",
    "2 Giovanni": "2 John",
    "3 Giovanni": "3 John",
    "Giuda": "Jude",
    "Apocalisse": "Revelation",
}
```

### German Book Names (Luther 1912)

```python
GERMAN_BOOK_NAMES = {
    # Old Testament
    "1. Mose": "Genesis",
    "2. Mose": "Exodus",
    "3. Mose": "Leviticus",
    "4. Mose": "Numbers",
    "5. Mose": "Deuteronomy",
    "Josua": "Joshua",
    "Richter": "Judges",
    "Ruth": "Ruth",
    "1. Samuel": "1 Samuel",
    "2. Samuel": "2 Samuel",
    "1. Könige": "1 Kings",
    "2. Könige": "2 Kings",
    "1. Chronik": "1 Chronicles",
    "2. Chronik": "2 Chronicles",
    "Esra": "Ezra",
    "Nehemia": "Nehemiah",
    "Esther": "Esther",
    "Hiob": "Job",
    "Psalmen": "Psalms",
    "Sprüche": "Proverbs",
    "Prediger": "Ecclesiastes",
    "Hohelied": "Song of Solomon",
    "Jesaja": "Isaiah",
    "Jeremia": "Jeremiah",
    "Klagelieder": "Lamentations",
    "Hesekiel": "Ezekiel",
    "Daniel": "Daniel",
    "Hosea": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadja": "Obadiah",
    "Jona": "Jonah",
    "Micha": "Micah",
    "Nahum": "Nahum",
    "Habakuk": "Habakkuk",
    "Zephanja": "Zephaniah",
    "Haggai": "Haggai",
    "Sacharja": "Zechariah",
    "Maleachi": "Malachi",
    # New Testament
    "Matthäus": "Matthew",
    "Markus": "Mark",
    "Lukas": "Luke",
    "Johannes": "John",
    "Apostelgeschichte": "Acts",
    "Römer": "Romans",
    "1. Korinther": "1 Corinthians",
    "2. Korinther": "2 Corinthians",
    "Galater": "Galatians",
    "Epheser": "Ephesians",
    "Philipper": "Philippians",
    "Kolosser": "Colossians",
    "1. Thessalonicher": "1 Thessalonians",
    "2. Thessalonicher": "2 Thessalonians",
    "1. Timotheus": "1 Timothy",
    "2. Timotheus": "2 Timothy",
    "Titus": "Titus",
    "Philemon": "Philemon",
    "Hebräer": "Hebrews",
    "Jakobus": "James",
    "1. Petrus": "1 Peter",
    "2. Petrus": "2 Peter",
    "1. Johannes": "1 John",
    "2. Johannes": "2 John",
    "3. Johannes": "3 John",
    "Judas": "Jude",
    "Offenbarung": "Revelation",
}
```

---

## 5. Updated load_bible.py

Key changes to implement:

```python
#!/usr/bin/env python3
"""
Load Bible data into the database - Multilingual version.

Usage:
    python load_bible.py                    # Load all translations
    python load_bible.py --translation kjv  # Load specific translation
    python load_bible.py --list             # List available translations
"""

import argparse
import asyncio
import json
import httpx
from pathlib import Path
from typing import Optional

# Translation configurations
TRANSLATIONS = {
    "kjv": {
        "name": "King James Version",
        "language": "English",
        "language_code": "en",
        "source": "thiagobodruk",
        "url": "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/en_kjv.json",
        "book_names": None,  # Uses standard English names
    },
    "web": {
        "name": "World English Bible",
        "language": "English",
        "language_code": "en",
        "source": "scrollmapper",
        "url": "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/json/web.json",
        "book_names": None,
    },
    "ita1927": {
        "name": "Riveduta 1927",
        "language": "Italian",
        "language_code": "it",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/ita1927.json",
        "book_names": ITALIAN_BOOK_NAMES,
    },
    "deu1912": {
        "name": "Lutherbibel 1912",
        "language": "German",
        "language_code": "de",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/deu1912.json",
        "book_names": GERMAN_BOOK_NAMES,
    },
}


async def download_translation(translation_code: str, output_dir: Path) -> dict:
    """Download Bible translation JSON."""
    config = TRANSLATIONS[translation_code]
    output_path = output_dir / f"{translation_code}.json"

    if output_path.exists():
        print(f"📖 Loading {config['name']} from cache")
        with open(output_path) as f:
            return json.load(f)

    print(f"📥 Downloading {config['name']} from {config['source']}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(config["url"], follow_redirects=True)
        response.raise_for_status()
        data = response.json()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def normalize_bible_data(data: dict, source: str, book_name_map: Optional[dict]) -> list:
    """
    Normalize different JSON formats to common structure.

    Returns: List of books with chapters containing verses
    """
    if source == "thiagobodruk":
        # Format: [{"abbrev": "gn", "chapters": [[v1, v2], [ch2...]]}]
        return data  # Already in expected format

    elif source == "getbible":
        # Format: {"books": [{"name": "...", "chapters": [{"verses": [...]}]}]}
        normalized = []
        for book in data.get("books", []):
            book_data = {
                "name": book["name"],
                "chapters": []
            }
            for chapter in book.get("chapters", []):
                verses = [v["text"] for v in chapter.get("verses", [])]
                book_data["chapters"].append(verses)
            normalized.append(book_data)
        return normalized

    elif source == "scrollmapper":
        # Similar to getbible but may have different structure
        # Implement based on actual format
        pass

    return data


async def load_translation(
    session,
    translation_code: str,
    bible_data: list,
    book_ids: dict,
    book_name_map: Optional[dict]
):
    """Load a single translation into the database."""

    verse_count = 0

    for book_idx, book_data in enumerate(bible_data):
        # Get book name - handle localized names
        if isinstance(book_data, dict) and "name" in book_data:
            local_name = book_data["name"]
            chapters = book_data.get("chapters", [])
        else:
            # thiagobodruk format uses index
            local_name = BIBLE_BOOKS[book_idx]["name"]
            chapters = book_data.get("chapters", [])

        # Map localized name to standard name
        if book_name_map and local_name in book_name_map:
            standard_name = book_name_map[local_name]
        else:
            standard_name = local_name

        book_id = book_ids.get(standard_name)
        if not book_id:
            print(f"  ⚠️ Unknown book: {local_name} -> {standard_name}")
            continue

        # Get chapter IDs for this book
        chapter_result = await session.execute(
            text("SELECT id, number FROM chapters WHERE book_id = :book_id"),
            {"book_id": book_id}
        )
        chapter_ids = {row[1]: row[0] for row in chapter_result.fetchall()}

        for chapter_idx, chapter_verses in enumerate(chapters):
            chapter_num = chapter_idx + 1
            chapter_id = chapter_ids.get(chapter_num)

            if not chapter_id:
                continue

            for verse_idx, verse_text in enumerate(chapter_verses):
                verse_num = verse_idx + 1

                await session.execute(
                    text("""
                        INSERT INTO verses
                            (book_id, chapter_id, chapter_number, verse_number, text, translation)
                        VALUES
                            (:book_id, :chapter_id, :chapter_num, :verse_num, :text, :translation)
                        ON CONFLICT (book_id, chapter_number, verse_number, translation)
                        DO UPDATE SET text = :text
                    """),
                    {
                        "book_id": book_id,
                        "chapter_id": chapter_id,
                        "chapter_num": chapter_num,
                        "verse_num": verse_num,
                        "text": verse_text,
                        "translation": translation_code,
                    }
                )
                verse_count += 1

        await session.commit()

    return verse_count
```

---

## 6. Updated create_embeddings.py

Key changes:

```python
async def create_embeddings(
    database_url: str,
    ollama_host: str,
    model: str,
    translation: Optional[str] = None
):
    """Generate embeddings for verses, optionally filtered by translation."""

    # Build query - filter by translation if specified
    query = """
        SELECT v.id, v.text, b.name, v.chapter_number, v.verse_number, v.translation
        FROM verses v
        JOIN books b ON v.book_id = b.id
        WHERE v.embedding IS NULL
    """
    if translation:
        query += " AND v.translation = :translation"
    query += " ORDER BY v.translation, b.position, v.chapter_number, v.verse_number"

    # ... rest of implementation

    # When creating embedding text, include translation context:
    for row in batch:
        verse_id, text, book_name, chapter, verse_num, trans_code = row

        # Include translation code for better multilingual embedding separation
        embedding_text = f"[{trans_code}] {book_name} {chapter}:{verse_num} - {text}"
        texts.append(embedding_text)
```

### Multilingual Embedding Model Option

For better cross-language search, consider using a multilingual embedding model:

```python
# In config.py, add option for multilingual model
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# Alternative multilingual models:
# - "multilingual-e5-large" (via Ollama: ollama pull mxbai/multilingual-e5-large)
# - "paraphrase-multilingual-MiniLM-L12-v2" (via sentence-transformers)
```

**Trade-offs:**

- `nomic-embed-text`: Better English performance, faster
- `multilingual-e5-large`: Better cross-language search, larger model

---

## 7. API Changes

### Update `api/scripture/repository.py`

```python
async def search_verses_semantic(
    self,
    query_embedding: list[float],
    limit: int = 10,
    similarity_threshold: float = 0.35,
    translation: Optional[str] = None,
    translations: Optional[list[str]] = None,
) -> list[dict]:
    """
    Search verses by semantic similarity.

    Args:
        query_embedding: Vector embedding of search query
        limit: Maximum results to return
        similarity_threshold: Minimum similarity score
        translation: Single translation to search (e.g., "ita1927")
        translations: List of translations to search (e.g., ["kjv", "web"])
    """

    query = """
        SELECT
            v.id, v.text, v.chapter_number, v.verse_number, v.translation,
            b.name as book_name,
            1 - (v.embedding <=> :embedding) as similarity
        FROM verses v
        JOIN books b ON v.book_id = b.id
        WHERE v.embedding IS NOT NULL
    """

    params = {"embedding": str(query_embedding), "threshold": similarity_threshold}

    if translation:
        query += " AND v.translation = :translation"
        params["translation"] = translation
    elif translations:
        query += " AND v.translation = ANY(:translations)"
        params["translations"] = translations

    query += """
        AND 1 - (v.embedding <=> :embedding) > :threshold
        ORDER BY similarity DESC
        LIMIT :limit
    """
    params["limit"] = limit

    # ... execute and return results
```

### Update `api/routes/scripture.py`

```python
@router.get("/search")
async def search_scripture(
    q: str,
    translation: Optional[str] = Query(None, description="Translation code (e.g., 'kjv', 'ita1927')"),
    limit: int = Query(10, ge=1, le=50),
    # ... other params
):
    """Search scripture with optional translation filter."""
    pass


@router.get("/translations")
async def list_translations():
    """List all available translations."""
    pass


@router.get("/verse/{book}/{chapter}/{verse}")
async def get_verse(
    book: str,
    chapter: int,
    verse: int,
    translation: str = Query("kjv", description="Translation code"),
):
    """Get specific verse in specified translation."""
    pass
```

---

## 8. Frontend Changes

### TranslationSelector Component

```typescript
// frontend/src/components/TranslationSelector.tsx

interface Translation {
  code: string;
  name: string;
  language: string;
}

const TRANSLATIONS: Translation[] = [
  { code: 'kjv', name: 'King James Version', language: 'English' },
  { code: 'web', name: 'World English Bible', language: 'English' },
  { code: 'ita1927', name: 'Riveduta 1927', language: 'Italiano' },
  { code: 'deu1912', name: 'Lutherbibel 1912', language: 'Deutsch' },
];

export function TranslationSelector({
  value,
  onChange
}: {
  value: string;
  onChange: (code: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="..."
    >
      {TRANSLATIONS.map((t) => (
        <option key={t.code} value={t.code}>
          {t.name} ({t.language})
        </option>
      ))}
    </select>
  );
}
```

### Store Preference

```typescript
// In main chat component or context
const [translation, setTranslation] = useState(() => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('preferredTranslation') || 'kjv';
  }
  return 'kjv';
});

useEffect(() => {
  localStorage.setItem('preferredTranslation', translation);
}, [translation]);
```

---

## 9. Testing Plan

### Unit Tests

```python
# tests/test_translations.py

def test_italian_book_mapping():
    """Verify all Italian books map to valid English names."""
    for italian, english in ITALIAN_BOOK_NAMES.items():
        assert english in [b["name"] for b in BIBLE_BOOKS]

def test_german_book_mapping():
    """Verify all German books map to valid English names."""
    for german, english in GERMAN_BOOK_NAMES.items():
        assert english in [b["name"] for b in BIBLE_BOOKS]

async def test_load_translation():
    """Test loading a translation."""
    # Mock download, verify verse count
    pass

async def test_search_with_translation_filter():
    """Test semantic search respects translation filter."""
    pass
```

### Integration Tests

```bash
# Verify verse counts per translation
SELECT translation, COUNT(*) FROM verses GROUP BY translation;

# Expected counts (approximately):
# kjv: 31,102
# web: 31,102
# ita1927: 31,102
# deu1912: 31,102

# Verify embeddings exist
SELECT translation, COUNT(*)
FROM verses
WHERE embedding IS NOT NULL
GROUP BY translation;
```

---

## 10. Implementation Order

1. **Database Migration** (30 min)
   - Run SQL migration
   - Verify schema changes

2. **Update Models** (30 min)
   - Add Translation model
   - Update Verse model
   - Run tests

3. **Update load_bible.py** (2-3 hours)
   - Add translation configurations
   - Implement format normalization
   - Add book name mappings
   - Test with one translation

4. **Download & Load Data** (1-2 hours)
   - Download all translation JSONs
   - Load each translation
   - Verify verse counts

5. **Generate Embeddings** (2-4 hours per translation)
   - Update create_embeddings.py
   - Run for each translation
   - ~31,000 verses × 4 translations = ~124,000 embeddings

6. **Update API** (1-2 hours)
   - Add translation filter to repository
   - Update routes
   - Add translations endpoint

7. **Update Frontend** (1-2 hours)
   - Add TranslationSelector
   - Wire up to API calls
   - Store preference

8. **Testing & Documentation** (1-2 hours)
   - Integration tests
   - Update README
   - Update CLAUDE.md

---

## 11. Rollback Plan

If issues arise:

```sql
-- Remove new translations, keep KJV
DELETE FROM verses WHERE translation != 'kjv';

-- Remove translation column
ALTER TABLE verses DROP CONSTRAINT unique_verse_translation;
ALTER TABLE verses DROP COLUMN translation;
ALTER TABLE verses ADD CONSTRAINT unique_verse
    UNIQUE(book_id, chapter_number, verse_number);

-- Drop translations table
DROP TABLE IF EXISTS translations;
```

---

## 12. Future Enhancements

1. **Cross-lingual search**: Query in English, find matching Italian verses
2. **Parallel view**: Show same verse in multiple translations side-by-side
3. **Translation comparison**: Highlight differences between translations
4. **More translations**: Spanish (Reina-Valera), French (Louis Segond), Portuguese (Almeida)
5. **Language auto-detection**: Detect user's browser language, default to matching translation
