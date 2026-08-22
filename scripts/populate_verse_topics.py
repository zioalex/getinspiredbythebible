#!/usr/bin/env python3
"""
Populate the ``verse_topics`` junction table from the topic keyword map
(BITB-044).

Topic-based search-ranking boost was built under BITB-018: query-side topic
detection exists (``api/chat/topics.py``), the ranking query already
``LEFT JOIN``s ``verse_topics`` (``api/scripture/repository.py``), and
migration ``004_add_topic_boosting_schema.sql`` created the table and seeded
the 13 ``topics`` rows. But nothing has ever inserted a row into
``verse_topics`` — the join always returns zero matches, so the boost is a
silent no-op even when ``topic_boosting_enabled`` is flipped on. This script
fills that gap.

Approach: deterministic, offline keyword matching (``api/chat/topic_tagging.py``)
reusing the exact vocabulary ``detect_topics()`` already uses on the query
side — no LLM calls, no API budget, fully re-runnable. This intentionally
does NOT flip ``topic_boosting_enabled`` or tune ``topic_boost_factor`` —
those require validating against the BITB-043 golden eval set and are a
follow-up once this data exists.

Idempotent: ``(verse_id, topic_id)`` is the table's primary key (migration
004), so a plain re-run with no ``--replace`` only adds pairs that weren't
already there — running it twice inserts 0 new rows the second time. Pass
``--replace`` to delete and re-seed a translation's rows first (e.g. after
editing ``TOPIC_KEYWORD_MAP`` or ``CORPUS_KEYWORD_DENYLIST``).

Only translations whose ``language_code`` is one of the 7 the keyword map
covers (en, it, de, es, fr, pt, ar) are tagged; others (ru, zh, hi, ko, ...)
are reported as skipped since the map has no vocabulary for them.

Denylist tuning: if a run's ``--verbose`` coverage report shows any topic
tagging more than 25% of a translation's verses, that's a sign a keyword is
too generic for corpus-scale matching (it's fine for the query side, where a
false positive just adds an extra boost term to one message). Add the
offending keyword to ``CORPUS_KEYWORD_DENYLIST`` in
``api/chat/topic_tagging.py`` with a comment recording the observed hit
count, then re-run with ``--replace``. As of this script's introduction, a
dry run against the real KJV (en) and Luther 1912 (de) corpora found no
topic above ~3.2% and no keyword above ~2% — well under that threshold — so
the denylist starts empty; other languages have not been validated the same
way in this repo and should get a ``--dry-run --verbose`` pass before being
trusted.

Usage:
    export DATABASE_URL="postgresql+asyncpg://user:pass@host/db?ssl=require"  # pragma: allowlist secret
    python scripts/populate_verse_topics.py --dry-run --verbose
    python scripts/populate_verse_topics.py
    python scripts/populate_verse_topics.py --translation kjv --translation web --replace

Exit codes:
    0: Success
    1: Failure (missing topics row, DB error, etc.)
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from chat.topic_tagging import (  # noqa: E402
    build_keyword_matchers,
    build_topic_matchers,
    match_topic_keywords,
    match_topics,
)
from chat.topics import SUPPORTED_TOPIC_LANGUAGES, TOPIC_KEYWORDS_BY_LANGUAGE  # noqa: E402


def _load_migration_utils():
    """Load scripts/migrations/utils.py by file path rather than adding its
    directory to sys.path — that directory's ``utils.py`` module would
    otherwise shadow the ``api/utils`` package (also named "utils") for
    every import after this one, breaking chat.service's own imports."""
    utils_path = REPO_ROOT / "scripts" / "migrations" / "utils.py"
    spec = importlib.util.spec_from_file_location("_migration_db_utils", utils_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


get_migration_connection_params = _load_migration_utils().get_migration_connection_params

DEFAULT_BATCH_SIZE = 5000
TOP_KEYWORDS_PER_TOPIC = 10


def log(message: str) -> None:
    """Print a timestamped, immediately-flushed log line (CI visibility)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


@dataclass
class TranslationTarget:
    code: str
    language_code: str


@dataclass
class TranslationStats:
    target: TranslationTarget
    verse_count: int = 0
    tagged_verse_count: int = 0
    pairs_found: int = 0
    inserted: int = 0
    already_present: int = 0
    topic_counts: dict[str, int] = field(default_factory=dict)
    keyword_counts: dict[str, dict[str, int]] = field(default_factory=dict)


def select_targets(
    rows: list[dict], requested: list[str] | None, supported: frozenset[str]
) -> list[TranslationTarget]:
    """Pick which translations to process.

    ``rows`` is the raw ``[{"code": ..., "language_code": ...}, ...]`` result
    from ``translations``. ``requested`` is the (possibly empty) list of
    ``--translation`` codes; when empty, every row whose language is
    supported is selected. Unsupported-language translations are always
    excluded, whether or not they were explicitly requested — there is no
    keyword vocabulary to tag them with.
    """
    targets = [
        TranslationTarget(code=row["code"], language_code=row["language_code"])
        for row in rows
        if row["language_code"] in supported
    ]
    if requested:
        wanted = set(requested)
        targets = [t for t in targets if t.code in wanted]
    return targets


async def load_topic_ids(conn: asyncpg.Connection) -> dict[str, int]:
    """Return ``{topic_name: topic_id}`` for the 13 topics the keyword map
    covers. Raises if any of them is missing from the ``topics`` table —
    that would mean migration 004 hasn't run."""
    rows = await conn.fetch("SELECT id, name FROM topics")
    by_name = {row["name"]: row["id"] for row in rows}
    missing = set(TOPIC_KEYWORDS_BY_LANGUAGE.keys()) - set(by_name.keys())
    if missing:
        raise RuntimeError(
            f"topics table is missing rows for: {sorted(missing)}. "
            "Has migration 004_add_topic_boosting_schema.sql been applied?"
        )
    return {name: by_name[name] for name in TOPIC_KEYWORDS_BY_LANGUAGE}


async def insert_pairs(
    conn: asyncpg.Connection, pairs: list[tuple[int, int]], batch_size: int
) -> None:
    """Upsert ``(verse_id, topic_id)`` rows in batches, one transaction per
    batch. ``ON CONFLICT DO NOTHING`` makes this safe to re-run."""
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        async with conn.transaction():
            await conn.executemany(
                "INSERT INTO verse_topics (verse_id, topic_id) VALUES ($1, $2) "
                "ON CONFLICT (verse_id, topic_id) DO NOTHING",
                batch,
            )


async def process_translation(
    conn: asyncpg.Connection,
    target: TranslationTarget,
    topic_ids: dict[str, int],
    *,
    dry_run: bool,
    replace: bool,
    limit: int | None,
    batch_size: int,
    verbose: bool,
) -> TranslationStats:
    stats = TranslationStats(target=target)

    existing_rows = await conn.fetch(
        "SELECT vt.verse_id, vt.topic_id FROM verse_topics vt "
        "JOIN verses v ON v.id = vt.verse_id WHERE v.translation = $1",
        target.code,
    )
    existing_pairs = {(row["verse_id"], row["topic_id"]) for row in existing_rows}

    if replace:
        if not dry_run:
            await conn.execute(
                "DELETE FROM verse_topics WHERE verse_id IN "
                "(SELECT id FROM verses WHERE translation = $1)",
                target.code,
            )
        # Whether or not this is a dry run, --replace means "pretend the
        # slate is clean" for the insert/already-present split below.
        existing_pairs = set()

    query = "SELECT id, text FROM verses WHERE translation = $1 ORDER BY id"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    verse_rows = await conn.fetch(query, target.code)
    stats.verse_count = len(verse_rows)

    topic_matchers = build_topic_matchers(target.language_code)
    keyword_matchers = build_keyword_matchers(target.language_code) if verbose else None

    pairs: set[tuple[int, int]] = set()
    for row in verse_rows:
        topics = match_topics(row["text"], target.language_code, topic_matchers)
        if not topics:
            continue
        stats.tagged_verse_count += 1
        for topic in topics:
            stats.topic_counts[topic] = stats.topic_counts.get(topic, 0) + 1
            pairs.add((row["id"], topic_ids[topic]))

        if verbose and keyword_matchers is not None:
            hits = match_topic_keywords(row["text"], target.language_code, keyword_matchers)
            for topic, keywords in hits.items():
                bucket = stats.keyword_counts.setdefault(topic, {})
                for keyword in keywords:
                    bucket[keyword] = bucket.get(keyword, 0) + 1

    stats.pairs_found = len(pairs)
    new_pairs = pairs - existing_pairs
    stats.already_present = len(pairs) - len(new_pairs)

    if not dry_run and new_pairs:
        await insert_pairs(conn, list(new_pairs), batch_size)
    stats.inserted = len(new_pairs)

    return stats


def _print_translation_report(stats: TranslationStats, verbose: bool, dry_run: bool) -> None:
    t = stats.target
    coverage_pct = (100 * stats.tagged_verse_count / stats.verse_count) if stats.verse_count else 0
    inserted_label = "would insert" if dry_run else "inserted"
    log(
        f"{t.code} ({t.language_code}): {stats.verse_count:,} verses, "
        f"{stats.tagged_verse_count:,} tagged ({coverage_pct:.1f}%), "
        f"{stats.pairs_found:,} pairs -> {stats.inserted:,} {inserted_label}, "
        f"{stats.already_present:,} already present"
    )
    for topic in sorted(stats.topic_counts):
        count = stats.topic_counts[topic]
        pct = (100 * count / stats.verse_count) if stats.verse_count else 0
        flag = "  <== exceeds 25% guideline" if pct > 25 else ""
        line = f"    {topic:12s} {count:6,d}  ({pct:4.1f}%){flag}"
        if verbose and topic in stats.keyword_counts:
            top = sorted(stats.keyword_counts[topic].items(), key=lambda kv: -kv[1])
            top_str = " | ".join(f"{kw} {c}" for kw, c in top[:TOP_KEYWORDS_PER_TOPIC])
            line += f"   [{top_str}]"
        log(line)


async def run(args: argparse.Namespace) -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        log("ERROR: DATABASE_URL environment variable is not set.")
        return 1

    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        topic_ids = await load_topic_ids(conn)

        translation_rows = await conn.fetch("SELECT code, language_code FROM translations")
        targets = select_targets(
            [dict(row) for row in translation_rows],
            args.translation,
            frozenset(SUPPORTED_TOPIC_LANGUAGES),
        )
        if not targets:
            log("No matching translations to process (check --translation / language support).")
            return 1

        unsupported = [
            row["code"]
            for row in translation_rows
            if row["language_code"] not in SUPPORTED_TOPIC_LANGUAGES
        ]
        if unsupported:
            log(f"Skipping translations with unsupported language: {sorted(unsupported)}")

        log(
            f"Processing {len(targets)} translation(s): {[t.code for t in targets]}"
            f"{' [DRY RUN]' if args.dry_run else ''}"
        )

        all_stats: list[TranslationStats] = []
        for target in targets:
            stats = await process_translation(
                conn,
                target,
                topic_ids,
                dry_run=args.dry_run,
                replace=args.replace,
                limit=args.limit,
                batch_size=args.batch_size,
                verbose=args.verbose,
            )
            _print_translation_report(stats, args.verbose, args.dry_run)
            all_stats.append(stats)

        total_pairs = sum(s.pairs_found for s in all_stats)
        total_inserted = sum(s.inserted for s in all_stats)
        grand_topic_counts: dict[str, int] = {}
        for s in all_stats:
            for topic, count in s.topic_counts.items():
                grand_topic_counts[topic] = grand_topic_counts.get(topic, 0) + count

        totals_label = "would newly insert" if args.dry_run else "newly inserted"
        log(
            f"Totals: {total_pairs:,} pairs across {len(all_stats)} translation(s), "
            f"{total_inserted:,} {totals_label}"
        )
        for topic in sorted(grand_topic_counts):
            log(f"    {topic:12s} {grand_topic_counts[topic]:6,d}")

        if args.dry_run:
            log("Dry run complete — no rows were written.")

        return 0
    finally:
        await conn.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Populate verse_topics from the topic keyword map (BITB-044).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute matches and print the coverage report without writing to the database.",
    )
    parser.add_argument(
        "--translation",
        action="append",
        help="Limit to this translation code (repeatable). Default: all supported-language translations.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete a translation's existing verse_topics rows before re-tagging it.",
    )
    parser.add_argument("--limit", type=int, help="Only process the first N verses per translation (debugging).")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per INSERT batch (default {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also report the top contributing keywords per topic.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
