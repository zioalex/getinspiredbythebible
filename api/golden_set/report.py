"""Markdown report generation for golden set evaluation runs.

Generates single-run summaries and multi-run comparison reports.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from golden_set.models import EvalRun


def generate_report(run: EvalRun) -> str:
    """Generate a markdown report for a single evaluation run.

    Args:
        run: The evaluation run to report on.

    Returns:
        Markdown-formatted report string.
    """
    total = len(run.results)
    passed = sum(1 for r in run.results if r.automated_score.passed)
    failed = total - passed

    scored = [r for r in run.results if r.human_score is not None]
    avg_overall = sum(r.human_score.overall for r in scored) / len(scored) if scored else 0

    timed = [r for r in run.results if r.response_time_ms > 0]
    avg_time = sum(r.response_time_ms for r in timed) / len(timed) if timed else 0

    lines: list[str] = []
    lines.append(f"# Golden Set Report: {run.run_id}")
    lines.append("")
    lines.append(
        f"**Provider:** {run.provider} | **Model:** {run.model} | "
        f"**Mode:** {run.mode} | **Date:** {run.timestamp.strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total Cases | {total} |")
    if total > 0:
        lines.append(f"| Auto-Pass | {passed}/{total} ({passed / total * 100:.1f}%) |")
        lines.append(f"| Auto-Fail | {failed} |")
    else:
        lines.append("| Auto-Pass | 0 |")
        lines.append("| Auto-Fail | 0 |")
    lines.append(f"| Human Reviewed | {len(scored)} |")
    if scored:
        lines.append(f"| Avg Human Overall | {avg_overall:.1f}/5 |")
    if timed:
        lines.append(f"| Avg Response Time | {avg_time:.0f}ms |")
    lines.append("")

    # By category
    categories: dict[str, list] = defaultdict(list)
    for r in run.results:
        cat = r.case_id.rsplit("-", 1)[0] if "-" in r.case_id else "unknown"
        categories[cat].append(r)

    lines.append("## By Category")
    lines.append("")
    lines.append("| Category | Cases | Auto-Pass | Human Avg |")
    lines.append("|---|---|---|---|")
    for cat in sorted(categories):
        cat_results = categories[cat]
        cat_total = len(cat_results)
        cat_passed = sum(1 for r in cat_results if r.automated_score.passed)
        cat_scored = [r for r in cat_results if r.human_score is not None]
        cat_avg = (
            f"{sum(r.human_score.overall for r in cat_scored) / len(cat_scored):.1f}"
            if cat_scored
            else "-"
        )
        rate = f"{cat_passed / cat_total * 100:.0f}%" if cat_total > 0 else "0%"
        lines.append(f"| {cat} | {cat_total} | {cat_passed}/{cat_total} ({rate}) | {cat_avg} |")
    lines.append("")

    # Failed cases
    failed_results = [r for r in run.results if not r.automated_score.passed]
    if failed_results:
        lines.append("## Failed Cases")
        lines.append("")
        for r in failed_results:
            lines.append(f"### {r.case_id}")
            lines.append("")
            lines.append(f"**Input:** {r.input_message}")
            lines.append("")
            lines.append(f"**Failed checks:** {', '.join(r.automated_score.failed_checks)}")
            lines.append("")
            for check in r.automated_score.failed_checks:
                detail = r.automated_score.details.get(check, "")
                if detail:
                    lines.append(f"- **{check}:** {detail}")
            lines.append("")

    return "\n".join(lines)


def _get_category(case_id: str) -> str:
    """Extract category from a case ID (e.g., 'enc-001' -> 'enc')."""
    return case_id.rsplit("-", 1)[0] if "-" in case_id else "unknown"


def _run_auto_pass_rate(run: EvalRun) -> str:
    """Get auto-pass rate string for a run."""
    total = len(run.results)
    if total > 0:
        passed = sum(1 for res in run.results if res.automated_score.passed)
        return f"{passed / total * 100:.1f}%"
    return "-"


def _run_human_score(run: EvalRun) -> str:
    """Get average human overall score string for a run."""
    scored = [res for res in run.results if res.human_score is not None]
    if scored:
        avg = sum(res.human_score.overall for res in scored) / len(scored)
        return f"{avg:.1f}/5"
    return "-"


def _run_avg_time(run: EvalRun) -> str:
    """Get average response time string for a run."""
    timed = [res for res in run.results if res.response_time_ms > 0]
    if timed:
        avg_t = sum(res.response_time_ms for res in timed) / len(timed)
        return f"{avg_t:.0f}ms"
    return "-"


def _category_stats(run: EvalRun, cat: str) -> tuple[str, str]:
    """Get auto-pass and human avg strings for a category within a run."""
    cat_results = [res for res in run.results if _get_category(res.case_id) == cat]
    if cat_results:
        p = sum(1 for res in cat_results if res.automated_score.passed)
        pass_str = f"{p}/{len(cat_results)}"
    else:
        pass_str = "-"

    scored = [res for res in cat_results if res.human_score is not None]
    if scored:
        avg = sum(res.human_score.overall for res in scored) / len(scored)
        human_str = f"{avg:.1f}"
    else:
        human_str = "-"

    return pass_str, human_str


def generate_comparison(runs: list[EvalRun]) -> str:
    """Generate a comparison report across multiple evaluation runs.

    Args:
        runs: List of evaluation runs to compare.

    Returns:
        Markdown-formatted comparison report.
    """
    if not runs:
        return "# Golden Set Comparison\n\nNo runs to compare.\n"

    lines: list[str] = []
    lines.append("# Golden Set Comparison")
    lines.append("")

    labels = [f"{r.provider}/{r.model}" for r in runs]
    header = "| Metric | " + " | ".join(labels) + " |"
    sep = "|---|" + "|".join(["---"] * len(runs)) + "|"
    lines.append(header)
    lines.append(sep)

    lines.append("| Auto-Pass Rate | " + " | ".join(_run_auto_pass_rate(r) for r in runs) + " |")
    lines.append("| Total Cases | " + " | ".join(str(len(r.results)) for r in runs) + " |")
    lines.append("| Avg Human Score | " + " | ".join(_run_human_score(r) for r in runs) + " |")
    lines.append("| Avg Response Time | " + " | ".join(_run_avg_time(r) for r in runs) + " |")
    lines.append("")

    # Per-category comparison
    all_categories: set[str] = set()
    for r in runs:
        for res in r.results:
            all_categories.add(_get_category(res.case_id))

    lines.append("## By Category")
    lines.append("")

    for cat in sorted(all_categories):
        lines.append(f"### {cat}")
        lines.append("")
        lines.append(header)
        lines.append(sep)

        stats = [_category_stats(r, cat) for r in runs]
        lines.append("| Auto-Pass | " + " | ".join(s[0] for s in stats) + " |")
        lines.append("| Human Avg | " + " | ".join(s[1] for s in stats) + " |")
        lines.append("")

    # Run metadata
    lines.append("## Run Details")
    lines.append("")
    lines.append("| Field | " + " | ".join(labels) + " |")
    lines.append(sep)
    lines.append("| Run ID | " + " | ".join(r.run_id for r in runs) + " |")
    lines.append("| Mode | " + " | ".join(r.mode for r in runs) + " |")
    lines.append(
        "| Date | " + " | ".join(r.timestamp.strftime("%Y-%m-%d %H:%M") for r in runs) + " |"
    )
    lines.append("")

    return "\n".join(lines)


def save_report(content: str, file_path: Path) -> Path:
    """Save a report to a markdown file.

    Args:
        content: Markdown report content.
        file_path: Path to save the report.

    Returns:
        Path to the saved file.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return file_path
