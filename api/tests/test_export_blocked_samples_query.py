"""BITB-326: the blocked-sample exporter never returns rows past their retention.

Expired rows still exist between their expiry and the next purge (hourly API sweep,
daily pg_cron job). The privacy policy promises blocked-message records are kept
"up to 30 days", so an export must not surface them in that window.
"""

import argparse
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.dialects import postgresql

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_blocked_samples.py"
_spec = importlib.util.spec_from_file_location("export_blocked_samples_query", _SCRIPT)
exporter = importlib.util.module_from_spec(_spec)
sys.modules["export_blocked_samples_query"] = exporter
_spec.loader.exec_module(exporter)


def _args(**overrides):
    base = dict(stage=None, language=None, since=None, until=None, reviewed=None, limit=None)
    base.update(overrides)
    return argparse.Namespace(**base)


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_query_excludes_expired_rows_without_filters():
    sql = _sql(exporter.build_query(_args()))
    assert "blocked_message_samples.expires_at > now()" in sql
    assert "ORDER BY blocked_message_samples.created_at DESC" in sql


def test_query_excludes_expired_rows_with_all_filters():
    sql = _sql(
        exporter.build_query(
            _args(
                stage="llama_guard",
                language="it",
                since=datetime(2026, 11, 1, tzinfo=timezone.utc),
                until=datetime(2026, 12, 1, tzinfo=timezone.utc),
                reviewed=False,
                limit=5,
            )
        )
    )
    assert "blocked_message_samples.expires_at > now()" in sql
    assert "blocked_message_samples.stage =" in sql
    assert "LIMIT" in sql
