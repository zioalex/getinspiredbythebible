#!/usr/bin/env python3
"""
Alarm when ``verse_topics`` (BITB-044) is empty or out of band for a
supported-language translation (BITB-105).

``populate_verse_topics.py`` fills ``verse_topics``; this script proves it
actually worked by reading the table back from the database, independently
of that run's own in-memory tally. A check built on the populate run's own
counters would report success even if every insert silently did nothing —
exactly the failure this story exists to catch (verse_topics sat empty for
months while the population *capability* existed and nobody ran it).

BITB-044 measured 18.3% verse-tagged coverage for KJV (en) and 12.3% for
Luther 1912 (de). The default floor (5%) sits well below either measured
value on purpose: five of the seven supported languages (it, es, fr, pt, ar)
have never been validated against a real corpus (BITB-106), and a thinner
keyword vocabulary can legitimately land lower. The floor exists to catch
zero and near-total collapse, not to police quality -- tighten it with
per-language numbers once BITB-106 supplies them.

The default ceiling (60%) is a different metric from the script's own
per-topic 25%-of-verses denylist guideline: overall coverage stacks 13
topics, so ~18% overall is consistent with no single topic exceeding ~3.2%.
Above 60% of a translation's verses tagged means a keyword has gone generic
corpus-wide.

Decision (BITB-105): a coverage violation alarms, it does not fail the
deploy. Topic rows feed a ranking boost that is itself gated by
``topic_boosting_enabled`` -- an untagged corpus degrades ranking quality,
never correctness or availability. This script exits 0 on a violation
unless run with --strict, which is what the negative rehearsal
(docs/HOW-TO-POPULATE-VERSE-TOPICS.md) and the unit tests use to prove the
alarm path actually fires.

Usage:
    export DATABASE_URL="postgresql+asyncpg://user:pass@host/db?ssl=require"  # pragma: allowlist secret
    python scripts/check_verse_topic_coverage.py
    python scripts/check_verse_topic_coverage.py --floor 100 --strict   # negative rehearsal

Exit codes:
    0: No violations, or violations present but --strict not passed
    1: --strict passed and at least one alarming violation was found, or a
       DB/connection error occurred
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from chat.topics import SUPPORTED_TOPIC_LANGUAGES  # noqa: E402


def _load_migration_utils():
    """Load scripts/migrations/utils.py by file path -- see
    populate_verse_topics.py for why this can't just be a package import
    (it would shadow api/utils, also named "utils")."""
    utils_path = REPO_ROOT / "scripts" / "migrations" / "utils.py"
    spec = importlib.util.spec_from_file_location("_migration_db_utils", utils_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


get_migration_connection_params = _load_migration_utils().get_migration_connection_params

DEFAULT_FLOOR_PCT = 5.0
DEFAULT_CEILING_PCT = 60.0
DEFAULT_MIN_VERSES_FOR_RATIO = 1_000

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_BELOW_FLOOR = "below_floor"
STATUS_ABOVE_CEILING = "above_ceiling"
STATUS_SMALL_SAMPLE = "small_sample"
STATUS_NO_VERSES = "no_verses"


def log(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True)
class CoverageResult:
    translation: str
    language_code: str
    verse_count: int
    tagged_verse_count: int
    coverage_pct: float
    status: str
    alarm: bool
    message: str


def evaluate_coverage(
    translation: str,
    language_code: str,
    verse_count: int,
    tagged_verse_count: int,
    *,
    floor_pct: float = DEFAULT_FLOOR_PCT,
    ceiling_pct: float = DEFAULT_CEILING_PCT,
    min_verses_for_ratio: int = DEFAULT_MIN_VERSES_FOR_RATIO,
) -> CoverageResult:
    """Classify one translation's verse_topics coverage.

    Order matters: emptiness is checked (and alarmed) before the small-sample
    exemption, so a handful of verses with zero tags still alarms -- only the
    *ratio* thresholds are unreliable on a small corpus, not the zero case.
    """
    coverage_pct = (100.0 * tagged_verse_count / verse_count) if verse_count else 0.0

    if verse_count == 0:
        return CoverageResult(
            translation,
            language_code,
            verse_count,
            tagged_verse_count,
            coverage_pct,
            STATUS_NO_VERSES,
            False,
            f"{translation} ({language_code}): no verses loaded yet -- nothing to tag",
        )

    if tagged_verse_count == 0:
        return CoverageResult(
            translation,
            language_code,
            verse_count,
            tagged_verse_count,
            coverage_pct,
            STATUS_EMPTY,
            True,
            f"{translation} ({language_code}): verse_topics has 0 rows for "
            f"{verse_count:,} verses -- topic boosting is a silent no-op for this translation",
        )

    if verse_count < min_verses_for_ratio:
        return CoverageResult(
            translation,
            language_code,
            verse_count,
            tagged_verse_count,
            coverage_pct,
            STATUS_SMALL_SAMPLE,
            False,
            f"{translation} ({language_code}): only {verse_count:,} verses loaded "
            f"(< {min_verses_for_ratio:,}) -- coverage % not meaningful yet",
        )

    if coverage_pct < floor_pct:
        return CoverageResult(
            translation,
            language_code,
            verse_count,
            tagged_verse_count,
            coverage_pct,
            STATUS_BELOW_FLOOR,
            True,
            f"{translation} ({language_code}): {tagged_verse_count:,}/{verse_count:,} verses "
            f"tagged ({coverage_pct:.1f}%) is below the {floor_pct:.1f}% floor",
        )

    if coverage_pct > ceiling_pct:
        return CoverageResult(
            translation,
            language_code,
            verse_count,
            tagged_verse_count,
            coverage_pct,
            STATUS_ABOVE_CEILING,
            True,
            f"{translation} ({language_code}): {tagged_verse_count:,}/{verse_count:,} verses "
            f"tagged ({coverage_pct:.1f}%) is above the {ceiling_pct:.1f}% ceiling",
        )

    return CoverageResult(
        translation,
        language_code,
        verse_count,
        tagged_verse_count,
        coverage_pct,
        STATUS_OK,
        False,
        f"{translation} ({language_code}): {tagged_verse_count:,}/{verse_count:,} verses "
        f"tagged ({coverage_pct:.1f}%) -- in band",
    )


def evaluate_all(
    rows: list[dict],
    *,
    floor_pct: float = DEFAULT_FLOOR_PCT,
    ceiling_pct: float = DEFAULT_CEILING_PCT,
    min_verses_for_ratio: int = DEFAULT_MIN_VERSES_FOR_RATIO,
) -> list[CoverageResult]:
    return [
        evaluate_coverage(
            row["code"],
            row["language_code"],
            row["verse_count"],
            row["tagged_verse_count"],
            floor_pct=floor_pct,
            ceiling_pct=ceiling_pct,
            min_verses_for_ratio=min_verses_for_ratio,
        )
        for row in rows
    ]


def render_annotations(results: list[CoverageResult]) -> list[str]:
    """GitHub Actions ::warning:: lines, one per alarming result. These
    surface at the top of the run and in the checks UI -- where an operator
    actually sees a warning that exits 0."""
    return [f"::warning::{result.message}" for result in results if result.alarm]


def render_summary(results: list[CoverageResult]) -> str:
    """Markdown table for $GITHUB_STEP_SUMMARY, every translation included
    (not just alarms) -- the durable per-run record."""
    lines = [
        "### Verse Topic Coverage",
        "",
        "| Translation | Language | Verses | Tagged | Coverage | Status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for result in results:
        marker = "⚠️ " if result.alarm else ""
        lines.append(
            f"| {result.translation} | {result.language_code} | {result.verse_count:,} | "
            f"{result.tagged_verse_count:,} | {result.coverage_pct:.1f}% | "
            f"{marker}{result.status} |"
        )
    return "\n".join(lines)


def exit_code(results: list[CoverageResult], *, strict: bool) -> int:
    if strict and any(result.alarm for result in results):
        return 1
    return 0


async def fetch_coverage_rows(
    conn: asyncpg.Connection, languages: frozenset[str], requested: list[str] | None
) -> list[dict]:
    query = """
        SELECT t.code,
               t.language_code,
               (SELECT COUNT(*) FROM verses v WHERE v.translation = t.code) AS verse_count,
               (SELECT COUNT(DISTINCT vt.verse_id)
                  FROM verse_topics vt JOIN verses v ON v.id = vt.verse_id
                 WHERE v.translation = t.code) AS tagged_verse_count
          FROM translations t
         WHERE t.language_code = ANY($1::text[])
         ORDER BY t.code
    """
    rows = await conn.fetch(query, list(languages))
    if requested:
        wanted = set(requested)
        rows = [row for row in rows if row["code"] in wanted]
    return [dict(row) for row in rows]


async def run(args: argparse.Namespace) -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        log("ERROR: DATABASE_URL environment variable is not set.")
        return 1

    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        try:
            rows = await fetch_coverage_rows(
                conn, frozenset(SUPPORTED_TOPIC_LANGUAGES), args.translation
            )
        except asyncpg.exceptions.UndefinedTableError:
            log(
                "::warning::verse_topics table does not exist -- has migration "
                "004_add_topic_boosting_schema.sql been applied?"
            )
            return 1 if args.strict else 0

        if not rows:
            log("No matching translations to check (check --translation / language support).")
            return 1

        results = evaluate_all(
            rows,
            floor_pct=args.floor,
            ceiling_pct=args.ceiling,
            min_verses_for_ratio=args.min_verses,
        )

        for result in results:
            log(result.message)

        for annotation in render_annotations(results):
            log(annotation)

        step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary_path:
            with open(step_summary_path, "a") as handle:
                handle.write(render_summary(results) + "\n")

        return exit_code(results, strict=args.strict)
    finally:
        await conn.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Alarm on empty or out-of-band verse_topics coverage (BITB-105).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--floor", type=float, default=DEFAULT_FLOOR_PCT, help="Minimum coverage %%."
    )
    parser.add_argument(
        "--ceiling", type=float, default=DEFAULT_CEILING_PCT, help="Maximum coverage %%."
    )
    parser.add_argument(
        "--min-verses",
        type=int,
        default=DEFAULT_MIN_VERSES_FOR_RATIO,
        help="Below this verse count, only emptiness is alarmed (not the ratio).",
    )
    parser.add_argument(
        "--translation",
        action="append",
        help="Limit to this translation code (repeatable). Default: all supported-language translations.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when a violation is found (default: alarm only, exit 0).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
