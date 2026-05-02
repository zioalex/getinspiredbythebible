# Migration Best Practices & Guidelines

**Version:** 1.0
**Last Updated:** 2026-03-04
**Owner:** Product & Engineering Team

---

## Overview

This document provides guidelines for creating database migrations in the "Get Inspired by the Bible" project. Following these practices ensures migrations run reliably in all environments (local dev, CI/CD, Azure production).

---

## Quick Start: Migration Template

Use this template for all new migrations:

```python
#!/usr/bin/env python3
"""
Database migration: [Brief description]

Purpose:
- [What this migration does]
- [Why it's needed]

Run with: python scripts/migrations/XXX_migration_name.py
"""

import asyncio
import os
import sys

import asyncpg

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from config import settings  # noqa: E402
from utils import get_migration_connection_params  # noqa: E402


async def run_migration():
    """Execute the migration."""
    print("=" * 60)
    print("Migration: XXX_migration_name")
    print("=" * 60)

    # IMPORTANT: Use helper function for SSL-aware connection
    clean_url, conn_kwargs = get_migration_connection_params(settings.database_url)

    print("Connecting to database...")
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        # Check if migration already applied (idempotency)
        print("Checking if migration already applied...")
        already_applied = await conn.fetchval("""
            -- Example: Check if table/column exists
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'your_table'
            );
        """)

        if already_applied:
            print("✅ Migration already applied — skipping")
            return

        # Begin transaction
        print("Starting transaction...")
        async with conn.transaction():
            # Your migration SQL here
            print("Creating table...")
            await conn.execute("""
                CREATE TABLE your_table (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    -- Add your columns
                );
            """)

            print("Creating indexes...")
            await conn.execute("""
                CREATE INDEX idx_your_index ON your_table(column_name);
            """)

            # Add more operations as needed

        print("✅ Migration completed successfully")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

    finally:
        await conn.close()
        print("Database connection closed")


if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Database URL: {settings.database_url[:30]}...")  # Don't print full URL with password

    asyncio.run(run_migration())
```

---

## Critical Rules

### 🔴 Rule #1: NEVER Pass SSL Parameters in Connection URL

**❌ WRONG:**

```python
database_url = "postgresql://user:pass@host/db?ssl=require" # pragma: allowlist secret
conn = await asyncpg.connect(database_url)  # ❌ WILL FAIL
```

**✅ CORRECT:**

```python
from utils import get_migration_connection_params

clean_url, conn_kwargs = get_migration_connection_params(settings.database_url)
conn = await asyncpg.connect(clean_url, **conn_kwargs)  # ✅ Works in all envs
```

**Why?** asyncpg doesn't accept SSL configuration as URL query parameters. SSL must be passed via the `ssl` connection argument.

**Background:** See `api/scripture/database.py` for the backend implementation that inspired this pattern.

---

### 🟡 Rule #2: Always Make Migrations Idempotent

Migrations should be safe to run multiple times without causing errors.

**✅ Use these patterns:**

```python
# For table creation
CREATE TABLE IF NOT EXISTS ...

# For column addition
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='your_table' AND column_name='new_column'
    ) THEN
        ALTER TABLE your_table ADD COLUMN new_column TEXT;
    END IF;
END
$$;

# For constraint changes
DO $$
BEGIN
    -- Drop old constraint if exists
    ALTER TABLE your_table DROP CONSTRAINT IF EXISTS old_constraint_name;

    -- Add new constraint
    ALTER TABLE your_table ADD CONSTRAINT new_constraint_name
        CHECK (column IN ('value1', 'value2', 'value3'));
END
$$;
```

**Why?** If a migration fails partway through, you can re-run it safely after fixing the issue.

---

### 🟡 Rule #3: Use Transactions for Multi-Step Migrations

**✅ CORRECT:**

```python
async with conn.transaction():
    await conn.execute("CREATE TABLE ...")
    await conn.execute("CREATE INDEX ...")
    await conn.execute("INSERT INTO ...")
```

**Why?** If any step fails, all changes are rolled back. The database stays in a consistent state.

---

### 🟢 Rule #4: Check Migration State Before Running

Always check if the migration has already been applied:

```python
# Check if table exists
table_exists = await conn.fetchval("""
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'your_table'
    );
""")

if table_exists:
    print("✅ Migration already applied — skipping")
    return

# Check if column exists
column_exists = await conn.fetchval("""
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='your_table' AND column_name='new_column'
    );
""")

# Check if constraint exists
constraint_exists = await conn.fetchval("""
    SELECT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'your_constraint_name'
    );
""")
```

---

### 🟢 Rule #5: Use Clear, Verbose Logging

```python
print("=" * 60)
print("Migration: 003_add_user_preferences")
print("=" * 60)
print("Connecting to database...")
print("Checking if migration already applied...")
print("Creating user_preferences table...")
print("Adding indexes...")
print("✅ Migration completed successfully")
```

**Why?** Makes it easy to debug failures in CI/CD logs.

---

### 🟢 Rule #6: Name Migrations with Sequential Numbers

**Format:** `XXX_descriptive_name.py`

**Examples:**

- `001_add_feedback_tables.py`
- `002_add_spiritual_contact_subject.py`
- `003_tune_postgresql_config.sql`
- `004_add_user_preferences.py`

**Why?** Makes it obvious which order migrations should run in.

---

## Common Patterns

### Pattern: Add a New Table

```python
print("Creating new table...")
await conn.execute("""
    CREATE TABLE IF NOT EXISTS new_table (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        metadata JSONB DEFAULT '{}'::jsonb
    );
""")

print("Adding indexes...")
await conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_new_table_name
    ON new_table(name);
""")

await conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_new_table_created
    ON new_table(created_at DESC);
""")
```

---

### Pattern: Add a Column to Existing Table

```python
print("Adding new column...")
await conn.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='existing_table' AND column_name='new_column'
        ) THEN
            ALTER TABLE existing_table
            ADD COLUMN new_column TEXT DEFAULT 'default_value';
        END IF;
    END
    $$;
""")
```

---

### Pattern: Modify a CHECK Constraint

```python
print("Updating CHECK constraint...")

# Check current constraint
current_constraint = await conn.fetchval("""
    SELECT pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'your_table'::regclass
      AND contype = 'c'
      AND conname LIKE '%column_name%';
""")

print(f"Current constraint: {current_constraint}")

# Drop old constraint
await conn.execute("""
    ALTER TABLE your_table
    DROP CONSTRAINT IF EXISTS your_table_column_name_check;
""")

# Add new constraint
await conn.execute("""
    ALTER TABLE your_table
    ADD CONSTRAINT your_table_column_name_check
    CHECK (column_name IN ('value1', 'value2', 'value3', 'new_value'));
""")

# Verify new constraint
new_constraint = await conn.fetchval("""
    SELECT pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'your_table'::regclass
      AND contype = 'c'
      AND conname = 'your_table_column_name_check';
""")

print(f"New constraint: {new_constraint}")
```

---

### Pattern: Create a pgvector Index

```python
print("Creating HNSW index for vector search...")
await conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_passages_embedding_hnsw
    ON passages
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
""")

print("Analyzing table for query planner...")
await conn.execute("ANALYZE passages;")
```

---

## Testing Your Migration

### Step 1: Test Locally (No SSL)

```bash
# Set local database URL (no SSL)
export DATABASE_URL="postgresql://user:pass@localhost:5432/bible_db" # pragma: allowlist secret

# Run migration
python scripts/migrations/XXX_your_migration.py

# Verify results
psql $DATABASE_URL -c "\d+ your_table"
```

---

### Step 2: Test Idempotency

```bash
# Run migration again — should skip gracefully
python scripts/migrations/XXX_your_migration.py

# Should print: "✅ Migration already applied — skipping"
```

---

### Step 3: Test in CI/CD

```bash
# Push to a feature branch
git checkout -b feat/your-migration
git add scripts/migrations/XXX_your_migration.py
git commit -m "feat(db): add migration for [description]"
git push origin feat/your-migration

# Create PR
gh pr create --title "Add migration: [description]"

# Workflow will run migrations automatically if:
# - Migration scripts changed
# - Pushing to main (after PR merge)
```

---

### Step 4: Test in Production (Manual Trigger)

```bash
# After PR merges, manually trigger if needed
gh workflow run azure-deploy.yml --ref main \
  -f action=deploy \
  -f skip_build=true \
  -f skip_database_seed=true

# Check workflow logs
gh run list --workflow=azure-deploy.yml --limit=1
gh run view <RUN_ID> --log

# Verify in production DB
az postgres flexible-server connect \
  --name <db-name> \
  --admin-user <user> \
  --database bible_db

# Or via psql
psql $AZURE_DATABASE_URL -c "SELECT * FROM your_table LIMIT 5;"
```

---

## Troubleshooting

### Issue: "parameter 'ssl' cannot be changed now"

**Cause:** You're passing SSL parameters in the connection URL.

**Fix:** Use the `get_migration_connection_params()` helper:

```python
from utils import get_migration_connection_params

clean_url, conn_kwargs = get_migration_connection_params(settings.database_url)
conn = await asyncpg.connect(clean_url, **conn_kwargs)
```

---

### Issue: "relation 'table_name' does not exist"

**Cause:** Migration depends on another migration that hasn't run yet.

**Fix:**

1. Check migration order (run by numeric prefix: 001, 002, 003...)
2. Add dependency check at start of migration:

```python
table_exists = await conn.fetchval("""
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'dependent_table'
    );
""")

if not table_exists:
    print("❌ Dependency not met: run migration XXX first")
    return
```

---

### Issue: "duplicate key value violates unique constraint"

**Cause:** Migration is not idempotent and is trying to insert data that already exists.

**Fix:** Use `INSERT ... ON CONFLICT DO NOTHING`:

```python
await conn.execute("""
    INSERT INTO your_table (id, name, value)
    VALUES (1, 'config_key', 'config_value')
    ON CONFLICT (id) DO NOTHING;
""")
```

---

### Issue: Migration takes too long / times out

**Cause:** Large table operations (e.g., adding index on millions of rows).

**Fix:** Use `CONCURRENTLY` for index creation:

```python
# Note: Can't run inside a transaction block
print("Creating index (this may take a while)...")
await conn.execute("""
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_large_table
    ON large_table(column_name);
""")
```

For `CONCURRENTLY`, don't wrap in `async with conn.transaction()`.

---

## File Structure

```
scripts/
└── migrations/
    ├── utils.py                           # Helper functions (SSL handling)
    ├── 001_add_feedback_tables.py         # Migration 1
    ├── 002_add_spiritual_contact_subject.py # Migration 2
    ├── 003_tune_postgresql_config.sql     # SQL-only migration
    └── XXX_your_new_migration.py          # Your migration
```

---

## Helper Functions Reference

### `get_migration_connection_params(database_url: str)`

Located in `scripts/migrations/utils.py`

**Purpose:** Parse database URL and extract SSL parameters for asyncpg-compatible connection.

**Usage:**

```python
from utils import get_migration_connection_params

clean_url, conn_kwargs = get_migration_connection_params(settings.database_url)
conn = await asyncpg.connect(clean_url, **conn_kwargs)
```

**What it does:**

1. Strips `?ssl=require` or `?sslmode=require` from URL
2. Creates SSL context when required
3. Returns clean URL + connection kwargs dict

**Handles:**

- Local dev (no SSL)
- Azure production (SSL required)
- Both `postgresql://` and `postgresql+asyncpg://` schemes

---

## CI/CD Integration

### When Migrations Run Automatically

Migrations run in the `run-migrations` job if:

1. Files in `scripts/migrations/` changed
2. NOT a pull request (only on merge to main)
3. Deploy job succeeded OR was skipped

### Manual Trigger

```bash
gh workflow run azure-deploy.yml --ref main \
  -f action=deploy \
  -f skip_build=true \
  -f skip_database_seed=true
```

### Workflow File

See `.github/workflows/azure-deploy.yml` → `run-migrations` job

---

## Migration Checklist

Before creating a PR with your migration:

- [ ] Used the migration template
- [ ] Imported and used `get_migration_connection_params()` for connection
- [ ] Made migration idempotent (safe to run multiple times)
- [ ] Used transactions for multi-step operations
- [ ] Added clear logging messages
- [ ] Tested locally (with and without SSL)
- [ ] Tested idempotency (ran migration twice)
- [ ] Documented what the migration does (docstring)
- [ ] Named file with sequential number: `XXX_description.py`
- [ ] Committed to feature branch, not main

---

## Long-Term Solution: Alembic

**Note:** This manual migration approach is temporary. We plan to migrate to Alembic (tracked in BITB-004) for:

- Automatic migration generation from model changes
- Built-in versioning and dependency tracking
- Rollback support
- Better integration with SQLAlchemy

Until then, follow these guidelines for all manual migrations.

---

## Questions?

**Need help with a migration?**

- Check this guide first
- Look at existing migrations in `scripts/migrations/` for examples
- Reference backend's `api/scripture/database.py` for SSL handling
- Ask in team chat or open an issue

**Found a better pattern?**

- Update this document
- Open a PR with improvements
- Share with the team

---

## References

- Backend SSL handling: `api/scripture/database.py` → `get_async_database_url()`
- CI workflow: `.github/workflows/azure-deploy.yml` → `run-migrations` job
- Existing migrations: `scripts/migrations/001_*.py`, `002_*.py`
- asyncpg docs: <https://magicstack.github.io/asyncpg/current/>
- PostgreSQL docs: <https://www.postgresql.org/docs/current/>

---

**Version History:**

- 1.0 (2026-03-04): Initial version after SSL connection bug discovery
