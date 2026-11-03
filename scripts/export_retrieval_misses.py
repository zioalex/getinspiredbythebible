#!/usr/bin/env python3
"""
Export rows from the retrieval_miss_samples table for RAG tuning (BITB-256).

Read-only. Connects via DATABASE_URL (same convention as api/config.py)
and prints rows to stdout (or --output) as JSON or CSV.

The table is populated by the backend when settings.retrieval_miss_capture_enabled
is true. It holds only derived signals (topic ids, sanitized expansion keywords,
verse refs + scores, language, translation) and never message text. Rows expire a
fixed retention_days (default 90) after first sight and are purged hourly.
See docs/HOW-TO-EXPORT-RETRIEVAL-MISSES.md.

Usage:
    python scripts/export_retrieval_misses.py --help
    python scripts/export_retrieval_misses.py --format csv --since 2026-11-01
    python scripts/export_retrieval_misses.py --reason empty --language it --limit 100
    python scripts/export_retrieval_misses.py --aggregate --format csv
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

from feedback.models import RetrievalMissSample  # noqa: E402
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

FIELDS = [
    "id",
    "created_at",
    "last_seen_at",
    "expires_at",
    "reasons",
    "intent",
    "language",
    "translation",
    "topics",
    "expansion_terms",
    "top_refs",
    "top_score",
    "threshold",
    "cited_outside_pool",
    "retrieval_mode",
    "embedding_provider",
    "embedding_model",
    "session_id_hash",
    "signature_sha256",
    "hit_count",
]

AGGREGATE_FIELDS = ["topic", "language", "reason", "hits", "signatures"]


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
    """Map any Postgres URL to the sync psycopg2 driver (psycopg2-binary is what we install).

    A bare ``postgresql://`` would make SQLAlchemy 2 look for psycopg (v3), which is not
    installed, so it is rewritten too.
    """
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
        "postgresql://",
        "postgres://",
    ):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix) :]
    return url


def row_to_dict(row: RetrievalMissSample) -> dict[str, Any]:
    return {f: getattr(row, f) for f in FIELDS}


def to_json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def build_query(args: argparse.Namespace):
    stmt = (
        select(RetrievalMissSample)
        .where(RetrievalMissSample.expires_at > func.now())
        .order_by(RetrievalMissSample.created_at.desc())
    )
    if args.language:
        stmt = stmt.where(RetrievalMissSample.language == args.language)
    if args.translation:
        stmt = stmt.where(RetrievalMissSample.translation == args.translation)
    if args.reason:
        stmt = stmt.where(RetrievalMissSample.reasons.contains([args.reason]))
    if args.since:
        stmt = stmt.where(RetrievalMissSample.created_at >= args.since)
    if args.until:
        stmt = stmt.where(RetrievalMissSample.created_at < args.until)
    if args.limit:
        stmt = stmt.limit(args.limit)
    return stmt


def build_aggregate_query(args: argparse.Namespace):
    """Topic x language x reason, summing hit_count. Returns (TextClause, params).

    ``unnest(reasons)`` makes a multi-reason row count once per reason; an empty
    ``topics`` array contributes a single '(none)' bucket (the LEFT JOIN LATERAL
    keeps rows with no topic).
    """
    where = ["r.expires_at > now()"]
    params: dict[str, Any] = {}
    if args.language:
        where.append("r.language = :language")
        params["language"] = args.language
    if args.translation:
        where.append("r.translation = :translation")
        params["translation"] = args.translation
    if args.since:
        where.append("r.created_at >= :since")
        params["since"] = args.since
    if args.until:
        where.append("r.created_at < :until")
        params["until"] = args.until
    reason_filter = ""
    if args.reason:
        reason_filter = "WHERE reason = :reason"
        params["reason"] = args.reason
    limit = ""
    if args.limit:
        limit = "LIMIT :limit"
        params["limit"] = args.limit
    sql = f"""
        SELECT topic, language, reason,
               SUM(hit_count) AS hits, COUNT(*) AS signatures
        FROM (
            SELECT COALESCE(t.topic, '(none)') AS topic,
                   r.language AS language,
                   x.reason AS reason,
                   r.hit_count AS hit_count
            FROM retrieval_miss_samples r
            CROSS JOIN LATERAL unnest(r.reasons) AS x(reason)
            LEFT JOIN LATERAL jsonb_array_elements_text(r.topics) AS t(topic) ON true
            WHERE {" AND ".join(where)}
        ) flat
        {reason_filter}
        GROUP BY topic, language, reason
        ORDER BY hits DESC, topic, language, reason
        {limit}
    """  # noqa: S608 - only fixed fragments are interpolated; values are bound params
    return text(sql), params


def emit_json(rows: list[dict[str, Any]], stream: io.TextIOBase) -> None:
    json.dump(
        [{k: to_json_safe(v) for k, v in row.items()} for row in rows],
        stream,
        ensure_ascii=False,
        indent=2,
    )
    stream.write("\n")


def emit_csv(
    rows: list[dict[str, Any]], stream: io.TextIOBase, fields: list[str] | None = None
) -> None:
    writer = csv.DictWriter(stream, fieldnames=fields or FIELDS)
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
        description="Export rows from retrieval_miss_samples (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument(
        "--reason",
        choices=("empty", "low_score", "cited_outside_pool"),
        help="Only rows carrying this miss reason.",
    )
    parser.add_argument("--language", help="Filter by language (ISO code).")
    parser.add_argument("--translation", help='Filter by translation (e.g. "kjv", "web").')
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
        "--aggregate",
        action="store_true",
        help="Group by topic x language x reason (summing hit_count) instead of listing rows.",
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
        if args.aggregate:
            stmt, params = build_aggregate_query(args)
            rows = [
                {
                    "topic": r.topic,
                    "language": r.language,
                    "reason": r.reason,
                    "hits": int(r.hits),
                    "signatures": int(r.signatures),
                }
                for r in session.execute(stmt, params)
            ]
            fields = AGGREGATE_FIELDS
        else:
            rows = [row_to_dict(r) for r in session.execute(build_query(args)).scalars()]
            fields = FIELDS

    if args.format == "json":
        emit_json(rows, args.output)
    else:
        emit_csv(rows, args.output, fields)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
