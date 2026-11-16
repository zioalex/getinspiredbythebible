"""BITB-329: scripts/export_feedback.py -- query filters, retention limits, CLI flags.

The exporter is the only way to read feedback/contact text (notification e-mails carry
identifiers only). It must never return a row past its row window, and never return text
past the text window even if the sweep has not NULLed it yet.

CI only collects api/tests, hence the importlib load of the script (same pattern as
test_export_blocked_samples_query.py). A real-database test runs when a local Postgres is
reachable and skips otherwise.
"""

import argparse
import importlib.util
import io
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from sqlalchemy.dialects import postgresql

from config import settings

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_feedback.py"
_spec = importlib.util.spec_from_file_location("export_feedback_script", _SCRIPT)
exporter = importlib.util.module_from_spec(_spec)
sys.modules["export_feedback_script"] = exporter
_spec.loader.exec_module(exporter)

MID = uuid.UUID("3f2b1c9e-8a4d-4e0b-9c1a-5d6e7f8a9b0c")


def _args(**overrides):
    base = dict(
        contacts=False,
        id=None,
        message_id=None,
        rating=None,
        subject=None,
        since=None,
        until=None,
        limit=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _fb(**overrides):
    return exporter.build_feedback_query(_args(**overrides), text_days=30, row_days=90)


def _ct(**overrides):
    return exporter.build_contact_query(_args(contacts=True, **overrides), contact_days=90)


class TestFeedbackQuery:
    def test_never_returns_rows_past_the_row_window(self):
        sql = _sql(_fb())
        assert "feedback.created_at > now() - make_interval(" in sql
        assert "ORDER BY feedback.created_at DESC" in sql

    def test_text_columns_are_masked_past_the_text_window(self):
        sql = _sql(_fb())
        for col in ("comment", "user_message", "assistant_response"):
            assert f"feedback.{col} END AS {col}" in sql
        assert sql.count("CASE WHEN (feedback.created_at <= now() - make_interval(") == 3

    def test_windows_use_the_configured_days(self):
        stmt = exporter.build_feedback_query(_args(), text_days=7, row_days=14)
        params = stmt.compile(dialect=postgresql.dialect()).params
        assert 7 in params.values() and 14 in params.values()

    def test_selectors_and_filters(self):
        sql = _sql(
            _fb(
                message_id=MID,
                id=5,
                rating="negative",
                since=datetime(2026, 11, 1, tzinfo=UTC),
                until=datetime(2026, 12, 1, tzinfo=UTC),
                limit=5,
            )
        )
        assert "feedback.message_id =" in sql
        assert "feedback.id =" in sql
        assert "feedback.rating =" in sql
        assert "feedback.created_at >=" in sql and "feedback.created_at <" in sql
        assert "LIMIT" in sql

    def test_message_id_param_is_the_uuid(self):
        params = _fb(message_id=MID).compile(dialect=postgresql.dialect()).params
        assert MID in params.values()


class TestContactQuery:
    def test_never_returns_rows_past_the_contact_window(self):
        sql = _sql(_ct())
        assert "contact_submissions.created_at > now() - make_interval(" in sql

    def test_filters(self):
        sql = _sql(
            _ct(
                id=12,
                subject="bug",
                since=datetime(2026, 11, 1, tzinfo=UTC),
                until=datetime(2026, 12, 1, tzinfo=UTC),
                limit=3,
            )
        )
        assert "contact_submissions.id =" in sql
        assert "contact_submissions.subject =" in sql
        assert "contact_submissions.created_at >=" in sql
        assert "LIMIT" in sql

    def test_window_uses_the_configured_days(self):
        stmt = exporter.build_contact_query(_args(contacts=True), contact_days=11)
        assert 11 in stmt.compile(dialect=postgresql.dialect()).params.values()


class TestCli:
    def _parse(self, argv):
        return exporter.build_parser().parse_args(argv)

    def test_parses_documented_flags(self):
        ns = self._parse(["--message-id", str(MID), "--rating", "negative", "--limit", "4"])
        assert (
            ns.message_id == MID and ns.rating == "negative" and ns.limit == 4 and not ns.contacts
        )
        ns = self._parse(["--contacts", "--id", "12", "--subject", "bug", "--since", "2026-11-01"])
        assert ns.contacts and ns.id == 12 and ns.subject == "bug"
        assert ns.since == datetime(2026, 11, 1, tzinfo=UTC)

    @pytest.mark.parametrize(
        "argv",
        [
            ["--message-id", "not-a-uuid"],
            ["--rating", "meh"],
            ["--subject", "nonsense"],
            ["--format", "xml"],
            ["--since", "yesterday"],
        ],
    )
    def test_rejects_bad_values(self, argv):
        with pytest.raises(SystemExit):
            self._parse(argv)

    @pytest.mark.parametrize(
        "argv",
        [
            ["--contacts", "--message-id", str(MID)],
            ["--contacts", "--rating", "negative"],
            ["--subject", "bug"],
        ],
    )
    def test_rejects_selectors_for_the_wrong_table(self, argv):
        parser = exporter.build_parser()
        with pytest.raises(SystemExit):
            exporter.validate_args(parser, parser.parse_args(argv))

    def test_requires_database_url(self, monkeypatch, capsys):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(SystemExit):
            exporter.main(["--id", "1"])
        assert "DATABASE_URL" in capsys.readouterr().err

    def test_emit_json_and_csv(self):
        rows = [
            {
                "id": 1,
                "created_at": datetime(2026, 11, 16, tzinfo=UTC),
                "message_id": MID,
                "verses_cited": ["John 3:16"],
            }
        ]
        out = io.StringIO()
        exporter.emit_json(rows, out)
        data = json.loads(out.getvalue())
        assert data[0]["message_id"] == str(MID)
        assert data[0]["created_at"].startswith("2026-11-16")
        out = io.StringIO()
        exporter.emit_csv(rows, ["id", "created_at", "message_id", "verses_cited"], out)
        assert str(MID) in out.getvalue() and '"[""John 3:16""]"' in out.getvalue()

    def test_sync_database_url_rewrites_driver_and_ssl(self):
        assert exporter.sync_database_url("postgresql+asyncpg://u@h/db?ssl=require").startswith(
            "postgresql+psycopg2://"
        )
        assert "sslmode=require" in exporter.sync_database_url("postgresql://u@h/db?ssl=require")


# --------------------------------------------------------------------- real database

_SAFE_HOSTS = {"localhost", "127.0.0.1", "postgres", "db"}


@pytest.fixture
def exporter_db(monkeypatch):
    import psycopg2
    from sqlalchemy import create_engine

    from feedback.models import Base

    parsed = urlparse(settings.database_url)
    if parsed.hostname not in _SAFE_HOSTS:
        pytest.skip(f"Refusing to create a database on host {parsed.hostname!r}")
    admin = dict(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
    )
    try:
        conn = psycopg2.connect(**admin)
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
        return
    conn.autocommit = True
    name = f"export_feedback_{uuid.uuid4().hex[:12]}"
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{name}"')
    except Exception as exc:
        conn.close()
        pytest.skip(f"Could not CREATE DATABASE: {exc}")
        return
    url = urlunparse(parsed._replace(path=f"/{name}", query=""))
    engine = create_engine(url.replace(parsed.scheme + "://", "postgresql+psycopg2://", 1))
    try:
        Base.metadata.create_all(engine)
        monkeypatch.setenv("DATABASE_URL", url)
        yield engine
    finally:
        engine.dispose()
        with conn.cursor() as cur:
            cur.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        conn.close()


def test_export_end_to_end_applies_retention_and_selectors(exporter_db, tmp_path):
    from sqlalchemy.orm import Session

    from feedback.models import ContactSubmission, Feedback

    now = datetime.now(UTC)
    ids = {n: uuid.uuid4() for n in ("fresh", "stale_text", "expired")}

    def fb(name, days):
        return Feedback(
            message_id=ids[name],
            rating="negative",
            comment=f"c-{name}",
            user_message=f"q-{name}",
            assistant_response=f"a-{name}",
            created_at=now - timedelta(days=days),
        )

    with Session(exporter_db) as s:
        s.add_all([fb("fresh", 1), fb("stale_text", 31), fb("expired", 91)])
        s.add_all(
            [
                ContactSubmission(
                    subject="bug", message="m-new", email="a@example.com", created_at=now
                ),
                ContactSubmission(
                    subject="other",
                    message="m-expired",
                    email="b@example.com",
                    created_at=now - timedelta(days=91),
                ),
            ]
        )
        s.commit()

    out = tmp_path / "fb.json"
    assert exporter.main(["--output", str(out)]) == 0
    rows = {r["message_id"]: r for r in json.loads(out.read_text())}
    assert str(ids["expired"]) not in rows  # past the row window: never returned
    assert rows[str(ids["fresh"])]["user_message"] == "q-fresh"
    assert rows[str(ids["fresh"])]["comment"] == "c-fresh"
    stale = rows[str(ids["stale_text"])]  # row exists, text is past 30 days: masked
    assert stale["user_message"] is None
    assert stale["assistant_response"] is None
    assert stale["comment"] is None
    assert stale["rating"] == "negative"

    out = tmp_path / "one.json"
    exporter.main(["--message-id", str(ids["fresh"]), "--output", str(out)])
    assert [r["message_id"] for r in json.loads(out.read_text())] == [str(ids["fresh"])]

    out = tmp_path / "contacts.csv"
    exporter.main(["--contacts", "--format", "csv", "--output", str(out)])
    text = out.read_text()
    assert "m-new" in text and "a@example.com" in text and "m-expired" not in text


# --- sslrootcert (verify-full on a fresh machine has no ~/.postgresql/root.crt) -----------

_BLOCKED = Path(__file__).resolve().parents[2] / "scripts" / "export_blocked_samples.py"
_MISSES = Path(__file__).resolve().parents[2] / "scripts" / "export_retrieval_misses.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(params=["feedback", "blocked", "misses"])
def sync_url(request):
    if request.param == "feedback":
        return exporter.sync_database_url
    path, name = (
        (_BLOCKED, "export_blocked_samples_ssl_t")
        if request.param == "blocked"
        else (_MISSES, "export_retrieval_misses_ssl_t")
    )
    return _load(path, name).sync_database_url


class TestSslRootCert:
    @pytest.mark.parametrize("mode", ["verify-full", "verify-ca"])
    def test_verify_modes_default_to_system_trust_store(self, sync_url, monkeypatch, mode):
        monkeypatch.delenv("PGSSLROOTCERT", raising=False)
        out = sync_url(f"postgresql://u:p@h/db?sslmode={mode}")
        assert out == f"postgresql+psycopg2://u:p@h/db?sslmode={mode}&sslrootcert=system"

    def test_asyncpg_style_ssl_param_also_gets_it(self, sync_url, monkeypatch):
        monkeypatch.delenv("PGSSLROOTCERT", raising=False)
        out = sync_url("postgresql+asyncpg://u:p@h/db?ssl=verify-full")
        assert "sslmode=verify-full" in out and "sslrootcert=system" in out

    def test_explicit_sslrootcert_is_kept(self, sync_url, monkeypatch):
        monkeypatch.delenv("PGSSLROOTCERT", raising=False)
        out = sync_url("postgresql://u:p@h/db?sslmode=verify-full&sslrootcert=/x/ca.pem")
        assert "sslrootcert=%2Fx%2Fca.pem" in out and "sslrootcert=system" not in out

    def test_pgsslrootcert_env_is_respected(self, sync_url, monkeypatch):
        monkeypatch.setenv("PGSSLROOTCERT", "/x/ca.pem")
        out = sync_url("postgresql://u:p@h/db?sslmode=verify-full")
        assert out == "postgresql+psycopg2://u:p@h/db?sslmode=verify-full"

    @pytest.mark.parametrize("mode", ["require", "disable", "prefer"])
    def test_other_modes_unchanged(self, sync_url, monkeypatch, mode):
        monkeypatch.delenv("PGSSLROOTCERT", raising=False)
        out = sync_url(f"postgresql://u:p@h/db?sslmode={mode}")
        assert out == f"postgresql+psycopg2://u:p@h/db?sslmode={mode}"
