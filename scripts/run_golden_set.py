#!/usr/bin/env python3
"""CLI for the golden set runner (BITB-178).

Usage
-----
--mock               No API: every case gets a placeholder answer (pipeline smoke test).
--base-url URL       Live mode: send the cases to URL/api/v1/chat. Use a local or dev API with
                     Turnstile off; a 403 is reported as "blocked", not as a model failure.
--category NAME      Only cases of this category (e.g. interpretation).
--tags A,B           Only cases with any of these tags (e.g. pushback-user-right).
--ids ID,ID          Only these case ids (e.g. interp-001,interp-030).
--output PATH        Where to save the run JSON (default: api/golden_set/results/<run_id>.json).
--delay SECONDS      Pause between live requests (default 0).
--timeout SECONDS    Per-request timeout (default 120).
--fail-under RATE    Exit 1 when the pass rate (0-1) is below RATE (default 0: never fail).

Environment
-----------
GOLDEN_SET_PROBE_SECRET   When set (live mode), sent as the X-Monitor-Probe-Secret header so a
                          production run passes Turnstile / rate limits. Read from the
                          environment only (never argv); never printed or saved.

Exit codes
----------
0  ok                                  2  no case matches the filters
1  pass rate below --fail-under        3  nothing was scorable (every case blocked or errored)

Example
-------
    python scripts/run_golden_set.py --mock --category interpretation
    python scripts/run_golden_set.py --base-url http://localhost:8000 --category interpretation \\
        --fail-under 0.8
"""

import argparse
import asyncio
import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent.parent / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from golden_set.loader import (  # noqa: E402
    filter_by_category,
    filter_by_tags,
    load_test_cases,
)
from golden_set.runner import (  # noqa: E402
    has_scorable_answer,
    print_summary,
    probe_headers_from_env,
    run_live,
    run_mock,
    save_run,
    summarize,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the golden set (mock or against a live API).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mock", action="store_true", help="No API; placeholder answers.")
    mode.add_argument("--base-url", help="Live mode: API root, e.g. http://localhost:8000")
    parser.add_argument("--category", help="Only this category.")
    parser.add_argument("--tags", help="Comma-separated tags; keep cases with any of them.")
    parser.add_argument("--ids", help="Comma-separated case ids.")
    parser.add_argument("--output", type=Path, help="Path for the saved run JSON.")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds between requests.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-request timeout (s).")
    parser.add_argument(
        "--fail-under", type=float, default=0.0, help="Exit 1 below this pass rate (0-1)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    cases = load_test_cases()
    if args.category:
        cases = filter_by_category(cases, args.category)
    if args.tags:
        cases = filter_by_tags(cases, [t.strip() for t in args.tags.split(",") if t.strip()])
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",") if i.strip()}
        cases = [c for c in cases if c.id in wanted]
    if not cases:
        print("No golden set cases match the given filters.", file=sys.stderr)
        return 2

    if args.mock:
        run = run_mock(cases)
    else:
        run = asyncio.run(
            run_live(
                cases,
                args.base_url,
                timeout=args.timeout,
                delay=args.delay,
                headers=probe_headers_from_env(),
            )
        )

    path = save_run(run, args.output)
    print_summary(run)
    print(f"Saved: {path}")

    if not has_scorable_answer(run):
        print("No case produced a scorable answer (all blocked or errored).", file=sys.stderr)
        return 3

    rate = summarize(run)["pass_rate"]
    if rate < args.fail_under:
        print(f"Pass rate {rate:.0%} is below --fail-under {args.fail_under:.0%}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
