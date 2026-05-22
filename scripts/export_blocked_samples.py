#!/usr/bin/env python3
"""
Export rows from the blocked_message_samples table for safety-filter tuning.

Read-only. Connects via DATABASE_URL (same convention as api/config.py)
and prints rows to stdout (or --output) as JSON or CSV.

The table is populated by the backend when settings.blocked_sample_capture_enabled
is true. Rows expire after settings.blocked_sample_retention_days (default 30
days) and are purged on app startup. See docs/HOW-TO-EXPORT-BLOCKED-SAMPLES.md.

Usage:
    python scripts/export_blocked_samples.py --help
    python scripts/export_blocked_samples.py --format csv --since 2026-05-01
    DATABASE_URL=postgresql://... python scripts/export_blocked_samples.py \\
        --stage keyword --limit 100
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Reuse the SQLAlchemy model defined in the api package without forcing a
# packaging change. The repo layout has api/ as a top-level directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from feedback.models import BlockedMessageSample  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

FIELDS = [
    "id",
    "created_at",
    "expires_at",
    "stage",
    "categories",
    "severity",
    "language",
    "message_text",
    "message_sha256",
    "session_id_hash",
    "hit_count",
    "reviewed",
]


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


def sync_database_url(url: str) -> str:
    """Strip the async asyncpg driver so the script can use sync SQLAlchemy."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def row_to_dict(row: BlockedMessageSample) -> dict[str, Any]:
    return {f: getattr(row, f) for f in FIELDS}


def to_json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def build_query(args: argparse.Namespace):
    stmt = select(BlockedMessageSample).order_by(BlockedMessageSample.created_at.desc())
    if args.stage:
        stmt = stmt.where(BlockedMessageSample.stage == args.stage)
    if args.language:
        stmt = stmt.where(BlockedMessageSample.language == args.language)
    if args.since:
        stmt = stmt.where(BlockedMessageSample.created_at >= args.since)
    if args.until:
        stmt = stmt.where(BlockedMessageSample.created_at < args.until)
    if args.reviewed is True:
        stmt = stmt.where(BlockedMessageSample.reviewed.is_(True))
    elif args.reviewed is False:
        stmt = stmt.where(BlockedMessageSample.reviewed.is_(False))
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


def emit_csv(rows: list[dict[str, Any]], stream: io.TextIOBase) -> None:
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export rows from blocked_message_samples (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument(
        "--stage",
        help='Filter by stage (e.g. "keyword", "content_safety").',
    )
    parser.add_argument("--language", help="Filter by detected language (ISO code).")
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
    reviewed = parser.add_mutually_exclusive_group()
    reviewed.add_argument(
        "--reviewed",
        dest="reviewed",
        action="store_true",
        default=None,
        help="Only rows marked reviewed=true.",
    )
    reviewed.add_argument(
        "--unreviewed",
        dest="reviewed",
        action="store_false",
        help="Only rows marked reviewed=false.",
    )
    parser.add_argument(
        "--output",
        type=argparse.FileType("w", encoding="utf-8"),
        default=sys.stdout,
        help="Write to file instead of stdout.",
    )
    args = parser.parse_args(argv)

    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL is not set in the environment.")

    engine = create_engine(sync_database_url(url), future=True)
    with Session(engine) as session:
        rows = [row_to_dict(r) for r in session.execute(build_query(args)).scalars()]

    if args.format == "json":
        emit_json(rows, args.output)
    else:
        emit_csv(rows, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
