#!/usr/bin/env python3
"""
Generate embeddings for Bible verses.

This script creates vector embeddings for all verses to enable
semantic search functionality.

Usage:
    python create_embeddings.py           # Generate embeddings for all verses
    python create_embeddings.py --ci      # CI mode: only 1 Corinthians (for testing)

Requirements:
    - Ollama running with mxbai-embed-large model (multilingual, 1024 dimensions)
    - Bible data already loaded (run load_bible.py first)
"""

import argparse
import asyncio
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Books to process in CI mode (minimal set for testing semantic search)
# 1 Corinthians contains the famous "love chapter" (chapter 13)
CI_MODE_BOOKS = ["1 Corinthians"]


def log(message: str, flush: bool = True) -> None:
    """Print timestamped log message, flushed immediately for CI visibility."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=flush)


class OllamaEmbedder:
    """Simple Ollama embedding client."""

    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        response = await self.client.post(
            f"{self.host}/api/embeddings", json={"model": self.model, "prompt": text}
        )
        response.raise_for_status()
        return response.json()["embedding"]

    async def embed_batch(self, texts: list[str], batch_size: int = 10) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await asyncio.gather(*[self.embed(t) for t in batch])
            embeddings.extend(batch_embeddings)
        return embeddings

    async def close(self):
        await self.client.aclose()


async def check_ollama(host: str, model: str) -> bool:
    """Check if Ollama is running with the required model."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{host}/api/tags")
            response.raise_for_status()

            models = [m["name"] for m in response.json().get("models", [])]

            if not any(model.split(":")[0] in m for m in models):
                log(f"❌ Model '{model}' not found in Ollama")
                log(f"   Available models: {models}")
                log(f"\n   To install: ollama pull {model}")
                return False

            return True
    except httpx.ConnectError:
        log(f"❌ Cannot connect to Ollama at {host}")
        log("   Make sure Ollama is running: ollama serve")
        return False


async def create_embeddings(
    database_url: str, ollama_host: str, model: str, books_filter: list = None
):
    """Generate embeddings for verses.

    Args:
        database_url: PostgreSQL connection string
        ollama_host: Ollama server URL
        model: Embedding model name
        books_filter: Optional list of book names to process (None = all books)
    """

    try:
        # Check Ollama
        if not await check_ollama(ollama_host, model):
            return

        # Convert to async URL for asyncpg
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg uses 'ssl' instead of 'sslmode'
        database_url = database_url.replace("sslmode=", "ssl=")

        engine = create_async_engine(database_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        embedder = OllamaEmbedder(ollama_host, model)

        try:
            async with async_session() as session:
                # Build query — optionally filter by book
                if books_filter:
                    # Create placeholders for book names
                    placeholders = ", ".join(f":book_{i}" for i in range(len(books_filter)))
                    query = f"""
                        SELECT v.id, v.text, b.name, v.chapter_number, v.verse_number
                        FROM verses v
                        JOIN books b ON v.book_id = b.id
                        WHERE v.embedding IS NULL AND b.name IN ({placeholders})
                        ORDER BY b.position, v.chapter_number, v.verse_number
                    """
                    params = {f"book_{i}": name for i, name in enumerate(books_filter)}
                    result = await session.execute(text(query), params)
                else:
                    result = await session.execute(text("""
                            SELECT v.id, v.text, b.name, v.chapter_number, v.verse_number
                            FROM verses v
                            JOIN books b ON v.book_id = b.id
                            WHERE v.embedding IS NULL
                            ORDER BY b.position, v.chapter_number, v.verse_number
                        """))
                verses = result.fetchall()

                if not verses:
                    log("✅ All verses already have embeddings!")
                    return

                total = len(verses)
                batch_size = 50
                total_batches = (total + batch_size - 1) // batch_size

                log(f"📊 Generating embeddings for {total} verses...")
                log(f"   Using model: {model}")
                log(f"   Batch size: {batch_size} verses/batch — {total_batches} batches total")
                log("")

                processed = 0
                overall_start = time.time()

                for i in range(0, total, batch_size):
                    batch = verses[i : i + batch_size]
                    batch_num = i // batch_size + 1
                    pct = (i / total) * 100

                    log(
                        f"  ⚙️  Batch {batch_num}/{total_batches}"
                        f" — verses {i+1}–{min(i+batch_size, total)}"
                        f" ({pct:.0f}%) ..."
                    )

                    batch_start = time.time()

                    # Create texts for embedding — include reference for better context
                    texts = [f"{row[2]} {row[3]}:{row[4]} - {row[1]}" for row in batch]

                    # Generate embeddings
                    embeddings = await embedder.embed_batch(texts, batch_size=10)

                    # Batch update database — one executemany instead of N round-trips
                    update_batch = [
                        {
                            "verse_id": verse_id,
                            "embedding": "[" + ",".join(str(x) for x in embeddings[j]) + "]",
                        }
                        for j, (verse_id, _, book_name, chapter, verse_num) in enumerate(batch)
                    ]
                    await session.execute(
                        text(
                            "UPDATE verses SET embedding = CAST(:embedding AS vector)"
                            " WHERE id = :verse_id"
                        ),
                        update_batch,
                    )
                    await session.commit()

                    processed += len(batch)
                    elapsed_batch = time.time() - batch_start
                    elapsed_total = time.time() - overall_start
                    rate = processed / elapsed_total if elapsed_total > 0 else 0
                    remaining = total - processed
                    eta_seconds = remaining / rate if rate > 0 else 0
                    current_ref = f"{batch[-1][2]} {batch[-1][3]}:{batch[-1][4]}"

                    log(f"      ✓ batch done in {elapsed_batch:.1f}s" f" — last ref: {current_ref}")
                    log(
                        f"        {processed}/{total} verses"
                        f"  rate={rate:.0f} v/s"
                        f"  ETA≈{eta_seconds/60:.1f}min"
                    )

                log(f"\n✅ Generated embeddings for {processed} verses")

                # Create index for faster search
                log("\n📇 Creating vector index...")
                await session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_verse_embedding_cosine
                        ON verses
                        USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100)
                    """))
                await session.commit()
                log("✅ Index created")

        finally:
            await embedder.close()
            await engine.dispose()

    except Exception as e:
        log(f"❌ Error generating embeddings: {e}")
        log(traceback.format_exc())
        raise


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate embeddings for Bible verses")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: process only 1 Corinthians (minimal data for testing semantic search)",
    )
    args = parser.parse_args()

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://bible:bible123@localhost:5432/bibledb",  # pragma: allowlist secret
    )

    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    embedding_model = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")

    # Determine books filter (CI mode processes only specific books)
    books_filter = CI_MODE_BOOKS if args.ci else None

    log("🔍 Bible Embedding Generator")
    log(f"   Database: {database_url}")
    log(f"   Ollama: {ollama_host}")
    log(f"   Model: {embedding_model}")
    if books_filter:
        log(f"   CI mode: processing only {', '.join(books_filter)}")
    log("")

    await create_embeddings(database_url, ollama_host, embedding_model, books_filter)

    log("\n🎉 Done! Your Bible is now searchable with semantic search.")


if __name__ == "__main__":
    asyncio.run(main())
