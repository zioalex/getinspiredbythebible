#!/usr/bin/env python3
"""Preflight for `alembic upgrade head` in the deploy workflow (BITB-126).

The deploy job used to diagnose the database's Alembic state by parsing
`alembic current`, which only works when Alembic can *resolve* the stamp it
reads. When the database is stamped at a revision this checkout does not
contain, `alembic current` itself dies before printing anything:

    ERROR [alembic.util.messaging] Can't locate revision identified by 'r0006'
    ##[error]Process completed with exit code 255.

That is the shape a **re-run of an older workflow run** takes: run 33369807581
replayed commit 12129b6a (which ships r0001..r0005) on 2026-09-08, days after
r0006 had already been applied to production. The database was fine, the deploy
was simply older than the live schema -- but the job failed with a bare exit
255, and the existing "database has no alembic_version row" preflight never got
to run, because it sat *downstream* of the command that had already exited.

So this preflight reads `alembic_version` with a plain SELECT -- no revision
resolution, nothing that can fail on an unknown id -- and compares the stamp to
this checkout's revision graph before any `alembic` command runs. Every
outcome it can reach names the actual cause and the actual remedy.

Usage (from the deploy workflow, DATABASE_URL exported):

    python scripts/alembic_preflight.py

Exit code 0 means `alembic upgrade head` is safe to run; 1 means it would fail,
and stdout says why.
"""

from __future__ import annotations

import asyncio
import os
import sys
from enum import Enum
from pathlib import Path
from typing import NamedTuple

from alembic.config import Config
from alembic.script import ScriptDirectory

_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_DIR = _REPO_ROOT / "api"
_ALEMBIC_INI = _API_DIR / "alembic.ini"
_ALEMBIC_DIR = _API_DIR / "alembic"
_MIGRATIONS_DIR = _REPO_ROOT / "scripts" / "migrations"

# The revision production was stamped at when Alembic took over the
# pre-existing schema (BITB-089 Stage 2). Named in the unstamped remedy.
_BASELINE_REVISION = "r0001"


class Verdict(Enum):
    """What the database's stamp means for `alembic upgrade head`."""

    OK = "ok"
    UNSTAMPED = "unstamped"
    STALE_CHECKOUT = "stale_checkout"
    DIVERGED = "diverged"
    MULTIPLE_HEADS = "multiple_heads"


def classify(
    db_revisions: set[str],
    known_revisions: set[str],
    head_ancestry: set[str],
    heads: set[str],
) -> Verdict:
    """Decide whether `alembic upgrade head` can run, from graph facts alone.

    Pure and DB-free so every branch is unit-testable:

    - ``db_revisions``   -- what `alembic_version` actually holds (may be empty)
    - ``known_revisions``-- every revision id present in this checkout
    - ``head_ancestry``  -- head plus everything head descends from
    - ``heads``          -- the checkout's head revision(s)
    """
    if len(heads) > 1:
        return Verdict.MULTIPLE_HEADS
    if not db_revisions:
        return Verdict.UNSTAMPED
    if db_revisions - known_revisions:
        return Verdict.STALE_CHECKOUT
    if db_revisions - head_ancestry:
        return Verdict.DIVERGED
    return Verdict.OK


def format_failure(
    verdict: Verdict,
    db_revisions: set[str],
    known_revisions: set[str],
    heads: set[str],
) -> list[str]:
    """The operator-facing explanation for a non-OK verdict.

    Returned as lines rather than printed so the wording is assertable in
    tests -- these messages are the whole point of the preflight, and a
    preflight that fails with an unhelpful message is the bug it exists to fix.
    """
    stamped = ", ".join(sorted(db_revisions)) or "<none>"
    local_head = ", ".join(sorted(heads)) or "<none>"

    if verdict is Verdict.UNSTAMPED:
        return [
            "Database has no alembic_version row. Stamp it once before",
            f"enabling this step: DATABASE_URL=<prod> alembic stamp {_BASELINE_REVISION}",
            "(BITB-089 Stage 2 -- take a backup first; the stamp writes no DDL).",
            "For a genuinely empty database, run 'alembic upgrade head' manually once.",
        ]

    if verdict is Verdict.STALE_CHECKOUT:
        return [
            f"Database is stamped at '{stamped}', which does not exist in this",
            f"checkout (api/alembic/versions/ holds {len(known_revisions)} revisions, "
            f"head={local_head}).",
            "This deploy is running a commit OLDER than the schema that is already",
            "live -- almost always a re-run of a stale workflow run. The database is",
            "not broken and needs no repair.",
            "Remedy: deploy the current main instead of re-running this run. Re-running",
            "it again cannot succeed. To genuinely roll the schema back, run",
            f"'alembic downgrade {local_head}' deliberately first, with a backup.",
        ]

    if verdict is Verdict.DIVERGED:
        return [
            f"Database is stamped at '{stamped}', which exists in this checkout but is",
            f"not an ancestor of head ({local_head}). 'alembic upgrade head' would not",
            "replay it, so the live schema and the migration chain have diverged.",
            "Remedy: reconcile the revision chain before deploying; do not force an",
            "upgrade over a diverged stamp.",
        ]

    if verdict is Verdict.MULTIPLE_HEADS:
        return [
            f"This checkout has multiple Alembic heads ({local_head}).",
            "'alembic upgrade head' is ambiguous and would fail. Remedy: merge the",
            "branches with 'alembic merge' so there is exactly one head.",
        ]

    raise ValueError(f"no failure message for verdict {verdict!r}")


class RevisionGraph(NamedTuple):
    """This checkout's `api/alembic/versions/` graph, as plain sets."""

    known: set[str]
    """Every revision id present in the checkout."""
    head_ancestry: set[str]
    """Head plus everything head descends from. Empty if head is ambiguous."""
    heads: set[str]
    """The checkout's head revision(s). More than one makes `upgrade head` fail."""
    ancestry: dict[str, set[str]]
    """Per revision: itself plus everything it descends from."""


def load_revision_graph() -> RevisionGraph:
    """Read this checkout's revision graph.

    `script_location` in alembic.ini is relative to api/, so it is overridden
    with an absolute path -- the preflight must not depend on its cwd.
    """
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_ALEMBIC_DIR))
    script = ScriptDirectory.from_config(config)

    known = {revision.revision for revision in script.walk_revisions()}
    ancestry = {
        revision: {ancestor.revision for ancestor in script.iterate_revisions(revision, "base")}
        for revision in known
    }
    heads = set(script.get_heads())
    head_ancestry = ancestry[next(iter(heads))] if len(heads) == 1 else set()
    return RevisionGraph(known, head_ancestry, heads, ancestry)


def count_pending(db_revisions: set[str], graph: RevisionGraph) -> int:
    """How many revisions `alembic upgrade head` would actually apply.

    A stamp implies its whole ancestry is already applied -- the row records the
    latest revision, not the full list -- so the applied set is the *ancestry*
    of what is stamped, never the stamped ids alone. Counting the raw ids
    instead reports a database already at head as having every prior revision
    still to apply, which is precisely the kind of misleading deploy log this
    preflight exists to stop producing.
    """
    applied: set[str] = set()
    for revision in db_revisions:
        applied |= graph.ancestry.get(revision, {revision})
    return len(graph.head_ancestry - applied)


async def _fetch_stamped_revisions(database_url: str) -> set[str]:
    """Every row of `alembic_version`, or an empty set if unstamped.

    A plain SELECT, deliberately: this must report what the database holds even
    when the id means nothing to this checkout, which is exactly the case
    `alembic current` cannot survive.

    Imported locally so that importing this module for its pure functions costs
    nothing and, more importantly, does not put `scripts/migrations` on
    `sys.path` (its `utils` is a name generic enough to shadow another).
    """
    import asyncpg  # noqa: PLC0415

    sys.path.insert(0, str(_MIGRATIONS_DIR))
    from utils import get_migration_connection_params  # noqa: PLC0415

    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)
    try:
        # to_regclass returns NULL rather than raising for a missing table, so
        # an Alembic-less database is a normal answer here, not an exception.
        if not await conn.fetchval("SELECT to_regclass('public.alembic_version')"):
            return set()
        rows = await conn.fetch("SELECT version_num FROM alembic_version")
    finally:
        await conn.close()
    return {row["version_num"] for row in rows}


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("::error::DATABASE_URL is not set; cannot run the Alembic preflight.")
        return 1

    graph = load_revision_graph()
    db_revisions = asyncio.run(_fetch_stamped_revisions(database_url))

    print("=== alembic preflight ===")
    print(f"database stamped at: {', '.join(sorted(db_revisions)) or '<no alembic_version row>'}")
    print(f"checkout head:       {', '.join(sorted(graph.heads)) or '<none>'}")
    print(f"checkout revisions:  {len(graph.known)}")

    verdict = classify(db_revisions, graph.known, graph.head_ancestry, graph.heads)
    if verdict is Verdict.OK:
        print(f"OK -- {count_pending(db_revisions, graph)} revision(s) to apply.")
        return 0

    for line in format_failure(verdict, db_revisions, graph.known, graph.heads):
        print(f"::error::{line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
