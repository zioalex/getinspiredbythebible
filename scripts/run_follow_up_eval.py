#!/usr/bin/env python3
"""CLI for the follow-up chip golden set (BITB-178).

Sends every curated case in api/golden_set/test_cases/follow_ups.yaml to a
running backend, checks the suggested follow-up chips and prints a report.

Exit codes: 0 all cases pass, 1 at least one failure, 2 backend unreachable.

Examples
--------
    python scripts/run_follow_up_eval.py --checklist
    python scripts/run_follow_up_eval.py --language it,de --scenario expected
    python scripts/run_follow_up_eval.py --base-url http://localhost:8001 --mode json --out r.json
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent.parent / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

# The evaluators import utils.verse_parser, whose package __init__ builds the app
# Settings (which insists on a DATABASE_URL). This runner never touches a database,
# so supply an inert placeholder when the caller has none configured.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://eval:eval@localhost:5432/eval"  # pragma: allowlist secret
)

import httpx  # noqa: E402
from golden_set.follow_up_runner import (  # noqa: E402
    SCENARIOS,
    BackendUnreachableError,
    FollowUpCaseResult,
    language_of,
    render_checklist,
    render_json,
    render_text_report,
    run_case,
    scenario_of,
)
from golden_set.loader import filter_by_category, load_test_cases  # noqa: E402
from golden_set.models import GoldenSetCase  # noqa: E402


def _split(values: list[str] | None) -> set[str]:
    return {part.strip() for raw in values or [] for part in raw.split(",") if part.strip()}


def select_cases(
    cases: list[GoldenSetCase],
    languages: set[str],
    scenario: str | None,
    case_ids: set[str],
) -> list[GoldenSetCase]:
    """Apply the --language / --scenario / --case filters."""
    selected = cases
    if languages:
        selected = [c for c in selected if language_of(c) in languages]
    if scenario:
        selected = [c for c in selected if scenario_of(c) == scenario]
    if case_ids:
        selected = [c for c in selected if c.id in case_ids]
    return selected


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Follow-up chip golden-set runner (BITB-178).")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--mode", choices=["stream", "json"], default="stream")
    parser.add_argument("--language", action="append", help="Language code(s); repeat or comma.")
    parser.add_argument("--scenario", choices=list(SCENARIOS))
    parser.add_argument("--case", action="append", help="Case id(s); repeat or comma.")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between cases.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-request timeout (s).")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--out", help="Write JSON results to this path.")
    parser.add_argument("--checklist", action="store_true", help="Print markdown checklist.")
    return parser


def _run_all(args: argparse.Namespace, cases: list[GoldenSetCase]) -> list[FollowUpCaseResult]:
    results: list[FollowUpCaseResult] = []
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        for index, case in enumerate(cases):
            if index and args.delay > 0:
                time.sleep(args.delay)
            results.append(run_case(client, case, mode=args.mode))
    return results


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cases = select_cases(
        filter_by_category(load_test_cases(), "follow_ups"),
        _split(args.language),
        args.scenario,
        _split(args.case),
    )
    if not cases:
        print("No follow-up cases match the given filters.", file=sys.stderr)
        return 1
    if args.checklist:
        print(render_checklist(cases))
        return 0
    try:
        results = _run_all(args, cases)
    except BackendUnreachableError as exc:
        print(f"Cannot reach backend at {args.base_url}: {exc}", file=sys.stderr)
        print("Start it with `make docker-up` or pass --base-url.", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(render_json(results), encoding="utf-8")
    print(render_json(results) if args.json else render_text_report(results))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
