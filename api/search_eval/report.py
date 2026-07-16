"""Aggregation and rendering for retrieval-evaluation runs (BITB-051 P3).

Pure post-processing over ``QueryResult``/``RunResult`` — no DB, no network,
so this module is trivially unit-testable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .runner import QueryResult, RunResult


@dataclass
class ConfigAggregate:
    """Per-config summary metrics, averaged across a set of queries."""

    config: str
    n_cases: int
    n_errors: int
    mean_precision_at_5: float
    mean_recall_at_10: float
    mean_mrr: float
    total_false_positives_at_5: int
    mean_expansion_latency_ms: float | None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(results: list[QueryResult]) -> list[ConfigAggregate]:
    """Aggregate per-query results into one row per config, first-seen order."""
    order: list[str] = []
    by_config: dict[str, list[QueryResult]] = {}
    for result in results:
        if result.config not in by_config:
            by_config[result.config] = []
            order.append(result.config)
        by_config[result.config].append(result)

    aggregates = []
    for name in order:
        rows = by_config[name]
        latencies = [
            r.expansion_latency_ms for r in rows if r.expansion_latency_ms is not None
        ]
        aggregates.append(
            ConfigAggregate(
                config=name,
                n_cases=len(rows),
                n_errors=sum(1 for r in rows if r.error is not None),
                mean_precision_at_5=_mean([r.precision_at_5 for r in rows]),
                mean_recall_at_10=_mean([r.recall_at_10 for r in rows]),
                mean_mrr=_mean([r.mrr for r in rows]),
                total_false_positives_at_5=sum(r.false_positives_at_5 for r in rows),
                mean_expansion_latency_ms=_mean(latencies) if latencies else None,
            )
        )
    return aggregates


def aggregate_by_language(
    results: list[QueryResult],
) -> dict[str, list[ConfigAggregate]]:
    """Aggregate results grouped by language, each with one row per config."""
    languages: list[str] = []
    by_lang: dict[str, list[QueryResult]] = {}
    for result in results:
        if result.language not in by_lang:
            by_lang[result.language] = []
            languages.append(result.language)
        by_lang[result.language].append(result)
    return {lang: aggregate(by_lang[lang]) for lang in languages}


def format_table(aggregates: list[ConfigAggregate]) -> str:
    """Render the configs x P@5/R@10/MRR/FP@5 comparison table."""
    header = f"{'Config':<20} {'P@5':>7} {'R@10':>7} {'MRR':>7} {'FP@5':>6} {'n':>4}"
    lines = [header, "-" * len(header)]
    for agg in aggregates:
        lines.append(
            f"{agg.config:<20} {agg.mean_precision_at_5:>7.2f} {agg.mean_recall_at_10:>7.2f} "
            f"{agg.mean_mrr:>7.2f} {agg.total_false_positives_at_5:>6} {agg.n_cases:>4}"
        )
    return "\n".join(lines)


def format_language_breakdown(by_lang: dict[str, list[ConfigAggregate]]) -> str:
    """Render a per-language P@5/R@10/MRR breakdown, one row per language."""
    if not by_lang:
        return ""
    configs = [agg.config for agg in next(iter(by_lang.values()))]
    lines = [
        "Per-language (P@5 / R@10 / MRR):",
        f"{'lang':<6} " + " ".join(f"{c:<22}" for c in configs),
    ]
    for lang, aggregates in by_lang.items():
        cells = " ".join(
            f"{agg.mean_precision_at_5:.2f}/{agg.mean_recall_at_10:.2f}/{agg.mean_mrr:.2f}".ljust(
                22
            )
            for agg in aggregates
        )
        lines.append(f"{lang:<6} {cells}")
    return "\n".join(lines)


def format_report(run: RunResult) -> str:
    """Render the full human-readable report: table + per-language + guards."""
    aggregates = aggregate(run.query_results)
    by_lang = aggregate_by_language(run.query_results)
    total_fp = sum(agg.total_false_positives_at_5 for agg in aggregates)
    total_errors = sum(agg.n_errors for agg in aggregates)

    sections = [format_table(aggregates), "", format_language_breakdown(by_lang)]

    latency_aggs = [
        agg for agg in aggregates if agg.mean_expansion_latency_ms is not None
    ]
    if latency_aggs:
        expansion_line = ", ".join(
            f"{agg.config}: {agg.mean_expansion_latency_ms:.0f} ms/query"
            for agg in latency_aggs
        )
        sections.append(f"\nExpansion latency (mean): {expansion_line}")

    guard_status = (
        "healthy (0)"
        if total_fp == 0
        else f"{total_fp} false positive(s) — investigate"
    )
    sections.append(f"False-positive guard: {guard_status}")

    if total_errors:
        noun = "query" if total_errors == 1 else "queries"
        sections.append(
            f"{total_errors} {noun} failed (fail-open, scored 0) — check logs"
        )

    return "\n".join(sections)


def to_json(run: RunResult) -> str:
    """Render the run as machine-readable JSON (for --json)."""
    payload = {
        "configs": run.configs,
        "aggregates": [asdict(agg) for agg in aggregate(run.query_results)],
        "by_language": {
            lang: [asdict(agg) for agg in aggs]
            for lang, aggs in aggregate_by_language(run.query_results).items()
        },
        "query_results": [asdict(r) for r in run.query_results],
    }
    return json.dumps(payload, indent=2)
