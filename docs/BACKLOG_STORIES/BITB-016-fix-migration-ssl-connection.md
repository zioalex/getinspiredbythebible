# BITB-016: Fix Migration Scripts SSL Connection Error

**Priority:** P0 (Critical/Blocker)
**Status:** ✅ Done (PR #227 merged 2026-03-04)
**Size:** S (< 1 hour)
**Created:** 2026-03-04
**Completed:** 2026-03-04

---

## User Story

**As a** developer running database migrations in CI/CD,
**I want** migration scripts to handle SSL connections correctly,
**so that** migrations can run successfully in Azure production environment.

---

## Problem Statement

**Current Error:**

```text
asyncpg.exceptions.CantChangeRuntimeParamError: parameter "ssl" cannot be changed now
```

**Root Cause:**
The migration scripts (`001_add_feedback_tables.py`, `002_add_spiritual_contact_subject.py`) are
passing the full `DATABASE_URL` with `?ssl=require` query parameter to `asyncpg.connect()`.

**Technical Issue:**
asyncpg does NOT support SSL configuration as a URL query parameter (unlike psycopg2).
SSL settings must be passed as a separate `ssl` parameter to the connection function.

**Impact:**

- **Severity:** P0 - Blocks all production migrations
- **Current State:** PR #224 migration (`002_add_spiritual_contact_subject.py`) failed in CI
- **Affected Scripts:** All Python migration scripts in `scripts/migrations/`

---

## Existing Solution

The backend already solves this in `api/scripture/database.py`:

```python
def get_async_database_url() -> tuple[str, dict]:
    """
    Convert database URL to async version and extract SSL settings.

    asyncpg doesn't support sslmode as a URL parameter like psycopg2.
    We need to extract it and pass SSL config via connect_args.
    """
    url = settings.database_url
    connect_args: dict = {}

    # Parse URL to extract and remove ssl/sslmode parameter
    parsed = urlparse(url)
    if parsed.query:
        query_params = parse_qs(parsed.query)
        sslmode = query_params.pop("sslmode", [None])[0]
        ssl_param = query_params.pop("ssl", [None])[0]

        # Rebuild URL without ssl parameters
        new_query = urlencode(query_params, doseq=True) if query_params else ""
        url = urlunparse(parsed._replace(query=new_query))

        # Configure SSL for asyncpg
        if sslmode in ("require", "verify-ca", "verify-full") or ssl_param == "require":
            ssl_context = ssl.create_default_context()
            if sslmode == "require" or ssl_param == "require":
                # Don't verify certificate
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context

    return url, connect_args
```

---

## Functional Requirements

- [ ] Migration scripts parse `DATABASE_URL` to extract SSL parameters
- [ ] SSL parameters removed from connection URL
- [ ] SSL context created and passed to `asyncpg.connect()` via `ssl` parameter
- [ ] Solution works for both local dev (no SSL) and Azure production (SSL required)
- [ ] All existing migration scripts updated with fix
- [ ] Future migration template created to prevent recurrence

---

## Non-Functional Requirements

- **Reliability:** Migrations must work in both dev and prod environments
- **Maintainability:** Reusable helper function to avoid code duplication
- **Backward Compatibility:** Must work with existing `DATABASE_URL` formats
- **Security:** SSL verification level must match production requirements

---

## Acceptance Criteria

**Code Changes:**

- [ ] Create helper function `get_migration_connection_params(database_url: str) -> tuple[str, dict]` in a new file `scripts/migrations/utils.py`
- [ ] Helper function:
  - Parses URL to extract `?ssl=require` or `?sslmode=require`
  - Creates SSL context when required
  - Returns clean URL + connection kwargs
- [ ] Update `001_add_feedback_tables.py`:
  - Import helper function
  - Replace `conn = await asyncpg.connect(database_url)` with:

    ```python
    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)
    ```

- [ ] Update `002_add_spiritual_contact_subject.py` with same fix
- [ ] Update any other Python migration scripts in `scripts/migrations/`

**Testing:**

- [ ] Manual test: Run migrations locally (no SSL) - should work
- [ ] CI test: Trigger workflow dispatch to run migrations in Azure - should work
- [ ] Verify PR #224 migration runs successfully:

  ```sql
  SELECT conname, pg_get_constraintdef(oid)
  FROM pg_constraint
  WHERE conrelid = 'contact_submissions'::regclass
    AND contype = 'c'
    AND conname LIKE '%subject%';
  ```

  Expected: constraint includes `'spiritual'`

**Documentation:**

- [ ] Comment in `utils.py` explains why SSL can't be in URL
- [ ] Reference backend's `get_async_database_url()` as inspiration
- [ ] Update migration template (if exists) or create one

---

## Tech Constraints

- Must use Python standard library `ssl` module
- Must handle both `?ssl=require` and `?sslmode=require` formats
- Must work with Python 3.12 (current CI Python version)
- Must not break existing backend SSL handling
- Should reuse logic from `api/scripture/database.py` where possible

---

## Out of Scope

- Refactoring backend's `get_async_database_url()` (already works correctly)
- Converting to Alembic migration framework (tracked in BITB-004)
- Adding SSL certificate verification (current behavior is `ssl=require` without verification)
- Changing CI workflow (workflow is correct, scripts are broken)

---

## Implementation Plan

### Option A: Copy Helper to Migration Utils (Recommended)

1. Create `scripts/migrations/utils.py`
2. Copy and adapt `get_async_database_url()` from backend
3. Rename to `get_migration_connection_params()`
4. Update all migration scripts to use helper

**Pros:** Self-contained, migrations don't depend on backend code
**Cons:** Small code duplication

### Option B: Import from Backend

1. Import `get_async_database_url()` from `api/scripture/database.py`
2. Update migration scripts to use it

**Pros:** No code duplication
**Cons:** Migrations depend on backend imports (could break if backend refactored)

**Recommendation:** **Option A** - migrations should be self-contained.

---

## Example Implementation

### `scripts/migrations/utils.py` (new file)

```python
"""
Utility functions for database migrations.
"""

import ssl
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def get_migration_connection_params(database_url: str) -> tuple[str, dict]:
    """
    Parse database URL and extract SSL parameters for asyncpg.

    asyncpg doesn't support ssl/sslmode as URL query parameters.
    This function extracts them and returns a clean URL plus connection kwargs.

    Args:
        database_url: Database URL (may include ?ssl=require or ?sslmode=require)

    Returns:
        Tuple of (clean_url, connection_kwargs)

    Example:
        >>> url = "postgresql://user:pass@host/db?ssl=require"  # pragma: allowlist secret
        >>> clean_url, kwargs = get_migration_connection_params(url)
        >>> conn = await asyncpg.connect(clean_url, **kwargs)
    """
    url = database_url
    conn_kwargs: dict = {}

    # Convert postgresql+asyncpg:// to postgresql:// (asyncpg format)
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")

    # Parse URL to extract SSL parameters
    parsed = urlparse(url)
    if parsed.query:
        query_params = parse_qs(parsed.query)

        # Extract ssl/sslmode parameters
        sslmode = query_params.pop("sslmode", [None])[0]
        ssl_param = query_params.pop("ssl", [None])[0]

        # Rebuild URL without SSL parameters
        new_query = urlencode(query_params, doseq=True) if query_params else ""
        url = urlunparse(parsed._replace(query=new_query))

        # Configure SSL context if required
        if sslmode in ("require", "verify-ca", "verify-full") or ssl_param == "require":
            ssl_context = ssl.create_default_context()
            # For 'require' mode: don't verify certificate (matches psycopg2 behavior)
            if sslmode == "require" or ssl_param == "require":
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            conn_kwargs["ssl"] = ssl_context

    return url, conn_kwargs
```

### Updated Migration Script Pattern

```python
#!/usr/bin/env python3
import asyncio
import os
import sys
import asyncpg

# Add directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from config import settings  # noqa: E402
from utils import get_migration_connection_params  # noqa: E402


async def run_migration():
    """Run the migration."""
    print("Connecting to database...")

    # Get connection params with SSL handling
    clean_url, conn_kwargs = get_migration_connection_params(settings.database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        # Migration logic here
        print("Running migration...")
        await conn.execute("...")
        print("✅ Migration complete")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
```

---

## Verification Steps

**After Fix:**

```bash
# 1. Run locally (no SSL)
export DATABASE_URL="postgresql://user:pass@localhost:5432/db"  # pragma: allowlist secret
python scripts/migrations/001_add_feedback_tables.py
# Should work ✅

# 2. Trigger in CI (with SSL)
gh workflow run azure-deploy.yml --ref main \
  -f action=deploy \
  -f skip_build=true \
  -f skip_database_seed=true

# 3. Check workflow logs
gh run list --workflow=azure-deploy.yml --limit=1
gh run view <RUN_ID> --log

# 4. Verify in production DB
psql $DATABASE_URL -c "
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'contact_submissions'::regclass
  AND contype = 'c'
  AND conname LIKE '%subject%';"

# Expected: constraint includes 'spiritual'
```

---

## Related Items

- **Blocker for:** PR #224 migration (still not run)
- **Related to:** BITB-014 (migration pipeline fix - completed)
- **Related Code:** `api/scripture/database.py` (backend SSL handling)
- **Long-term Solution:** BITB-004 (Alembic migration framework)

---

## Risk Assessment

**Risk Level:** Low
**Rationale:**

- Small change (add helper function, update 2-3 files)
- Solution already proven in backend code
- Easy to test locally before CI
- No production impact until migrations run

**Mitigation:**

- Test locally with and without SSL first
- Use exact same SSL logic as backend
- Verify in dev environment before production
- Keep migration scripts idempotent (safe to re-run)

---

## Files to Modify

1. `scripts/migrations/utils.py` (new file - helper function)
2. `scripts/migrations/001_add_feedback_tables.py` (update connection logic)
3. `scripts/migrations/002_add_spiritual_contact_subject.py` (update connection logic)
4. Any other `scripts/migrations/*.py` files (if they exist)

---

## Estimated Time

- **Coding:** 30 minutes (create helper, update scripts)
- **Testing:** 15 minutes (local + CI)
- **Total:** < 1 hour

---

**Priority:** P0 - Must fix before any migrations can run in production
