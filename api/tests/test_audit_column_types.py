"""Tests for scripts/audit_column_types.py (BITB-094).

Pure functions over synthetic Alembic diff tuples -- zero DB dependency and
no live Alembic autogenerate run. `_collect_raw_diffs()`/`run_audit()`, which
actually talk to a database, are exercised by running the script for real
against a throwaway database (see docs/audits/BITB-094-column-type-audit.md
for that captured output) rather than here.

The module under test imports `alembic` only inside `_collect_raw_diffs()`
(a lazy import), so loading it here needs neither a database nor a running
Alembic environment -- matching the style of
api/tests/test_verse_topic_coverage_check.py for scripts/check_verse_topic_coverage.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "audit_column_types.py"


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location("audit_column_types", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# A representative modify_type diff tuple, shaped exactly like what
# AlterColumnOp.to_diff_tuple() produces: ("modify_type", schema, table,
# column, {existing_*}, old_type, new_type).
def _modify_type(table: str, column: str, old="OLD_TYPE", new="NEW_TYPE", schema=None):
    return (
        "modify_type",
        schema,
        table,
        column,
        {"existing_nullable": True, "existing_server_default": False, "existing_comment": None},
        old,
        new,
    )


class TestIsExpectedEmbeddingDiff:
    @pytest.mark.parametrize(
        "table,column",
        [("verses", "embedding"), ("passages", "embedding"), ("topics", "embedding")],
    )
    def test_embedding_columns_are_expected(self, audit_module, table, column):
        diff = _modify_type(table, column, old="VECTOR(dim=1024)", new="VECTOR(dim=1536)")
        assert audit_module.is_expected_embedding_diff(diff) is True

    def test_translations_created_at_is_not_expected(self, audit_module):
        """The known BITB-094 candidate: a real (non-embedding) type diff
        must never be swallowed into the expected-difference bucket."""
        diff = _modify_type(
            "translations", "created_at", old="TIMESTAMP", new="TIMESTAMP(timezone=True)"
        )
        assert audit_module.is_expected_embedding_diff(diff) is False

    def test_embedding_named_column_on_wrong_table_is_not_expected(self, audit_module):
        """Matching is (table, column), not the column name alone -- a
        hypothetical `embedding` column on an unrelated table is real drift."""
        diff = _modify_type("some_other_table", "embedding")
        assert audit_module.is_expected_embedding_diff(diff) is False

    def test_non_type_op_on_an_embedding_column_is_not_expected(self, audit_module):
        """Only a type change on these columns is expected -- e.g. a
        nullability change on verses.embedding would be real and should be
        flagged, not bucketed away."""
        diff = (
            "modify_nullable",
            None,
            "verses",
            "embedding",
            {"existing_type": "VECTOR(dim=1024)"},
            True,
            False,
        )
        assert audit_module.is_expected_embedding_diff(diff) is False

    def test_add_column_op_is_not_expected(self, audit_module):
        diff = ("add_column", None, "verses", object())
        assert audit_module.is_expected_embedding_diff(diff) is False

    def test_empty_diff_is_not_expected(self, audit_module):
        assert audit_module.is_expected_embedding_diff(()) is False


class TestBucketDiffs:
    def test_splits_embedding_from_everything_else(self, audit_module):
        embedding_diff = _modify_type(
            "verses", "embedding", old="VECTOR(dim=1024)", new="VECTOR(dim=1536)"
        )
        drift_diff = _modify_type(
            "translations", "created_at", old="TIMESTAMP", new="TIMESTAMP(timezone=True)"
        )

        expected, flagged = audit_module.bucket_diffs([embedding_diff, drift_diff])

        assert expected == [embedding_diff]
        assert flagged == [drift_diff]

    def test_all_three_embedding_columns_bucket_together(self, audit_module):
        diffs = [
            _modify_type("verses", "embedding"),
            _modify_type("passages", "embedding"),
            _modify_type("topics", "embedding"),
        ]
        expected, flagged = audit_module.bucket_diffs(diffs)
        assert expected == diffs
        assert flagged == []

    def test_empty_input_yields_empty_buckets(self, audit_module):
        expected, flagged = audit_module.bucket_diffs([])
        assert expected == []
        assert flagged == []

    def test_structural_diff_is_flagged_not_dropped(self, audit_module):
        """The bucketing must never silently drop a difference -- everything
        that isn't the named expected-difference case has to surface."""
        add_table_diff = ("add_table", type("FakeTable", (), {"name": "new_table"})())
        expected, flagged = audit_module.bucket_diffs([add_table_diff])
        assert expected == []
        assert flagged == [add_table_diff]


class TestFlattenDiffs:
    def test_flattens_alter_column_op_lists(self, audit_module):
        """AlterColumnOp.to_diff_tuple() returns a *list* of tuples when a
        column has multiple simultaneous changes; other ops return a bare
        tuple. Both shapes must end up as plain tuples in the flat result."""
        multi_change = [
            _modify_type("translations", "created_at"),
            ("modify_nullable", None, "translations", "created_at", {}, True, False),
        ]
        single_change = ("add_column", None, "verses", object())

        flat = audit_module.flatten_diffs([multi_change, single_change])

        assert flat == [multi_change[0], multi_change[1], single_change]

    def test_empty_input(self, audit_module):
        assert audit_module.flatten_diffs([]) == []


class TestFormatDiff:
    def test_modify_type_names_table_column_and_both_types(self, audit_module):
        diff = _modify_type(
            "translations", "created_at", old="TIMESTAMP", new="TIMESTAMP(timezone=True)"
        )
        rendered = audit_module.format_diff(diff)
        assert "translations.created_at" in rendered
        assert "TIMESTAMP" in rendered

    def test_unrecognized_op_does_not_raise(self, audit_module):
        """Any diff-tuple shape alembic might ever emit must render as
        *something* rather than crash the report."""
        rendered = audit_module.format_diff(("add_fk", None, "some_constraint"))
        assert "add_fk" in rendered

    def test_empty_diff_does_not_raise(self, audit_module):
        audit_module.format_diff(())  # must not raise


class TestRedactUrl:
    def test_password_is_hidden(self, audit_module):
        redacted = audit_module.redact_url("postgresql://user:secretpass@host:5432/db")
        assert "secretpass" not in redacted
        assert "user" in redacted
        assert "host" in redacted

    def test_url_without_password_is_unchanged(self, audit_module):
        url = "postgresql://user@host:5432/db"
        assert audit_module.redact_url(url) == url
