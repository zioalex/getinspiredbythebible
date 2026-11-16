#!/usr/bin/env python3
"""
Export feedback or contact-form rows, including their text, while it still exists.

Read-only. Connects via DATABASE_URL (same convention as api/config.py) and prints rows to
stdout (or --output) as JSON or CSV.

Notification e-mails carry identifiers only (BITB-329); this tool is how the operator reads
the full text. Retention (enforced by the API's hourly sweep, see api/feedback/retention.py):

- feedback text (user_message, assistant_response, comment): FEEDBACK_TEXT_RETENTION_DAYS
  (30), then NULL;
- the rest of a feedback row: FEEDBACK_RETENTION_DAYS (90), then deleted;
- contact submissions: CONTACT_RETENTION_DAYS (90), then deleted.

Between a row's expiry and the next sweep it still exists, so every query also filters on
created_at > now() - interval and never returns a row (or text) past its limit.

Usage:
    python scripts/export_feedback.py --help
    python scripts/export_feedback.py --message-id 3f2b1c9e-...-...            # one feedback
    python scripts/export_feedback.py --rating negative --since 2026-11-01 --format csv
    python scripts/export_feedback.py --contacts --id 12                       # one contact
    python scripts/export_feedback.py --contacts --subject bug --limit 20

See docs/HOW-TO-EXPORT-FEEDBACK.md (firewall, DATABASE_URL, cleanup).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from config import settings  # noqa: E402
from feedback.models import ContactSubmission, Feedback  # noqa: E402
from sqlalchemy import case, create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

FEEDBACK_FIELDS = [
    "id",
    "created_at",
    "message_id",
    "rating",
    "reason",
    "comment",
    "user_message",
    "assistant_response",
    "verses_cited",
    "model_used",
    "response_time_ms",
    "session_id",
]
CONTACT_FIELDS = [
    "id",
    "created_at",
    "subject",
    "email",
    "message",
    "status",
    "session_id",
]

CONTACT_SUBJECTS = ("spiritual", "bug", "feature", "feedback", "other")


def parse_date(value: str) -> datetime:
    """Accept YYYY-MM-DD or full ISO 8601 and return a UTC-aware datetime."""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}: expected YYYY-MM-DD or ISO 8601"
        ) from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid UUID {value!r}") from e


def sync_database_url(url: str) -> str:
    """Map any Postgres URL to the sync psycopg2 driver (psycopg2-binary is what we install).

    Same rewrite as scripts/export_blocked_samples.py: a bare ``postgresql://`` would make
    SQLAlchemy 2 look for psycopg (v3), and asyncpg-style ``ssl=`` becomes ``sslmode=``.
    """
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
        "postgresql://",
        "postgres://",
    ):
        if url.startswith(prefix):
            url = "postgresql+psycopg2://" + url[len(prefix) :]
            break
    else:
        return url
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    ssl_value = query.pop("ssl", [None])[0]
    if ssl_value and "sslmode" not in query:
        query["sslmode"] = [ssl_value]
    # libpq's verify-full/verify-ca need a root cert; without ~/.postgresql/root.crt they fail on
    # a fresh machine. ``sslrootcert=system`` (libpq >= 16) uses the OS trust store instead.
    if (
        query.get("sslmode", [None])[0] in ("verify-full", "verify-ca")
        and "sslrootcert" not in query
        and not os.environ.get("PGSSLROOTCERT")
    ):
        query["sslrootcert"] = ["system"]
    return urlunsplit(parts._replace(query=urlencode(query, doseq=True)))


def to_json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def row_to_dict(row: Any, fields: list[str]) -> dict[str, Any]:
    return {f: getattr(row, f) for f in fields}


def _age_limit(days: int):
    """``now() - make_interval(days => N)`` with N bound as a parameter."""
    return func.now() - func.make_interval(0, 0, 0, days)


def build_feedback_query(args: argparse.Namespace, *, text_days: int, row_days: int):
    """Feedback rows within retention. Text columns are blanked past the text window.

    The sweep NULLs the text after ``text_days``; the CASE below does the same at read time
    so a row between 30 days and the next sweep never yields text either.
    """
    over_text_limit = Feedback.created_at <= _age_limit(text_days)

    def masked(col):
        return case((over_text_limit, None), else_=col).label(col.key)

    stmt = (
        select(
            Feedback.id,
            Feedback.created_at,
            Feedback.message_id,
            Feedback.rating,
            Feedback.reason,
            masked(Feedback.comment),
            masked(Feedback.user_message),
            masked(Feedback.assistant_response),
            Feedback.verses_cited,
            Feedback.model_used,
            Feedback.response_time_ms,
            Feedback.session_id,
        )
        .where(Feedback.created_at > _age_limit(row_days))
        .order_by(Feedback.created_at.desc())
    )
    if args.id is not None:
        stmt = stmt.where(Feedback.id == args.id)
    if args.message_id is not None:
        stmt = stmt.where(Feedback.message_id == args.message_id)
    if args.rating:
        stmt = stmt.where(Feedback.rating == args.rating)
    if args.since:
        stmt = stmt.where(Feedback.created_at >= args.since)
    if args.until:
        stmt = stmt.where(Feedback.created_at < args.until)
    if args.limit:
        stmt = stmt.limit(args.limit)
    return stmt


def build_contact_query(args: argparse.Namespace, *, contact_days: int):
    """Contact submissions within retention."""
    stmt = (
        select(ContactSubmission)
        .where(ContactSubmission.created_at > _age_limit(contact_days))
        .order_by(ContactSubmission.created_at.desc())
    )
    if args.id is not None:
        stmt = stmt.where(ContactSubmission.id == args.id)
    if args.subject:
        stmt = stmt.where(ContactSubmission.subject == args.subject)
    if args.since:
        stmt = stmt.where(ContactSubmission.created_at >= args.since)
    if args.until:
        stmt = stmt.where(ContactSubmission.created_at < args.until)
    if args.limit:
        stmt = stmt.limit(args.limit)
    return stmt


def emit_json(rows: list[dict[str, Any]], stream: io.TextIOBase) -> None:
    json.dump(
        [{k: to_json_safe(v) for k, v in row.items()} for row in rows],
        stream,
        ensure_ascii=False,
        indent=2,
    )
    stream.write("\n")


def emit_csv(rows: list[dict[str, Any]], fields: list[str], stream: io.TextIOBase) -> None:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                k: (
                    json.dumps(v, ensure_ascii=False)
                    if isinstance(v, (dict, list))
                    else to_json_safe(v)
                )
                for k, v in row.items()
            }
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export feedback (default) or contact-form rows with their text (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument(
        "--contacts",
        action="store_true",
        help="Export contact-form submissions instead of feedback.",
    )
    parser.add_argument(
        "--id", type=int, help="Row id (feedback.id, or contact id with --contacts)."
    )
    parser.add_argument(
        "--message-id",
        type=parse_uuid,
        help="Feedback only: the chat message UUID (shown in the notification e-mail).",
    )
    parser.add_argument("--rating", choices=("positive", "negative"), help="Feedback only.")
    parser.add_argument(
        "--subject",
        choices=CONTACT_SUBJECTS,
        help="Contacts only: filter by subject category.",
    )
    parser.add_argument(
        "--since",
        type=parse_date,
        help="Include rows created at or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--until",
        type=parse_date,
        help="Exclude rows created at or after this date (YYYY-MM-DD).",
    )
    parser.add_argument("--limit", type=int, help="Maximum rows to return.")
    parser.add_argument(
        "--output",
        type=argparse.FileType("w", encoding="utf-8"),
        default=sys.stdout,
        help="Write to file instead of stdout.",
    )
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject selectors that do not apply to the chosen table."""
    if args.contacts:
        for flag, value in (("--message-id", args.message_id), ("--rating", args.rating)):
            if value is not None:
                parser.error(f"{flag} is for feedback; it cannot be combined with --contacts.")
    elif args.subject:
        parser.error("--subject is for contacts; add --contacts.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)

    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL is not set in the environment.")

    engine = create_engine(sync_database_url(url), future=True)
    with Session(engine) as session:
        if args.contacts:
            stmt = build_contact_query(args, contact_days=settings.contact_retention_days)
            rows = [row_to_dict(r, CONTACT_FIELDS) for r in session.execute(stmt).scalars()]
            fields = CONTACT_FIELDS
        else:
            stmt = build_feedback_query(
                args,
                text_days=settings.feedback_text_retention_days,
                row_days=settings.feedback_retention_days,
            )
            rows = [dict(r._mapping) for r in session.execute(stmt)]
            fields = FEEDBACK_FIELDS

    if args.format == "json":
        emit_json(rows, args.output)
    else:
        emit_csv(rows, fields, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
