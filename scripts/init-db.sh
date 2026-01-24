#!/bin/bash
set -e

echo "Checking if database needs initialization..."

# Check verse count using a here-doc to avoid quoting issues
VERSE_COUNT=$(python3 -u <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

async def check():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT COUNT(*) FROM verses'))
        count = result.scalar()
    await engine.dispose()
    return count

count = asyncio.run(check())
print(count)
EOF
)

echo "Found $VERSE_COUNT verses in database"

if [ "$VERSE_COUNT" -eq 0 ]; then
    echo "Loading Bible data..."
    python3 -u load_bible.py

    echo "Creating embeddings..."
    python3 -u create_embeddings.py

    echo "Database initialization complete!"
else
    echo "Database already initialized, skipping."
fi
