#!/usr/bin/env python3
"""
Load Bible data into the database.

This script downloads a public domain Bible translation (World English Bible)
and loads it into the PostgreSQL database.

Usage:
    python load_bible.py
"""

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

# Bible books metadata
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

# URL for World English Bible JSON
# This is a public domain modern English translation
WEB_BIBLE_URL = "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/en_kjv.json"


async def download_bible(output_path: Path) -> dict:
    """Download Bible JSON if not already present."""
    if output_path.exists():
        print(f"📖 Loading Bible from {output_path}")
        with open(output_path) as f:
            return json.load(f)

    print(f"📥 Downloading Bible from {WEB_BIBLE_URL}")
    async with httpx.AsyncClient() as client:
        response = await client.get(WEB_BIBLE_URL, follow_redirects=True)
        response.raise_for_status()
        data = response.json()

    # Save for future use
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f)

    print(f"💾 Saved Bible to {output_path}")
    return data


async def load_bible_to_db(database_url: str, bible_data: list):
    """Load Bible data into PostgreSQL."""
    # Convert to async URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        # Create extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    async with async_session() as session:
        # Create tables using raw SQL for simplicity
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

        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS verses (
                id SERIAL PRIMARY KEY,
                book_id INTEGER REFERENCES books(id),
                chapter_id INTEGER REFERENCES chapters(id),
                chapter_number INTEGER NOT NULL,
                verse_number INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding vector(768),
                UNIQUE(book_id, chapter_number, verse_number)
            )
        """))

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
                embedding vector(768)
            )
        """))

        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS topics (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                parent_id INTEGER REFERENCES topics(id),
                embedding vector(768)
            )
        """))

        # Create indexes for better performance
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_verse_embedding
            ON verses USING ivfflat (embedding vector_cosine_ops)
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_passage_embedding
            ON passages USING ivfflat (embedding vector_cosine_ops)
        """))

        await session.commit()

        # Clear existing data
        await session.execute(text("DELETE FROM verses"))
        await session.execute(text("DELETE FROM chapters"))
        await session.execute(text("DELETE FROM books"))
        await session.commit()

        print("📚 Loading books...")

        # Insert books
        book_ids = {}
        for book_meta in BIBLE_BOOKS:
            result = await session.execute(
                text("""
                    INSERT INTO books (name, abbreviation, testament, position)
                    VALUES (:name, :abbr, :testament, :position)
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
        print(f"✅ Loaded {len(book_ids)} books")

        # Process Bible data
        # The JSON format is: [{"abbrev": "gn", "chapters": [[verse1, verse2], [chapter2 verses], ...]}]

        verse_count = 0
        chapter_count = 0

        for book_idx, book_data in enumerate(bible_data):
            book_name = BIBLE_BOOKS[book_idx]["name"]
            book_id = book_ids[book_name]

            print(f"  📖 Loading {book_name}...")

            for chapter_idx, chapter_verses in enumerate(book_data.get("chapters", [])):
                chapter_num = chapter_idx + 1

                # Insert chapter
                result = await session.execute(
                    text("""
                        INSERT INTO chapters (book_id, number)
                        VALUES (:book_id, :number)
                        RETURNING id
                    """),
                    {"book_id": book_id, "number": chapter_num}
                )
                chapter_id = result.scalar_one()
                chapter_count += 1

                # Insert verses
                for verse_idx, verse_text in enumerate(chapter_verses):
                    verse_num = verse_idx + 1

                    await session.execute(
                        text("""
                            INSERT INTO verses (book_id, chapter_id, chapter_number, verse_number, text)
                            VALUES (:book_id, :chapter_id, :chapter_num, :verse_num, :text)
                        """),
                        {
                            "book_id": book_id,
                            "chapter_id": chapter_id,
                            "chapter_num": chapter_num,
                            "verse_num": verse_num,
                            "text": verse_text
                        }
                    )
                    verse_count += 1

            await session.commit()

        print(f"✅ Loaded {chapter_count} chapters and {verse_count} verses")

    await engine.dispose()


async def main():
    """Main entry point."""
    import os

    # Get database URL from environment or use default
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://bible:bible123@localhost:5432/bibledb"  # pragma: allowlist secret
    )

    # Download Bible
    bible_path = Path(__file__).parent.parent / "data" / "bible" / "kjv.json"
    bible_data = await download_bible(bible_path)

    # Load to database
    print(f"\n🗄️ Loading to database: {database_url}")
    await load_bible_to_db(database_url, bible_data)

    print("\n🎉 Bible loaded successfully!")
    print("Next step: Run create_embeddings.py to generate semantic search vectors")


if __name__ == "__main__":
    asyncio.run(main())
