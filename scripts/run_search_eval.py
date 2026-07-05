#!/usr/bin/env python3
"""CLI for the retrieval-evaluation harness (BITB-051).

Usage
-----
--validate   Validate the golden-set file (no DB/LLM required; safe to run in CI).
             Exits 0 on success, 1 on validation failure.

Future phases (P3/P4) will add --run, --config, --language, --smoke, --json flags
that execute real retrieval against a live database.

Example
-------
    python scripts/run_search_eval.py --validate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the ``api`` package directory is on the path when invoked from the
# project root (e.g. ``python scripts/run_search_eval.py``).
_REPO_ROOT = Path(__file__).parent.parent
_API_DIR = _REPO_ROOT / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def _cmd_validate(args: argparse.Namespace) -> int:
    """Load and validate the golden set; print a coverage summary."""
    from search_eval.loader import (
        coverage_summary,
        load_golden_set,
        supported_languages,
    )

    path = Path(args.path) if args.path else None

    try:
        cases = load_golden_set(path)
    except FileNotFoundError as exc:
        print(f"ERROR: golden-set file not found — {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: validation failed — {exc}", file=sys.stderr)
        return 1

    summary = coverage_summary(cases)
    supported = supported_languages()
    missing = supported - set(summary)

    print(f"Golden set: {len(cases)} cases across {len(summary)} languages")
    for lang in sorted(summary):
        print(f"  {lang}: {summary[lang]} cases")

    ids = [c.id for c in cases]
    duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
    if duplicates:
        print(f"ERROR: duplicate IDs: {sorted(set(duplicates))}", file=sys.stderr)
        return 1

    failures: list[str] = []
    if len(cases) < 55:
        failures.append(f"need ≥55 cases, found {len(cases)}")
    if missing:
        failures.append(f"missing supported languages: {sorted(missing)}")
    for case in cases:
        if not case.relevant_refs:
            failures.append(f"{case.id}: no relevant_refs")

    if failures:
        for msg in failures:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1

    print("OK — golden set is valid.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieval-evaluation harness for scripture search (BITB-051)."
    )
    sub = parser.add_subparsers(dest="command")

    val = sub.add_parser("--validate", help="Validate golden set (no DB required).")
    val.add_argument("--path", help="Override golden-set JSON path.")

    # Top-level --validate alias (no sub-command required)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate golden set (no DB required).",
    )
    parser.add_argument("--path", help="Override golden-set JSON path.")

    args = parser.parse_args()

    if args.validate or args.command == "--validate":
        return _cmd_validate(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
