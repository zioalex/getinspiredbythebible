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
    echo "Loading Bible data (KJV by default)..."
    echo "To load other translations: python load_bible.py --translation <code>"
    echo "To load all translations: python load_bible.py --all"
    python3 -u load_bible.py

    echo "Creating embeddings..."
    python3 -u create_embeddings.py

    echo "Database initialization complete!"
    echo ""
    echo "Additional translations available:"
    echo "  - KJV (King James Version) - loaded"
    echo "  - WEB (World English Bible) - run: python load_bible.py --translation web"
    echo "  - Italian (Riveduta 1927) - run: python load_bible.py --translation ita1927"
    echo "  - German (Luther 1912) - run: python load_bible.py --translation deu1912"
else
    echo "Database already initialized, skipping."
fi
