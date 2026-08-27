#!/usr/bin/env python3
"""CLI for the retrieval-evaluation harness (BITB-051).

Usage
-----
--validate            Validate the golden-set file (no DB/LLM required; safe for CI).
                       Exits 0 on success, 1 on validation failure.
--run                 Run the golden set through the real search pipeline.
                       Requires DATABASE_URL + embedding (and, for expansion
                       configs, LLM) provider credentials. Exits non-zero with
                       a clear message (no traceback) if a connection/provider
                       cannot be reached.
--config NAMES        Comma-separated config names to run (default:
                       baseline_semantic,expansion_semantic). See
                       search_eval.runner.EVAL_CONFIGS for the full list.
--language CODE        Restrict to one golden-set language (e.g. it, de).
--smoke                Run --run against only the first 3 cases — a fast
                       plumbing check, not a real measurement.
--json                 Print machine-readable JSON instead of the text report.
--probe-embedding      Diagnose the configured embedding provider directly
                       (BITB-107): no database required. Prints resolved
                       provider config (never secrets) and makes one real
                       embed() call through the app's actual provider stack.
                       On failure, prints the full exception chain to stderr
                       so a CI console log carries a real diagnosis instead
                       of the openai SDK's uninformative "Connection error."

P4 (full-corpus, nightly/manual CI on Azure) is tracked separately —
see docs/SEARCH_EVAL_HOWTO.md.

Example
-------
    python scripts/run_search_eval.py --validate
    python scripts/run_search_eval.py --run --smoke
    DATABASE_URL=... python scripts/run_search_eval.py --run --config hybrid,hybrid_expansion --language it
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


def _cmd_probe_embedding(args: argparse.Namespace) -> int:
    """Diagnose the configured embedding provider with one real embed() call.

    No database required. Builds the exact cache+resilience-wrapped provider
    stack the app uses (providers.factory.create_embedding_provider) rather
    than a raw client, so a pass/fail here reproduces exactly what a real
    search-eval/chat request would hit (BITB-107).
    """
    import asyncio
    import os
    import traceback
    from urllib.parse import urlparse

    from config import settings
    from providers.factory import create_embedding_provider

    is_azure = settings.embedding_provider == "azure_openai"
    endpoint = settings.azure_openai_endpoint if is_azure else settings.ollama_host
    parsed = urlparse(endpoint or "")
    # Read the raw env var (not settings.azure_openai_api_key, already
    # stripped by config.py's field_validator) so this diagnoses exactly the
    # whitespace-in-secret failure mode this probe exists to catch.
    raw_key = os.environ.get("AZURE_OPENAI_API_KEY", "") if is_azure else ""

    print("Embedding provider probe (BITB-107)")
    print(f"  embedding_provider:                 {settings.embedding_provider}")
    print(f"  endpoint (scheme+host only):        {parsed.scheme}://{parsed.hostname or ''}")
    print(f"  azure_embedding_deployment:         {settings.azure_embedding_deployment}")
    print(f"  embedding_dimensions:               {settings.embedding_dimensions}")
    print(f"  embedding_request_timeout:          {settings.embedding_request_timeout}")
    print(f"  api key length:                     {len(raw_key) if is_azure else 'n/a'}")
    has_ws = raw_key != raw_key.strip() if is_azure else "n/a"
    print(f"  api key has_surrounding_whitespace: {has_ws}")

    try:
        provider = create_embedding_provider(settings)
        response = asyncio.run(provider.embed("probe"))
    except Exception:
        print("FAILED: embed() raised — full exception chain follows.", file=sys.stderr)
        traceback.print_exception(*sys.exc_info(), file=sys.stderr)
        return 1

    actual = len(response.embedding)
    matches = actual == settings.embedding_dimensions
    print(
        f"OK — embed() returned a {actual}-dimensional vector "
        f"(matches settings.embedding_dimensions: {matches})."
    )
    return 0 if matches else 1


def _cmd_run(args: argparse.Namespace) -> int:
    """Run the golden set through the real search pipeline and print a report."""
    import asyncio

    from search_eval.loader import load_golden_set
    from search_eval.report import format_report, to_json
    from search_eval.runner import DEFAULT_AB, EVAL_CONFIGS, run_eval

    if args.config:
        config_names = [name.strip() for name in args.config.split(",") if name.strip()]
        unknown = [name for name in config_names if name not in EVAL_CONFIGS]
        if unknown:
            print(
                f"ERROR: unknown config(s) {unknown}; choose from {sorted(EVAL_CONFIGS)}",
                file=sys.stderr,
            )
            return 1
    else:
        config_names = list(DEFAULT_AB)

    try:
        cases = load_golden_set(
            Path(args.path) if args.path else None, language=args.language
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: failed to load golden set — {exc}", file=sys.stderr)
        return 1

    if not cases:
        print("ERROR: no golden-set cases matched the given filters.", file=sys.stderr)
        return 1

    if args.smoke:
        cases = cases[:3]

    try:
        run_result = asyncio.run(run_eval(cases, config_names))
    except Exception as exc:  # noqa: BLE001 - surface a clean message, not a traceback
        print(f"ERROR: search-eval run failed — {exc}", file=sys.stderr)
        print(
            "Hint: --run needs DATABASE_URL and embedding-provider credentials "
            "(and an LLM provider for *_expansion configs). See docs/SEARCH_EVAL_HOWTO.md.",
            file=sys.stderr,
        )
        return 1

    print(to_json(run_result) if args.json else format_report(run_result))

    # run_eval() is fail-open per query (a few bad cases shouldn't abort a
    # partial report), but if EVERY case errored that's not partial
    # degradation — it means the DB/provider was never reachable at all, and
    # the "Done when" contract promises a non-zero exit with no traceback.
    total = len(run_result.query_results)
    failed = sum(1 for r in run_result.query_results if r.error is not None)
    if total and failed == total:
        print(
            "ERROR: every query failed — DB/provider likely unreachable. "
            "See docs/SEARCH_EVAL_HOWTO.md for required env vars.",
            file=sys.stderr,
        )
        return 1

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
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the golden set through the real search pipeline (needs DB + provider creds).",
    )
    parser.add_argument(
        "--config",
        help="Comma-separated eval config names (default: baseline_semantic,expansion_semantic).",
    )
    parser.add_argument(
        "--language", help="Restrict --run to one golden-set language code."
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="With --run, use only the first 3 cases — a fast plumbing check.",
    )
    parser.add_argument(
        "--json", action="store_true", help="With --run, print JSON output."
    )
    parser.add_argument(
        "--probe-embedding",
        action="store_true",
        help="Diagnose the configured embedding provider with one embed() call (no DB required).",
    )

    args = parser.parse_args()

    if args.validate or args.command == "--validate":
        return _cmd_validate(args)

    if args.probe_embedding:
        return _cmd_probe_embedding(args)

    if args.run:
        return _cmd_run(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
