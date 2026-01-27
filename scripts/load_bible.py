#!/usr/bin/env python3
"""
Load Bible data into the database - Multilingual version.

This script downloads and loads Bible translations (KJV, Italian, German, etc.)
into the PostgreSQL database.

Usage:
    python load_bible.py                    # Load KJV (default)
    python load_bible.py --translation kjv  # Load specific translation
    python load_bible.py --list             # List available translations
    python load_bible.py --all              # Load all translations
"""

import argparse
import asyncio
import json
import httpx
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Import translation configurations
from translations import TRANSLATIONS, map_book_name, list_available_translations

# Bible books metadata (standard English names)
BIBLE_BOOKS = [
    # Old Testament
    {"name": "Genesis", "abbr": "Gen", "testament": "old", "position": 1},
    {"name": "Exodus", "abbr": "Exod", "testament": "old", "position": 2},
    {"name": "Leviticus", "abbr": "Lev", "testament": "old", "position": 3},
    {"name": "Numbers", "abbr": "Num", "testament": "old", "position": 4},
    {"name": "Deuteronomy", "abbr": "Deut", "testament": "old", "position": 5},
    {"name": "Joshua", "abbr": "Josh", "testament": "old", "position": 6},
    {"name": "Judges", "abbr": "Judg", "testament": "old", "position": 7},
    {"name": "Ruth", "abbr": "Ruth", "testament": "old", "position": 8},
    {"name": "1 Samuel", "abbr": "1Sam", "testament": "old", "position": 9},
    {"name": "2 Samuel", "abbr": "2Sam", "testament": "old", "position": 10},
    {"name": "1 Kings", "abbr": "1Kgs", "testament": "old", "position": 11},
    {"name": "2 Kings", "abbr": "2Kgs", "testament": "old", "position": 12},
    {"name": "1 Chronicles", "abbr": "1Chr", "testament": "old", "position": 13},
    {"name": "2 Chronicles", "abbr": "2Chr", "testament": "old", "position": 14},
    {"name": "Ezra", "abbr": "Ezra", "testament": "old", "position": 15},
    {"name": "Nehemiah", "abbr": "Neh", "testament": "old", "position": 16},
    {"name": "Esther", "abbr": "Esth", "testament": "old", "position": 17},
    {"name": "Job", "abbr": "Job", "testament": "old", "position": 18},
    {"name": "Psalms", "abbr": "Ps", "testament": "old", "position": 19},
    {"name": "Proverbs", "abbr": "Prov", "testament": "old", "position": 20},
    {"name": "Ecclesiastes", "abbr": "Eccl", "testament": "old", "position": 21},
    {"name": "Song of Solomon", "abbr": "Song", "testament": "old", "position": 22},
    {"name": "Isaiah", "abbr": "Isa", "testament": "old", "position": 23},
    {"name": "Jeremiah", "abbr": "Jer", "testament": "old", "position": 24},
    {"name": "Lamentations", "abbr": "Lam", "testament": "old", "position": 25},
    {"name": "Ezekiel", "abbr": "Ezek", "testament": "old", "position": 26},
    {"name": "Daniel", "abbr": "Dan", "testament": "old", "position": 27},
    {"name": "Hosea", "abbr": "Hos", "testament": "old", "position": 28},
    {"name": "Joel", "abbr": "Joel", "testament": "old", "position": 29},
    {"name": "Amos", "abbr": "Amos", "testament": "old", "position": 30},
    {"name": "Obadiah", "abbr": "Obad", "testament": "old", "position": 31},
    {"name": "Jonah", "abbr": "Jonah", "testament": "old", "position": 32},
    {"name": "Micah", "abbr": "Mic", "testament": "old", "position": 33},
    {"name": "Nahum", "abbr": "Nah", "testament": "old", "position": 34},
    {"name": "Habakkuk", "abbr": "Hab", "testament": "old", "position": 35},
    {"name": "Zephaniah", "abbr": "Zeph", "testament": "old", "position": 36},
    {"name": "Haggai", "abbr": "Hag", "testament": "old", "position": 37},
    {"name": "Zechariah", "abbr": "Zech", "testament": "old", "position": 38},
    {"name": "Malachi", "abbr": "Mal", "testament": "old", "position": 39},
    # New Testament
    {"name": "Matthew", "abbr": "Matt", "testament": "new", "position": 40},
    {"name": "Mark", "abbr": "Mark", "testament": "new", "position": 41},
    {"name": "Luke", "abbr": "Luke", "testament": "new", "position": 42},
    {"name": "John", "abbr": "John", "testament": "new", "position": 43},
    {"name": "Acts", "abbr": "Acts", "testament": "new", "position": 44},
    {"name": "Romans", "abbr": "Rom", "testament": "new", "position": 45},
    {"name": "1 Corinthians", "abbr": "1Cor", "testament": "new", "position": 46},
    {"name": "2 Corinthians", "abbr": "2Cor", "testament": "new", "position": 47},
    {"name": "Galatians", "abbr": "Gal", "testament": "new", "position": 48},
    {"name": "Ephesians", "abbr": "Eph", "testament": "new", "position": 49},
    {"name": "Philippians", "abbr": "Phil", "testament": "new", "position": 50},
    {"name": "Colossians", "abbr": "Col", "testament": "new", "position": 51},
    {"name": "1 Thessalonians", "abbr": "1Thess", "testament": "new", "position": 52},
    {"name": "2 Thessalonians", "abbr": "2Thess", "testament": "new", "position": 53},
    {"name": "1 Timothy", "abbr": "1Tim", "testament": "new", "position": 54},
    {"name": "2 Timothy", "abbr": "2Tim", "testament": "new", "position": 55},
    {"name": "Titus", "abbr": "Titus", "testament": "new", "position": 56},
    {"name": "Philemon", "abbr": "Phlm", "testament": "new", "position": 57},
    {"name": "Hebrews", "abbr": "Heb", "testament": "new", "position": 58},
    {"name": "James", "abbr": "Jas", "testament": "new", "position": 59},
    {"name": "1 Peter", "abbr": "1Pet", "testament": "new", "position": 60},
    {"name": "2 Peter", "abbr": "2Pet", "testament": "new", "position": 61},
    {"name": "1 John", "abbr": "1John", "testament": "new", "position": 62},
    {"name": "2 John", "abbr": "2John", "testament": "new", "position": 63},
    {"name": "3 John", "abbr": "3John", "testament": "new", "position": 64},
    {"name": "Jude", "abbr": "Jude", "testament": "new", "position": 65},
    {"name": "Revelation", "abbr": "Rev", "testament": "new", "position": 66},
]


async def download_translation(translation_code: str, output_path: Path) -> dict:
    """Download Bible translation JSON."""
    config = TRANSLATIONS[translation_code]

    if output_path.exists():
        print(f"📖 Loading {config['name']} from cache: {output_path}")
        with open(output_path, encoding="utf-8") as f:
            return json.load(f)

    print(f"📥 Downloading {config['name']} ({config['language']}) from {config['source']}")
    print(f"    URL: {config['url']}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(config["url"], follow_redirects=True)
        response.raise_for_status()
        data = response.json()

    # Save for future use
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved to: {output_path}")
    return data


def normalize_bible_data(data: dict|list, source: str) -> list:
    """
    Normalize different JSON formats to common structure.

    Returns: List of books with chapters containing verses
    Format: [{"name": "...", "chapters": [[v1, v2], [ch2...]]}, ...]
    """
    if source == "thiagobodruk":
        # Already in correct format: [{"abbrev": "gn", "chapters": [[v1, v2], ...]}]
        return data

    elif source == "getbible":
        # Format: {"books": [{"name": "...", "chapters": [{"verses": [{text, verse}, ...]}]}]}
        if isinstance(data, dict) and "books" in data:
            normalized = []
            for book in data.get("books", []):
                book_data = {
                    "name": book.get("name", ""),
                    "chapters": []
                }
                for chapter in book.get("chapters", []):
                    # Extract verse texts in order
                    verses = [v.get("text", "") for v in chapter.get("verses", [])]
                    book_data["chapters"].append(verses)
                normalized.append(book_data)
            return normalized

    # Fallback: return as-is
    return data if isinstance(data, list) else []


async def ensure_schema(session):
    """Ensure database schema exists with translation support."""

    # Create translations table first
    await session.execute(text("""
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
        )
    """))

    # Create books, chapters, verses tables
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS books (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) NOT NULL UNIQUE,
            abbreviation VARCHAR(10) NOT NULL,
            testament VARCHAR(20) NOT NULL,
            position INTEGER NOT NULL
        )
    """))

    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS chapters (
            id SERIAL PRIMARY KEY,
            book_id INTEGER REFERENCES books(id),
            number INTEGER NOT NULL,
            UNIQUE(book_id, number)
        )
    """))

    # Check if verses table needs translation column
    result = await session.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'verses' AND column_name = 'translation'
    """))
    has_translation_column = result.fetchone() is not None

    if not has_translation_column:
        # Create new verses table with translation column
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS verses (
                id SERIAL PRIMARY KEY,
                book_id INTEGER REFERENCES books(id),
                chapter_id INTEGER REFERENCES chapters(id),
                chapter_number INTEGER NOT NULL,
                verse_number INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation VARCHAR(20) DEFAULT 'kjv' NOT NULL REFERENCES translations(code),
                embedding vector(1024),
                UNIQUE(book_id, chapter_number, verse_number, translation)
            )
        """))
    else:
        # Table exists with translation column - just ensure it exists
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS verses (
                id SERIAL PRIMARY KEY,
                book_id INTEGER REFERENCES books(id),
                chapter_id INTEGER REFERENCES chapters(id),
                chapter_number INTEGER NOT NULL,
                verse_number INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation VARCHAR(20) DEFAULT 'kjv' NOT NULL REFERENCES translations(code),
                embedding vector(1024),
                UNIQUE(book_id, chapter_number, verse_number, translation)
            )
        """))

    # Create other tables
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS passages (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            start_book_id INTEGER NOT NULL REFERENCES books(id),
            start_chapter INTEGER NOT NULL,
            start_verse INTEGER NOT NULL,
            end_chapter INTEGER NOT NULL,
            end_verse INTEGER NOT NULL,
            text TEXT NOT NULL,
            topics VARCHAR(500),
            embedding vector(1024)
        )
    """))

    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,
            parent_id INTEGER REFERENCES topics(id),
            embedding vector(1024)
        )
    """))

    # Create indexes
    await session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_verse_embedding
        ON verses USING ivfflat (embedding vector_cosine_ops)
    """))

    await session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_verses_translation
        ON verses(translation)
    """))

    await session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_passage_embedding
        ON passages USING ivfflat (embedding vector_cosine_ops)
    """))

    await session.commit()


async def load_translation_metadata(session, translation_code: str):
    """Insert translation metadata into translations table."""
    config = TRANSLATIONS[translation_code]

    await session.execute(
        text("""
            INSERT INTO translations (code, name, language, language_code, description, is_default)
            VALUES (:code, :name, :language, :lang_code, :description, :is_default)
            ON CONFLICT (code) DO UPDATE
            SET name = :name, language = :language, description = :description
        """),
        {
            "code": config["code"],
            "name": config["name"],
            "language": config["language"],
            "lang_code": config["language_code"],
            "description": config.get("description"),
            "is_default": config.get("is_default", False),
        }
    )
    await session.commit()
    print(f"✅ Loaded translation metadata: {config['name']} ({config['code']})")


async def ensure_books_and_chapters(session) -> dict:
    """Ensure books and chapters exist in database. Returns book_ids mapping."""

    # Check if books already loaded
    result = await session.execute(text("SELECT COUNT(*) FROM books"))
    book_count = result.scalar()

    if book_count == 66:
        # Books already exist, fetch IDs
        result = await session.execute(text("SELECT id, name FROM books"))
        book_ids = {row[1]: row[0] for row in result.fetchall()}
        return book_ids

    print("📚 Loading books and chapters (one-time setup)...")

    # Insert books
    book_ids = {}
    for book_meta in BIBLE_BOOKS:
        result = await session.execute(
            text("""
                INSERT INTO books (name, abbreviation, testament, position)
                VALUES (:name, :abbr, :testament, :position)
                ON CONFLICT (name) DO UPDATE SET name = :name
                RETURNING id
            """),
            {
                "name": book_meta["name"],
                "abbr": book_meta["abbr"],
                "testament": book_meta["testament"],
                "position": book_meta["position"]
            }
        )
        book_ids[book_meta["name"]] = result.scalar_one()

    await session.commit()

    # Insert chapters for each book (Bible structure is constant)
    # We know chapter counts from standard Bible structure
    chapter_counts = {
        "Genesis": 50, "Exodus": 40, "Leviticus": 27, "Numbers": 36, "Deuteronomy": 34,
        "Joshua": 24, "Judges": 21, "Ruth": 4, "1 Samuel": 31, "2 Samuel": 24,
        "1 Kings": 22, "2 Kings": 25, "1 Chronicles": 29, "2 Chronicles": 36, "Ezra": 10,
        "Nehemiah": 13, "Esther": 10, "Job": 42, "Psalms": 150, "Proverbs": 31,
        "Ecclesiastes": 12, "Song of Solomon": 8, "Isaiah": 66, "Jeremiah": 52, "Lamentations": 5,
        "Ezekiel": 48, "Daniel": 12, "Hosea": 14, "Joel": 3, "Amos": 9,
        "Obadiah": 1, "Jonah": 4, "Micah": 7, "Nahum": 3, "Habakkuk": 3,
        "Zephaniah": 3, "Haggai": 2, "Zechariah": 14, "Malachi": 4,
        "Matthew": 28, "Mark": 16, "Luke": 24, "John": 21, "Acts": 28,
        "Romans": 16, "1 Corinthians": 16, "2 Corinthians": 13, "Galatians": 6, "Ephesians": 6,
        "Philippians": 4, "Colossians": 4, "1 Thessalonians": 5, "2 Thessalonians": 3, "1 Timothy": 6,
        "2 Timothy": 4, "Titus": 3, "Philemon": 1, "Hebrews": 13, "James": 5,
        "1 Peter": 5, "2 Peter": 3, "1 John": 5, "2 John": 1, "3 John": 1,
        "Jude": 1, "Revelation": 22
    }

    for book_name, book_id in book_ids.items():
        num_chapters = chapter_counts.get(book_name, 1)
        for chapter_num in range(1, num_chapters + 1):
            await session.execute(
                text("""
                    INSERT INTO chapters (book_id, number)
                    VALUES (:book_id, :number)
                    ON CONFLICT (book_id, number) DO NOTHING
                """),
                {"book_id": book_id, "number": chapter_num}
            )

    await session.commit()
    print(f"✅ Loaded {len(book_ids)} books with chapters")

    return book_ids


async def load_verses(session, translation_code: str, bible_data: list):
    """Load verses for a specific translation."""

    config = TRANSLATIONS[translation_code]
    book_name_map = config.get("book_names")

    # Get book IDs
    result = await session.execute(text("SELECT id, name FROM books ORDER BY position"))
    book_ids = {row[1]: row[0] for row in result.fetchall()}

    # Normalize data format
    normalized_data = normalize_bible_data(bible_data, config["source"])

    verse_count = 0

    for book_idx, book_data in enumerate(normalized_data):
        # Get book name - handle both dict and list formats
        if isinstance(book_data, dict) and "name" in book_data:
            local_name = book_data["name"]
            chapters = book_data.get("chapters", [])
        else:
            # thiagobodruk format uses index
            local_name = BIBLE_BOOKS[book_idx]["name"]
            chapters = book_data.get("chapters", []) if isinstance(book_data, dict) else []

        # Map localized name to standard English name
        if book_name_map:
            standard_name = map_book_name(local_name, translation_code)
        else:
            standard_name = local_name

        book_id = book_ids.get(standard_name)
        if not book_id:
            print(f"  ⚠️ Unknown book: {local_name} -> {standard_name}")
            continue

        print(f"  📖 Loading {standard_name} ({translation_code})...")

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

                # Insert or update verse
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


def convert_db_url_for_asyncpg(database_url: str) -> str:
    """Convert database URL for asyncpg compatibility.

    asyncpg uses 'ssl' parameter instead of 'sslmode', so we need to convert.
    """
    # Convert to async URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # asyncpg uses 'ssl' instead of 'sslmode'
    # sslmode=require -> ssl=require
    database_url = database_url.replace("sslmode=", "ssl=")

    return database_url


async def load_translation_to_db(database_url: str, translation_code: str):
    """Load a specific Bible translation into the database."""

    database_url = convert_db_url_for_asyncpg(database_url)

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        # Create vector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    async with async_session() as session:
        # Ensure schema exists
        await ensure_schema(session)

        # Load translation metadata
        await load_translation_metadata(session, translation_code)

        # Ensure books and chapters exist
        book_ids = await ensure_books_and_chapters(session)

        # Download translation data
        bible_path = Path(__file__).parent.parent / "data" / "bible" / "translations" / f"{translation_code}.json"
        bible_data = await download_translation(translation_code, bible_path)

        # Load verses
        print(f"\n📝 Loading verses for {TRANSLATIONS[translation_code]['name']}...")
        verse_count = await load_verses(session, translation_code, bible_data)

        print(f"✅ Loaded {verse_count:,} verses for {translation_code}")

    await engine.dispose()


async def main():
    """Main entry point."""
    import os

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Load Bible translations into database")
    parser.add_argument(
        "--translation", "-t",
        type=str,
        help="Translation code to load (kjv, ita1927, deu1912, web)"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available translations"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Load all translations"
    )

    args = parser.parse_args()

    # List translations and exit
    if args.list:
        print("\n📚 Available translations:")
        for trans in list_available_translations():
            print(f"  - {trans['code']:<12} {trans['name']:<30} ({trans['language']})")
        return

    # Get database URL
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://bible:bible123@localhost:5432/bibledb"  # pragma: allowlist secret
    )

    # Determine which translations to load
    if args.all:
        translations_to_load = list(TRANSLATIONS.keys())
    elif args.translation:
        if args.translation not in TRANSLATIONS:
            print(f"❌ Unknown translation: {args.translation}")
            print(f"   Available: {', '.join(TRANSLATIONS.keys())}")
            return
        translations_to_load = [args.translation]
    else:
        # Default: load KJV
        translations_to_load = ["kjv"]

    # Load each translation
    print(f"\n🗄️  Database: {database_url}")
    print(f"📖 Translations to load: {', '.join(translations_to_load)}\n")

    for trans_code in translations_to_load:
        print(f"\n{'='*60}")
        print(f"Loading: {TRANSLATIONS[trans_code]['name']} ({trans_code})")
        print(f"{'='*60}")
        await load_translation_to_db(database_url, trans_code)

    print("\n🎉 All translations loaded successfully!")
    print("\nNext step: Run create_embeddings.py to generate semantic search vectors")
    print("Example: python create_embeddings.py --translation ita1927")


if __name__ == "__main__":
    asyncio.run(main())
