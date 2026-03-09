#!/usr/bin/env python3
"""
Generate embeddings for Bible verses using Azure OpenAI.

This script creates vector embeddings for all verses using Azure OpenAI's
text-embedding-3-small model (1536 dimensions).

Usage:
    python create_azure_embeddings.py

Environment Variables Required:
    AZURE_OPENAI_ENDPOINT     - Azure OpenAI resource endpoint
    AZURE_OPENAI_API_KEY      - Azure OpenAI API key
    AZURE_EMBEDDING_DEPLOYMENT - Deployment name (default: text-embedding-3-small)
    DATABASE_URL              - PostgreSQL connection string

Requirements:
    - Azure OpenAI resource with embedding model deployed
    - Bible data already loaded (run load_bible.py first)
"""

import asyncio
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from openai import AsyncAzureOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def log(message: str, flush: bool = True) -> None:
    """Print timestamped log message, flushed immediately for CI visibility."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=flush)


class AzureOpenAIEmbedder:
    """Azure OpenAI embedding client with batch support."""

    def __init__(self, endpoint: str, api_key: str, deployment_name: str):
        self.deployment_name = deployment_name
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-01",
        )

    async def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Azure OpenAI supports native batching which is more efficient.
        Rate limits: 120,000 tokens per minute for standard deployments.
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self.client.embeddings.create(
                input=batch,
                model=self.deployment_name,
            )
            for item in response.data:
                embeddings.append(item.embedding)

            # Small delay to respect rate limits
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)

        return embeddings


async def check_azure_openai(endpoint: str, api_key: str, deployment: str) -> bool:
    """Check if Azure OpenAI is accessible."""
    try:
        client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-01",
        )
        await client.embeddings.create(
            input="test",
            model=deployment,
        )
        return True
    except Exception as e:
        log(f"Cannot connect to Azure OpenAI: {e}")
        return False


async def create_embeddings(
    database_url: str,
    azure_endpoint: str,
    azure_api_key: str,
    deployment_name: str,
) -> bool:
    """Generate embeddings for all verses using Azure OpenAI.

    Returns:
        bool: True if successful, False if failed.
    """

    log("Checking Azure OpenAI connection...")
    if not await check_azure_openai(azure_endpoint, azure_api_key, deployment_name):
        log("Failed to connect to Azure OpenAI. Please check your configuration.")
        return False

    log("Azure OpenAI connection successful!")

    # Convert to async URL for asyncpg
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg uses 'ssl' instead of 'sslmode'
    database_url = database_url.replace("sslmode=", "ssl=")

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    embedder = AzureOpenAIEmbedder(azure_endpoint, azure_api_key, deployment_name)

    try:
        async with async_session() as session:
            # Get verses without embeddings
            result = await session.execute(text("""
                    SELECT v.id, v.text, b.name, v.chapter_number, v.verse_number
                    FROM verses v
                    JOIN books b ON v.book_id = b.id
                    WHERE v.embedding IS NULL
                    ORDER BY b.position, v.chapter_number, v.verse_number
                """))
            verses = result.fetchall()

            if not verses:
                log("All verses already have embeddings!")
                return True

            total = len(verses)
            batch_size = 100
            total_batches = (total + batch_size - 1) // batch_size

            log(f"Generating embeddings for {total} verses...")
            log(f"   Using deployment: {deployment_name}")
            log(f"   Dimensions: 1536 (text-embedding-3-small)")
            log(f"   Estimated cost: ~$0.02 per 1M tokens (~$0.20 total for Bible)")
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
                embeddings = await embedder.embed_batch(texts, batch_size=50)

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

            log(f"\nGenerated embeddings for {processed} verses")

            # Create index for faster search
            log("\nCreating vector index...")
            await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_verse_embedding_cosine
                    ON verses
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """))
            await session.commit()
            log("Index created")

            return True

    except Exception as e:
        log(f"❌ Error generating embeddings: {e}")
        log(traceback.format_exc())
        return False

    finally:
        await engine.dispose()


async def main():
    """Main entry point."""
    # Required environment variables
    # Strip whitespace to handle Windows line endings (\r\n) in env vars
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    deployment_name = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-small").strip()

    if not azure_endpoint:
        log("Error: AZURE_OPENAI_ENDPOINT environment variable is required")
        log("Example: https://your-resource.openai.azure.com/")
        sys.exit(1)

    if not azure_api_key:
        log("Error: AZURE_OPENAI_API_KEY environment variable is required")
        sys.exit(1)

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://bible:bible123@localhost:5432/bibledb",  # pragma: allowlist secret
    ).strip()

    log("Azure OpenAI Bible Embedding Generator")
    log(f"   Database: {database_url}")
    log(f"   Azure OpenAI: {azure_endpoint}")
    log(f"   Deployment: {deployment_name}")
    log("")

    success = await create_embeddings(
        database_url,
        azure_endpoint,
        azure_api_key,
        deployment_name,
    )

    if success:
        log("\nDone! Your Bible is now searchable with Azure OpenAI embeddings.")
    else:
        log("\nFailed to generate embeddings. See errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
