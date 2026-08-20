#!/bin/bash
set -e

echo "=== Applying database migrations (legacy scripts/migrations) ==="
python3 -u migrations/run_migrations.py
echo ""

# Alembic owns new schema changes (BITB-004/089), but until now this dev stack
# never ran it: the schema came from scripts/init.sql plus the legacy runner
# above, while production runs `alembic upgrade head` from the deploy pipeline.
# Two environments on two different migration systems is how a revision can be
# correct in production and missing here -- which is exactly what happened when
# BITB-062's legacy half was dropped as redundant and every `SELECT verses.*`
# started failing in the compose stack.
#
# The stamp mirrors the production cutover (docs/MIGRATION_GUIDELINES.md): a
# database built by init.sql already has the r0001 baseline schema, it just has
# no bookkeeping to say so. Stamping records that, and `upgrade head` then
# applies only the revisions after it -- so an existing volume picks up new
# columns instead of silently lacking them.
#
# `python3 -m alembic` rather than the `alembic` console script: the module is
# installed via api/requirements.txt, but this entrypoint should not depend on
# the script directory being on PATH in that image. Matches how
# api/tests/test_alembic_migrations.py invokes it.
#
# PYTHONDONTWRITEBYTECODE: /api is a read-only bind mount here, so alembic must
# not try to write __pycache__ next to env.py.
echo "=== Applying Alembic migrations ==="
(
  cd /api
  export PYTHONDONTWRITEBYTECODE=1
  if [ -z "$(python3 -m alembic current 2>/dev/null | tail -n1 | tr -d '[:space:]')" ]; then
    echo "No alembic_version row -- stamping r0001 (schema came from init.sql)"
    python3 -m alembic stamp r0001
  fi
  python3 -m alembic upgrade head
  python3 -m alembic current
)
echo ""

echo "=== Translation status before load ==="
python3 -u load_bible.py --status
echo ""

echo "Checking if database needs initialization..."

# Check verse count using a here-doc to avoid quoting issues
VERSE_COUNT=$(python3 -u <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

async def check():
    url = os.environ['DATABASE_URL']
    # create_async_engine needs the asyncpg dialect; accept plain postgresql:// too
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    engine = create_async_engine(url)
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
    echo "  - German (Schlachter 1951) - run: python load_bible.py --translation schlachter"
else
    echo "Database already initialized, skipping."
fi
