#!/usr/bin/env python3
"""Audit ORM column TYPES against a live database (BITB-094).

WHY THIS EXISTS
----------------
``api/alembic/env.py`` sets ``compare_type=False``, deliberately, because
``Vector(settings.embedding_dimensions)`` is environment-dependent: 1024 for
the ollama-backed local/CI default, 1536 for ``azure_openai`` in production.
With type comparison on, ``alembic check`` would report every environment as
"drift" purely because two environments run different embedding providers.

The cost (see ``api/alembic/README.md`` invariant #2 and
``docs/BACKLOG_STORIES/BITB-094-audit-column-types-against-production.md``)
is that ``compare_type=False`` suppresses **all** column-type comparison, not
just the three Vector columns. No `alembic check` run has ever verified that
a `varchar(50)` in the database is still a `varchar(50)` in the models, that
an `integer` hasn't quietly become a `bigint`, or that a `timestamp` hasn't
drifted from a `timestamptz`. This script closes exactly that gap, without
touching ``compare_type`` in ``env.py`` itself (out of scope for BITB-094 --
the vector dimensions make a global flip unusable as a CI gate).

HOW IT WORKS
------------
This is not a hand-rolled reflect-and-diff. It runs the same machinery
``alembic check`` runs internally -- ``RevisionContext.run_autogenerate()``
inside an ``EnvironmentContext`` that loads and executes
``api/alembic/env.py`` by file path via ``ScriptDirectory.run_env()`` (see
``alembic/command.py::check`` in the installed ``alembic`` package for the
reference implementation this mirrors). Because ``env.py`` is executed for
real, ``target_metadata`` / ``include_name`` / ``include_object`` /
``compare_server_default`` used for the comparison are env.py's actual
objects, not a copy pasted into this script -- the audit's notion of "which
tables/columns Alembic owns" cannot drift from the real migration
environment. The one deliberate difference from a normal ``alembic check``
run: ``EnvironmentContext.configure`` is monkeypatched here, only for the
duration of this script, to force ``compare_type=True`` regardless of what
``env.py`` passes. ``env.py`` on disk is never modified.

The comparison is read-only. ``run_autogenerate`` only reflects the target
database; the callback handed to ``EnvironmentContext`` always returns ``[]``,
so no revision file and no DDL is ever produced or executed.

WHAT A RESULT ACTUALLY PROVES
------------------------------
Any type-modification diff touching ``verses.embedding``,
``passages.embedding`` or ``topics.embedding`` is bucketed and printed as
"expected difference (environment-dependent embedding dimension)" -- not
silently dropped, not treated as an error. Everything else prints as a
flagged difference that needs human triage.

Run against a database that was itself created by ``alembic upgrade head``
(a fresh local/CI database, or the throwaway one this story used to validate
this tool), the result mostly just proves that the migration history is
internally consistent with the ORM models -- which is close to trivial, since
both sides trace back to the same models. THIS IS NOT A SUBSTITUTE FOR
RUNNING IT AGAINST REAL PRODUCTION DATA. It only becomes the authoritative
check the BITB-094 acceptance criteria ask for when pointed at a schema-only
restore of production.

HOW TO RUN IT FOR REAL (authoritative run)
--------------------------------------------
Restore a **schema-only** copy of production -- see
``docs/HOW-TO-BACKUP-RESTORE-DATABASE.md``, Scenario C, the
``make db-backup-schema`` / ``make db-restore-local`` pair. Types are schema,
not data, so a schema-only restore is sufficient and needs no large dump.

    DATABASE_URL="<prod>" make db-backup-schema
    make db-restore-local DUMP=backups/<the-file>.dump
    DATABASE_URL="postgresql://postgres@localhost:5433/bibledb" PGPASSWORD=local \\
        python scripts/audit_column_types.py

NEVER point ``DATABASE_URL`` at production directly for this script, even
though the comparison itself is read-only -- matching the standing warning in
``api/alembic/README.md``: "Never point any of the above at the production
database from a local machine or a PR."

Usage:
    cd api  # or let this script chdir there itself, matching every other
            # Alembic command's documented convention (api/alembic/README.md)
    export DATABASE_URL="postgresql://user:pass@host/db"
    python ../scripts/audit_column_types.py

Exit codes:
    0: the comparison ran successfully -- whether or not differences were
       found. This is an audit/report tool, not a CI gate (see BITB-094's
       recorded decision in docs/audits/BITB-094-column-type-audit.md); it
       is deliberately not wired into any CI workflow.
    1: connection or usage error (DATABASE_URL unset, cannot connect, cannot
       load api/alembic/env.py, etc.)
    2: bad command-line arguments (argparse's own exit code)
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api"

# The three Vector columns whose dimension is legitimately environment-dependent
# (1024 for the ollama-backed local/CI default, 1536 for azure_openai in
# production -- see api/config.py and api/alembic/env.py's compare_type=False
# comment). Anything else that shows up as a type diff is real and needs a
# human to look at it.
EXPECTED_EMBEDDING_COLUMNS = frozenset(
    {
        ("verses", "embedding"),
        ("passages", "embedding"),
        ("topics", "embedding"),
    }
)


def flatten_diffs(raw_diffs: Iterable[Any]) -> list[tuple]:
    """Flatten Alembic's raw autogenerate diff list into flat diff tuples.

    Most leaf ops (``add_column``, ``add_table``, ...) yield a single tuple
    from ``to_diff_tuple()``. ``AlterColumnOp`` is the exception: one column
    can carry several simultaneous changes (type, nullable, default,
    comment), so its ``to_diff_tuple()`` returns a *list* of tuples, one per
    changed facet -- see ``alembic/operations/ops.py::AlterColumnOp.to_diff_tuple``
    in the installed alembic package. This flattens both shapes into a single
    list of plain diff tuples.
    """
    flat: list[tuple] = []
    for item in raw_diffs:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    return flat


def is_expected_embedding_diff(diff: tuple) -> bool:
    """True for a ``modify_type`` diff touching one of the environment-dependent
    Vector columns -- exactly what ``compare_type=False`` was introduced to
    suppress, and exactly what BITB-094 exists to name explicitly instead of
    hiding.

    Diff shape: ``("modify_type", schema, table, column, {...existing...}, old_type, new_type)``
    -- see ``AlterColumnOp.to_diff_tuple`` in the installed alembic package.
    """
    if not diff or diff[0] != "modify_type" or len(diff) < 4:
        return False
    table, column = diff[2], diff[3]
    return (table, column) in EXPECTED_EMBEDDING_COLUMNS


def bucket_diffs(diffs: Iterable[tuple]) -> tuple[list[tuple], list[tuple]]:
    """Split flattened diff tuples into ``(expected_embedding, flagged)``."""
    expected: list[tuple] = []
    flagged: list[tuple] = []
    for diff in diffs:
        (expected if is_expected_embedding_diff(diff) else flagged).append(diff)
    return expected, flagged


def format_diff(diff: tuple) -> str:
    """One-line human-readable rendering of a flattened Alembic diff tuple."""
    op = diff[0] if diff else "?"
    if (
        op in ("modify_type", "modify_nullable", "modify_default", "modify_comment")
        and len(diff) >= 7
    ):
        _, schema, table, column, _kw, old, new = diff[:7]
        qualified = f"{schema}.{table}" if schema else table
        return f"{op:<16} {qualified}.{column}: {old!r} -> {new!r}"
    if op in ("add_column", "remove_column") and len(diff) >= 4:
        _, schema, table, column = diff[:4]
        colname = getattr(column, "name", column)
        qualified = f"{schema}.{table}" if schema else table
        return f"{op:<16} {qualified}.{colname}"
    if op in ("add_table", "remove_table") and len(diff) >= 2:
        table_obj = diff[1]
        tname = getattr(table_obj, "name", table_obj)
        return f"{op:<16} {tname}"
    # Generic fallback -- keeps the tool useful for a diff shape not
    # special-cased above (e.g. add_index/add_fk/add_constraint) rather than
    # raising or silently dropping it.
    return f"{op:<16} {diff[1:]!r}"


def redact_url(url: str) -> str:
    """Hide a password in a DSN before printing it.

    Matches the redaction convention documented in
    docs/HOW-TO-BACKUP-RESTORE-DATABASE.md / scripts/db-backup-restore.sh.
    """
    parts = urlsplit(url)
    if parts.password:
        netloc = parts.netloc.replace(f":{parts.password}@", ":***@")
        parts = parts._replace(netloc=netloc)
    return urlunsplit(parts)


def _collect_raw_diffs() -> list[Any]:
    """Run Alembic's own autogenerate comparison against ``DATABASE_URL``.

    Reuses ``api/alembic/env.py``'s actual ``target_metadata`` /
    ``include_name`` / ``include_object`` / ``compare_server_default`` by
    executing env.py for real (see the module docstring for why). The only
    override is ``compare_type``, forced to ``True`` for the duration of this
    call via a monkeypatch of ``EnvironmentContext.configure`` -- restored in
    a ``finally`` block regardless of outcome.

    Must be called with the current working directory set to ``api/`` (see
    ``run_audit`` below) -- ``alembic.ini``'s ``script_location = alembic``
    and ``prepend_sys_path = .`` are both resolved relative to cwd by
    Alembic itself, exactly as they are for every other Alembic command.
    """
    from alembic import autogenerate as autogen
    from alembic.config import Config
    from alembic.runtime.environment import EnvironmentContext
    from alembic.script import ScriptDirectory

    real_configure = EnvironmentContext.configure

    def _configure_forcing_compare_type_true(self, *args, **kwargs):
        kwargs["compare_type"] = True
        return real_configure(self, *args, **kwargs)

    EnvironmentContext.configure = _configure_forcing_compare_type_true  # type: ignore[method-assign]
    try:
        cfg = Config(str(API_DIR / "alembic.ini"))
        script_directory = ScriptDirectory.from_config(cfg)

        # Same command_args `alembic check` builds internally (alembic/command.py)
        # -- required by RevisionContext even though we never write the
        # revision file it could produce.
        command_args = {
            "message": None,
            "autogenerate": True,
            "sql": False,
            "head": "head",
            "splice": False,
            "branch_label": None,
            "version_path": None,
            "rev_id": None,
            "depends_on": None,
        }
        revision_context = autogen.RevisionContext(cfg, script_directory, command_args)

        def retrieve_migrations(rev, context):
            revision_context.run_autogenerate(rev, context)
            return []  # never emit an actual revision/DDL -- read-only

        with EnvironmentContext(
            cfg,
            script_directory,
            fn=retrieve_migrations,
            as_sql=False,
            template_args=revision_context.template_args,
            revision_context=revision_context,
        ):
            script_directory.run_env()  # loads and executes api/alembic/env.py
    finally:
        EnvironmentContext.configure = real_configure  # type: ignore[method-assign]

    migration_script = revision_context.generated_revisions[-1]
    raw_diffs: list[Any] = []
    for upgrade_ops in migration_script.upgrade_ops_list:
        raw_diffs.extend(upgrade_ops.as_diffs())
    return raw_diffs


def run_audit() -> int:
    """Run the audit against ``DATABASE_URL`` and print a report.

    Returns a process exit code -- 0 on a successful comparison regardless of
    what it found, 1 on a connection/usage error. See the module docstring.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        print("Run with --help for how to point this at a schema-only restore.", file=sys.stderr)
        return 1

    if not API_DIR.is_dir():
        print(f"ERROR: expected an api/ directory at {API_DIR}, found none.", file=sys.stderr)
        return 1

    # Every Alembic command in this repo runs from api/ (api/alembic/README.md).
    # This script honors that convention itself rather than asking the caller
    # to `cd api` first -- alembic.ini's script_location/prepend_sys_path are
    # resolved relative to cwd.
    os.chdir(API_DIR)

    try:
        raw_diffs = _collect_raw_diffs()
    except Exception as exc:  # noqa: BLE001 -- surfaced to the operator verbatim
        print(f"ERROR: could not compare against DATABASE_URL: {exc}", file=sys.stderr)
        return 1

    diffs = flatten_diffs(raw_diffs)
    expected, flagged = bucket_diffs(diffs)

    print(f"BITB-094 column-type audit against {redact_url(database_url)}")
    print(
        f"{len(diffs)} total structural+type difference(s) found "
        "(compare_type forced on for this run; env.py's own table/index "
        "allowlist still applies)."
    )
    print()

    if expected:
        print(
            f"Expected difference (environment-dependent embedding dimension) -- {len(expected)}:"
        )
        for diff in expected:
            print(f"  {format_diff(diff)}")
        print()
    else:
        print(
            "No embedding-dimension difference found. Expected when run against a "
            "database created by `alembic upgrade head` itself (see the module "
            "docstring) -- both sides trace back to the same EMBEDDING_DIMENSIONS. "
            "A real production restore running a different embedding provider "
            "would show one here."
        )
        print()

    if flagged:
        print(f"FLAGGED -- needs human triage -- {len(flagged)}:")
        for diff in flagged:
            print(f"  {format_diff(diff)}")
    else:
        print("No flagged differences outside the expected embedding-dimension bucket.")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit_column_types.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args(argv)
    return run_audit()


if __name__ == "__main__":
    sys.exit(main())
