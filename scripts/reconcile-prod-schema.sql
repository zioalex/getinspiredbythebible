-- Reconcile the production schema with the ORM models (BITB-093).
--
-- WHY THIS EXISTS
-- ---------------
-- Production's schema was not built by one system. Some tables came from
-- SQLAlchemy's create_all() at app startup, some from scripts/init.sql and
-- scripts/migrations/. `verses` is visibly both: its FK columns are nullable
-- and its unique constraint carries a Postgres-generated name (create_all from
-- an older model revision), while `translation` has the NOT NULL DEFAULT 'kjv'
-- that only init.sql declares. create_all never ALTERs an existing table, so
-- every model change since those tables were first created lives in code only.
--
-- BITB-089 Stage 1 surfaced this: `alembic check` against a restored copy of
-- production reports a non-empty diff, which means the r0001 baseline is not a
-- truthful description of production and must not be stamped over.
--
-- This script converges production TO the models, so that `alembic check` comes
-- back clean and `alembic stamp r0001` becomes an honest statement. The other
-- half of the reconciliation goes the other way -- seven columns where
-- production has a server default the models never declared are fixed in the
-- models, not here (see BITB-093).
--
-- HOW TO RUN
-- ----------
--   1. Rehearse it on a restored copy first, never on production first. A
--      schema-only copy is enough to prove the resulting schema (add
--      -v allow_empty=1; see the note below the psql settings):
--        make db-backup-schema && make db-restore-local DUMP=backups/<file>.dump
--        PGPASSWORD=local psql "postgresql://postgres@localhost:5433/bibledb" \
--             -v allow_empty=1 -f scripts/reconcile-prod-schema.sql
--        make db-rehearse-alembic            # must now report a clean check
--
--      (password via PGPASSWORD, never in the URL -- the repo convention, see
--      docs/HOW-TO-BACKUP-RESTORE-DATABASE.md)
--
--   2. A schema-only rehearsal cannot check the data preconditions, so run these
--      two read-only queries against PRODUCTION before step 4. Both must be 0,
--      and a non-zero total proves you are not accidentally querying the empty
--      copy:
--        SELECT count(*) AS total,
--               count(*) FILTER (WHERE book_id IS NULL OR chapter_id IS NULL) AS bad
--          FROM verses;
--        SELECT count(*) FROM verses v
--          LEFT JOIN translations t ON v.translation = t.code
--         WHERE t.code IS NULL;      -- orphans would fail VALIDATE CONSTRAINT
--
--   3. Take a backup of production (Scenario D of docs/HOW-TO-BACKUP-RESTORE-DATABASE.md).
--   4. Run it against production -- WITHOUT allow_empty, so the guards are armed --
--      then re-run the rehearsal against a fresh copy.
--   5. Only then: DATABASE_URL="<prod>" alembic stamp r0001   (BITB-089 Stage 2)
--
-- PROPERTIES
-- ----------
--   * Fails closed. Every precondition is asserted; a surprise aborts the
--     transaction rather than half-applying.
--   * Idempotent. Re-running it is a no-op, so an interrupted run is safe to repeat.
--   * Renames constraints instead of dropping and recreating them. Autogenerate
--     proposes DROP + ADD, which rebuilds a unique index across the whole of
--     `verses` under an ACCESS EXCLUSIVE lock. RENAME CONSTRAINT is metadata-only
--     and instant.
--
-- LOCKING
-- -------
-- SET NOT NULL takes a brief ACCESS EXCLUSIVE lock and scans the table. `verses`
-- is ~400k rows (measured), so this is short but not free: run it in a quiet
-- window. Columns on the same table are combined into one ALTER TABLE so each
-- table is locked once. The FK change is split into ADD ... NOT VALID plus
-- VALIDATE so the row scan does not hold an exclusive lock.
--
-- PRIVILEGES
-- ----------
-- ALTER TABLE, RENAME CONSTRAINT and COMMENT ON all require table ownership, and
-- Azure Flexible Server gives no superuser. Tables created by create_all() are
-- owned by whichever role the application connects as, which need not be the
-- admin role you are running this with. Check before the production run:
--   SELECT current_user;
--   SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'public';
-- A mismatch fails on the first ALTER and rolls back -- no harm, but it is
-- better to find out before the maintenance window than during it.

\set ON_ERROR_STOP on

-- Rehearsing against a schema-only copy? Pass -v allow_empty=1.
--
-- The DDL below works perfectly on empty tables, and the question a rehearsal
-- answers -- "does `alembic check` come back clean afterwards?" -- is a pure
-- schema comparison that never reads a row. What an empty copy cannot do is
-- certify the data preconditions: a zero NULL count over zero rows is vacuous.
-- So the checks are skipped rather than silently passed, and the run says so.
--
-- Interpolation happens out here because psql does not substitute :variables
-- inside dollar-quoted blocks; set_config carries the value in instead.
\if :{?allow_empty}
\else
  \set allow_empty 0
\endif
SELECT set_config('reconcile.allow_empty', :'allow_empty', false);

BEGIN;

-- ---------------------------------------------------------------------------
-- Preconditions. Nothing below runs unless all of these hold.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    n bigint;
BEGIN
    SELECT count(*) INTO n FROM verses;
    IF n = 0 THEN
        IF current_setting('reconcile.allow_empty', true) = '1' THEN
            RAISE NOTICE '%', concat(
                'verses is empty -- schema-only rehearsal. Data preconditions ',
                'SKIPPED: this run proves the resulting schema, and nothing about ',
                'NULLs or FK orphans in production. Check those separately (see ',
                'the header) before running this against production.');
            RETURN;
        END IF;
        RAISE EXCEPTION
            'verses is empty. This looks like a schema-only copy, where the NULL '
            'checks below prove nothing. Run against production, against a copy '
            'restored with data, or re-run with -v allow_empty=1 to rehearse the '
            'DDL only.';
    END IF;

    -- Orphaned translation codes would make VALIDATE CONSTRAINT fail in step 4,
    -- after the earlier steps have already committed. Catch it up front.
    SELECT count(*) INTO n
      FROM verses v
      LEFT JOIN translations t ON v.translation = t.code
     WHERE t.code IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION
            'verses has % row(s) whose translation has no matching row in '
            'translations. The FK cannot be validated until these are resolved.', n;
    END IF;

    SELECT count(*) INTO n FROM verses WHERE book_id IS NULL OR chapter_id IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'verses has % row(s) with NULL book_id/chapter_id; backfill before SET NOT NULL', n;
    END IF;

    SELECT count(*) INTO n FROM chapters WHERE book_id IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'chapters has % row(s) with NULL book_id; backfill first', n;
    END IF;

    SELECT count(*) INTO n FROM feedback WHERE created_at IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'feedback has % row(s) with NULL created_at; backfill first', n;
    END IF;

    SELECT count(*) INTO n FROM contact_submissions WHERE created_at IS NULL OR status IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'contact_submissions has % row(s) with NULL created_at/status; backfill first', n;
    END IF;

    SELECT count(*) INTO n FROM translations
     WHERE license IS NULL OR is_default IS NULL OR created_at IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'translations has % row(s) with NULL license/is_default/created_at; backfill first', n;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 1. Constraint names. Production carries Postgres-generated names; both the
--    models and scripts/init.sql name these explicitly. Rename, do not rebuild.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chapters_book_id_number_key') THEN
        ALTER TABLE chapters RENAME CONSTRAINT chapters_book_id_number_key TO unique_chapter;
        RAISE NOTICE 'renamed chapters_book_id_number_key -> unique_chapter';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint
                WHERE conname = 'verses_book_id_chapter_number_verse_number_translation_key') THEN
        ALTER TABLE verses
            RENAME CONSTRAINT verses_book_id_chapter_number_verse_number_translation_key
                           TO unique_verse_translation;
        RAISE NOTICE 'renamed verses unique constraint -> unique_verse_translation';
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. NOT NULL. The models and scripts/init.sql agree these are mandatory;
--    only production (built by an older create_all) allows NULL.
-- ---------------------------------------------------------------------------
-- Columns on the same table are set in a single ALTER TABLE: one lock
-- acquisition and one pass instead of one per column. `verses` is ~400k rows,
-- so this is the difference between one brief ACCESS EXCLUSIVE window and two.
ALTER TABLE verses
    ALTER COLUMN book_id    SET NOT NULL,
    ALTER COLUMN chapter_id SET NOT NULL;

ALTER TABLE chapters ALTER COLUMN book_id SET NOT NULL;

ALTER TABLE feedback ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE contact_submissions
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN status     SET NOT NULL;

ALTER TABLE translations
    ALTER COLUMN license    SET NOT NULL,
    ALTER COLUMN is_default SET NOT NULL,
    ALTER COLUMN created_at SET NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Stray column comments. Two columns in production carry the literal comment
--    text 'comment'. Nothing in this repository sets a column comment -- no
--    COMMENT ON anywhere, no comment= on any model -- so these were applied by
--    hand. Left in place they appear in every future autogenerate diff.
-- ---------------------------------------------------------------------------
COMMENT ON COLUMN books.abbreviation IS NULL;
COMMENT ON COLUMN verses.embedding   IS NULL;

COMMIT;

-- ---------------------------------------------------------------------------
-- 4. Foreign key ON DELETE CASCADE, outside the transaction above so VALIDATE
--    can run without holding an exclusive lock for the scan.
--
--    ⚠️ BEHAVIOURAL CHANGE, NOT COSMETIC. After this, deleting a row from
--    `translations` deletes every verse of that translation. Both the model
--    (ondelete="CASCADE") and scripts/init.sql declare it; production is the
--    outlier. Confirm that is genuinely intended before running this section --
--    it is separated precisely so it can be skipped or deferred.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'verses_translation_fkey'
           AND confdeltype <> 'c'          -- 'c' = ON DELETE CASCADE
    ) THEN
        ALTER TABLE verses DROP CONSTRAINT verses_translation_fkey;
        ALTER TABLE verses
            ADD CONSTRAINT verses_translation_fkey
            FOREIGN KEY (translation) REFERENCES translations(code)
            ON DELETE CASCADE
            NOT VALID;
        RAISE NOTICE 'verses_translation_fkey recreated with ON DELETE CASCADE (NOT VALID)';
    END IF;
END
$$;

ALTER TABLE verses VALIDATE CONSTRAINT verses_translation_fkey;

-- ---------------------------------------------------------------------------
-- Verification. Expect: no NULL-able book_id/chapter_id, the two renamed
-- constraints present, no stray comments, and confdeltype = 'c'.
-- ---------------------------------------------------------------------------
\echo '--- nullability (all should be NO) ---'
SELECT table_name, column_name, is_nullable
  FROM information_schema.columns
 WHERE (table_name, column_name) IN (
        ('chapters','book_id'), ('verses','book_id'), ('verses','chapter_id'),
        ('feedback','created_at'), ('contact_submissions','created_at'),
        ('contact_submissions','status'), ('translations','license'),
        ('translations','is_default'), ('translations','created_at'))
 ORDER BY 1, 2;

\echo '--- constraint names (expect unique_chapter, unique_verse_translation) ---'
SELECT conname FROM pg_constraint
 WHERE conname IN ('unique_chapter', 'unique_verse_translation') ORDER BY 1;

\echo '--- verses_translation_fkey delete action (expect c) ---'
SELECT conname, confdeltype FROM pg_constraint WHERE conname = 'verses_translation_fkey';

\echo '--- stray comments (expect zero rows) ---'
SELECT c.relname, a.attname, col_description(c.oid, a.attnum) AS comment
  FROM pg_class c
  JOIN pg_attribute a ON a.attrelid = c.oid
 WHERE col_description(c.oid, a.attnum) IS NOT NULL
   AND c.relname IN ('books', 'verses');
