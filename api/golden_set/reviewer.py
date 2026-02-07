"""Interactive CLI for human review of golden set results.

Loads a completed evaluation run and presents each case for human scoring.
Supports incremental saves, skip, and resume.
"""

import sys

from golden_set.loader import load_test_cases
from golden_set.models import CaseResult, EvalRun, HumanScore
from golden_set.runner import list_runs, load_run, save_run


def _prompt_score(label: str, default: int = 3) -> int:
    """Prompt the user for a score between 1 and 5."""
    while True:
        raw = input(f"  {label} (1-5) [{default}]: ").strip()
        if raw == "":
            return default
        try:
            val = int(raw)
            if 1 <= val <= 5:
                return val
            print("    Score must be between 1 and 5.")
        except ValueError:
            print("    Please enter a number.")


def _display_case(
    index: int,
    total: int,
    case_id: str,
    result: CaseResult,
    reference_response: str | None,
    reviewed_count: int,
    skipped_count: int,
) -> None:
    """Display a single case for review."""
    score = result.automated_score

    print(f"\n{'=' * 70}")
    print(f"  Case [{index + 1}/{total}]  {case_id}")
    print(f"  Reviewed: {reviewed_count} | Skipped: {skipped_count}")
    print(f"{'=' * 70}")

    # Auto score
    status = "PASS" if score.passed else "FAIL"
    print(f"\n  AUTO: {status} ({score.passed_checks}/{score.total_checks} checks)")
    if score.failed_checks:
        for check in score.failed_checks:
            detail = score.details.get(check, "")
            print(f"    x {check}: {detail}")

    # Input
    print(f"\n{'─' * 70}")
    print("  INPUT:")
    print(f"    {result.input_message}")

    # Response
    print(f"\n{'─' * 70}")
    print("  RESPONSE:")
    for line in result.actual_response.split("\n"):
        print(f"    {line}")

    # Reference (if available)
    if reference_response:
        print(f"\n{'─' * 70}")
        print("  REFERENCE:")
        for line in reference_response.strip().split("\n"):
            print(f"    {line}")

    # Provider info
    print(f"\n  Provider: {result.provider} | Model: {result.model}")
    if result.response_time_ms > 0:
        print(f"  Response time: {result.response_time_ms}ms")


def review_run(run: EvalRun, resume: bool = True) -> EvalRun:
    """Interactively review all cases in an evaluation run.

    Args:
        run: The evaluation run to review.
        resume: If True, skip cases that already have human scores.

    Returns:
        The updated EvalRun with human scores added.
    """
    # Build a lookup of reference responses from YAML
    all_cases = load_test_cases()
    reference_map = {c.id: c.reference_response for c in all_cases}

    total = len(run.results)
    reviewed_count = sum(1 for r in run.results if r.human_score is not None)
    skipped_count = 0

    print(f"\n{'=' * 70}")
    print("  Golden Set Review")
    print(f"  Run: {run.run_id} | {run.provider}/{run.model} | {run.mode}")
    print(f"  Cases: {total} | Already reviewed: {reviewed_count}")
    print(f"{'=' * 70}")
    print("  Commands: [Enter] score with defaults | [s]kip | [q]uit")

    for i, result in enumerate(run.results):
        # Skip already-reviewed cases in resume mode
        if resume and result.human_score is not None:
            continue

        _display_case(
            index=i,
            total=total,
            case_id=result.case_id,
            result=result,
            reference_response=reference_map.get(result.case_id),
            reviewed_count=reviewed_count,
            skipped_count=skipped_count,
        )

        # Prompt for action
        print(f"\n{'─' * 70}")
        action = input("  [a]pprove / [f]ail / [s]kip / [q]uit: ").strip().lower()

        if action == "q":
            print("\n  Saving progress and exiting...")
            break

        if action == "s":
            skipped_count += 1
            continue

        # Score
        print("\n  Score (1-5, press Enter for default [3]):")
        relevance = _prompt_score("Relevance")
        scripture = _prompt_score("Scripture Accuracy")
        tone = _prompt_score("Tone Quality")
        source = _prompt_score("Source Attribution")
        overall = _prompt_score("Overall")
        notes = input("  Notes (optional): ").strip()

        result.human_score = HumanScore(
            relevance=relevance,
            scripture_accuracy=scripture,
            tone_quality=tone,
            source_attribution=source,
            overall=overall,
            notes=notes,
        )
        reviewed_count += 1

    # Print summary
    scored = [r for r in run.results if r.human_score is not None]
    if scored:
        avg_overall = sum(r.human_score.overall for r in scored) / len(scored)
        print(f"\n{'=' * 70}")
        print("  Review Summary")
        print(f"  Reviewed: {len(scored)}/{total}")
        print(f"  Average overall score: {avg_overall:.1f}/5")
        print(f"{'=' * 70}\n")

    return run


def select_run() -> EvalRun | None:
    """Let the user select which run to review."""
    runs = list_runs()
    if not runs:
        print("No saved runs found. Run 'make golden-test-live' first.")
        return None

    if len(runs) == 1:
        return load_run(runs[0])

    print("\nAvailable runs:")
    for i, path in enumerate(runs):
        run = load_run(path)
        reviewed = sum(1 for r in run.results if r.human_score is not None)
        print(
            f"  [{i + 1}] {run.run_id} | {run.provider}/{run.model} | "
            f"{run.mode} | {len(run.results)} cases | {reviewed} reviewed"
        )

    while True:
        raw = input(f"\nSelect run (1-{len(runs)}) [1]: ").strip()
        if raw == "":
            return load_run(runs[0])
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(runs):
                return load_run(runs[idx])
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(runs)}.")

    return None


def main() -> None:
    """Entry point for the review CLI."""
    run = select_run()
    if run is None:
        sys.exit(1)

    updated_run = review_run(run)

    # Save the updated run
    path = save_run(updated_run)
    print(f"Results saved to: {path}")


if __name__ == "__main__":
    main()
