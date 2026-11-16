"""hash stored session ids and drop contact user agents (BITB-329)

Revision ID: r0010
Revises: r0009
Create Date: 2026-11-16 00:00:00.000000

Data-only migration, no DDL. The app now stores ``sha256(session_id)`` instead of the raw
session id in ``feedback.session_id`` and ``contact_submissions.session_id`` and no longer
stores ``contact_submissions.user_agent`` (privacy policy, BITB-329). This revision brings
the rows written before that change in line:

* every ``session_id`` that is not already a 64-character hex string is replaced by
  ``encode(sha256(convert_to(session_id, 'UTF8')), 'hex')`` -- the same digest as
  ``feedback.blocked_samples._hash_session_id`` (SHA-256 of the UTF-8 bytes, lowercase hex);
* ``contact_submissions.user_agent`` is set to NULL.

Lock / rewrite assessment (docs/MIGRATION_GUIDELINES.md):

* No DDL, so no ``ACCESS EXCLUSIVE`` lock and no table rewrite. ``UPDATE`` takes
  ``ROW EXCLUSIVE`` on the table (does not block reads or ordinary inserts) plus row locks on
  the touched rows only. Both tables are small (user-submitted feedback and contact messages,
  thousands of rows at most); at that size each statement is expected to take well under a
  second. Production-scale duration has not been measured, so it is stated as "expected",
  not "measured".
* ``lock_timeout`` (5s) stops the statements from queueing behind a long transaction and
  ``statement_timeout`` (60s) bounds their run time; both are ``SET LOCAL`` so they cannot
  leak into another session.
* Idempotent: the hash only touches values that are not already 64 hex characters (a
  re-run, or rows written by the new app, are left alone) and the user-agent update only
  touches non-NULL values.
* Backward-compatible (Rule #7): the old app image only ever writes and never reads these
  columns, and the new app image writes hashes, so deploy order does not matter. Rows an old
  image writes between this migration and its replacement keep a raw id until the next
  run of this revision or the retention sweep deletes them (<= 90 days).
* ``downgrade()`` is a documented no-op: hashing is irreversible and the user agents are
  gone by design.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0010"
down_revision: str | None = "r0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HASHABLE = "session_id IS NOT NULL AND session_id <> '' AND session_id !~ '^[0-9a-f]{64}$'"


def _set_timeouts() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '60s'")


def upgrade() -> None:
    _set_timeouts()
    for table in ("feedback", "contact_submissions"):
        op.execute(
            f"UPDATE {table} "  # noqa: S608 -- fixed table names, no user input
            "SET session_id = encode(sha256(convert_to(session_id, 'UTF8')), 'hex') "
            f"WHERE {_HASHABLE}"
        )
    op.execute("UPDATE contact_submissions SET user_agent = NULL WHERE user_agent IS NOT NULL")


def downgrade() -> None:
    """No-op: hashing is irreversible and user agents are deliberately not kept."""
    _set_timeouts()
