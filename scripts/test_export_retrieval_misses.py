#!/usr/bin/env python3
"""Tests for scripts/export_retrieval_misses.py (BITB-256).

No database: the query builders are compiled to SQL text and ``main`` runs against a
mocked SQLAlchemy ``Session``. Needs the api dependencies (sqlalchemy); skipped without.
"""

import argparse
import importlib.util
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("sqlalchemy")

_SCRIPT = Path(__file__).resolve().parent / "export_retrieval_misses.py"
_spec = importlib.util.spec_from_file_location("export_retrieval_misses", _SCRIPT)
exporter = importlib.util.module_from_spec(_spec)
sys.modules["export_retrieval_misses"] = exporter
_spec.loader.exec_module(exporter)


def _args(**overrides):
    base = dict(
        reason=None,
        language=None,
        translation=None,
        since=None,
        until=None,
        limit=None,
        aggregate=False,
        format="json",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _compile(stmt) -> str:
    from sqlalchemy.dialects import postgresql

    return str(stmt.compile(dialect=postgresql.dialect()))


class TestHelpers:
    def test_parse_date_is_utc_aware(self):
        assert exporter.parse_date("2026-11-01") == datetime(2026, 11, 1, tzinfo=timezone.utc)

    def test_parse_date_rejects_garbage(self):
        with pytest.raises(argparse.ArgumentTypeError):
            exporter.parse_date("yesterday")

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://u:p@h/db",
            "postgresql+asyncpg://u:p@h/db",
            "postgres://u:p@h/db",
            "postgresql+psycopg2://u:p@h/db",
        ],
    )
    def test_sync_database_url_always_selects_psycopg2(self, url):
        # psycopg2-binary is the installed sync driver; a bare postgresql:// would make
        # SQLAlchemy 2 look for psycopg (v3) and fail.
        assert exporter.sync_database_url(url) == "postgresql+psycopg2://u:p@h/db"

    def test_blocked_samples_exporter_has_the_same_mapping(self):
        path = Path(__file__).resolve().parent / "export_blocked_samples.py"
        spec = importlib.util.spec_from_file_location("export_blocked_samples", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for url in ("postgresql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"):
            assert mod.sync_database_url(url) == "postgresql+psycopg2://u:p@h/db"

    def test_fields_never_include_text_columns(self):
        banned = {"message", "message_text", "prompt", "expansion_text", "response"}
        assert not banned & set(exporter.FIELDS)


class TestBuildQuery:
    def test_no_filters_orders_newest_first(self):
        sql = _compile(exporter.build_query(_args()))
        assert "FROM retrieval_miss_samples" in sql
        assert "ORDER BY retrieval_miss_samples.created_at DESC" in sql
        assert "retrieval_miss_samples.expires_at > now()" in sql  # never export expired rows

    def test_all_filters_applied(self):
        sql = _compile(
            exporter.build_query(
                _args(
                    reason="empty",
                    language="it",
                    translation="kjv",
                    since=datetime(2026, 11, 1, tzinfo=timezone.utc),
                    until=datetime(2026, 12, 1, tzinfo=timezone.utc),
                    limit=5,
                )
            )
        )
        assert "retrieval_miss_samples.language =" in sql
        assert "retrieval_miss_samples.translation =" in sql
        assert "retrieval_miss_samples.reasons @>" in sql
        assert "created_at >=" in sql and "created_at <" in sql
        assert "LIMIT" in sql


class TestAggregateQuery:
    def test_groups_by_topic_language_reason_and_sums_hit_count(self):
        stmt, params = exporter.build_aggregate_query(_args(aggregate=True))
        sql = str(stmt)
        assert "unnest(r.reasons)" in sql
        assert "jsonb_array_elements_text(r.topics)" in sql
        assert "COALESCE(t.topic, '(none)')" in sql
        assert "LEFT JOIN LATERAL" in sql  # keeps rows with empty topics
        assert "SUM(hit_count)" in sql
        assert "GROUP BY topic, language, reason" in sql
        assert "r.expires_at > now()" in sql
        assert params == {}

    def test_filters_are_bound_parameters_not_interpolated(self):
        stmt, params = exporter.build_aggregate_query(
            _args(language="de", translation="web", reason="low_score", limit=3)
        )
        sql = str(stmt)
        assert ":language" in sql and ":translation" in sql and ":reason" in sql
        assert "'de'" not in sql and "'low_score'" not in sql
        assert params == {
            "language": "de",
            "translation": "web",
            "reason": "low_score",
            "limit": 3,
        }


class TestEmit:
    def test_json_serialises_datetimes_and_unicode(self):
        out = io.StringIO()
        exporter.emit_json(
            [
                {
                    "id": 1,
                    "created_at": datetime(2026, 11, 1, tzinfo=timezone.utc),
                    "topic": "平安",
                }
            ],
            out,
        )
        data = json.loads(out.getvalue())
        assert data[0]["created_at"].startswith("2026-11-01")
        assert data[0]["topic"] == "平安"

    def test_csv_uses_given_fields_and_json_encodes_lists(self):
        out = io.StringIO()
        exporter.emit_csv(
            [
                {
                    "topic": "(none)",
                    "language": "ko",
                    "reason": "empty",
                    "hits": 3,
                    "signatures": 1,
                }
            ],
            out,
            exporter.AGGREGATE_FIELDS,
        )
        lines = out.getvalue().strip().splitlines()
        assert lines[0] == "topic,language,reason,hits,signatures"
        assert lines[1] == "(none),ko,empty,3,1"

    def test_csv_default_fields_encode_list_cells(self):
        out = io.StringIO()
        row = {f: None for f in exporter.FIELDS}
        row["topics"] = ["anxiety"]
        exporter.emit_csv([row], out)
        assert '"[""anxiety""]"' in out.getvalue()


class TestMain:
    def test_requires_database_url(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(SystemExit) as exc:
            exporter.main([])
        assert exc.value.code == 2

    def test_aggregate_mode_runs_against_session(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
        row = SimpleNamespace(topic="anxiety", language="en", reason="empty", hits=7, signatures=2)
        session = MagicMock()
        session.execute.return_value = [row]
        session_cm = MagicMock()
        session_cm.__enter__.return_value = session
        out = tmp_path / "agg.json"
        with (
            patch.object(exporter, "create_engine") as mk_engine,
            patch.object(exporter, "Session", return_value=session_cm),
        ):
            rc = exporter.main(["--aggregate", "--language", "en", "--output", str(out)])
        assert rc == 0
        mk_engine.assert_called_once_with("postgresql+psycopg2://u:p@h/db", future=True)
        assert json.loads(out.read_text()) == [
            {
                "topic": "anxiety",
                "language": "en",
                "reason": "empty",
                "hits": 7,
                "signatures": 2,
            }
        ]
