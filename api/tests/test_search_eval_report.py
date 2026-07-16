"""Tests for retrieval-eval report aggregation/rendering (BITB-051 P3).

Pure functions over synthetic ``QueryResult`` lists — no database, no
network — runs in the standard (blocking) backend-tests CI job.
"""

from __future__ import annotations

import json

from search_eval.report import (
    aggregate,
    aggregate_by_language,
    format_language_breakdown,
    format_report,
    format_table,
    to_json,
)
from search_eval.runner import QueryResult, RunResult


def _qr(**overrides) -> QueryResult:
    defaults = dict(
        case_id="c1",
        language="en",
        config="baseline_semantic",
        retrieved=["John 3:16"],
        precision_at_5=1.0,
        recall_at_10=1.0,
        mrr=1.0,
        false_positives_at_5=0,
    )
    defaults.update(overrides)
    return QueryResult(**defaults)


class TestAggregate:
    def test_means_computed_per_config(self):
        results = [
            _qr(config="a", precision_at_5=1.0, recall_at_10=1.0, mrr=1.0),
            _qr(config="a", precision_at_5=0.0, recall_at_10=0.0, mrr=0.0),
        ]
        aggs = aggregate(results)
        assert len(aggs) == 1
        assert aggs[0].config == "a"
        assert aggs[0].n_cases == 2
        assert aggs[0].mean_precision_at_5 == 0.5
        assert aggs[0].mean_recall_at_10 == 0.5
        assert aggs[0].mean_mrr == 0.5

    def test_preserves_first_seen_config_order(self):
        results = [_qr(config="b"), _qr(config="a"), _qr(config="b")]
        aggs = aggregate(results)
        assert [a.config for a in aggs] == ["b", "a"]

    def test_counts_errors(self):
        results = [_qr(config="a", error=None), _qr(config="a", error="boom")]
        aggs = aggregate(results)
        assert aggs[0].n_errors == 1
        assert aggs[0].n_cases == 2

    def test_sums_false_positives(self):
        results = [
            _qr(config="a", false_positives_at_5=1),
            _qr(config="a", false_positives_at_5=2),
        ]
        assert aggregate(results)[0].total_false_positives_at_5 == 3

    def test_expansion_latency_averaged_only_over_present_values(self):
        results = [
            _qr(config="a", expansion_latency_ms=100.0),
            _qr(config="a", expansion_latency_ms=200.0),
            _qr(config="a", expansion_latency_ms=None),
        ]
        assert aggregate(results)[0].mean_expansion_latency_ms == 150.0

    def test_no_latency_values_is_none(self):
        results = [_qr(config="a", expansion_latency_ms=None)]
        assert aggregate(results)[0].mean_expansion_latency_ms is None

    def test_empty_results_is_empty(self):
        assert aggregate([]) == []


class TestAggregateByLanguage:
    def test_groups_by_language(self):
        results = [
            _qr(language="en", config="a", precision_at_5=1.0),
            _qr(language="it", config="a", precision_at_5=0.0),
        ]
        by_lang = aggregate_by_language(results)
        assert set(by_lang) == {"en", "it"}
        assert by_lang["en"][0].mean_precision_at_5 == 1.0
        assert by_lang["it"][0].mean_precision_at_5 == 0.0


class TestFormatTable:
    def test_includes_every_config_row(self):
        aggs = aggregate([_qr(config="a"), _qr(config="b")])
        table = format_table(aggs)
        assert "a" in table
        assert "b" in table
        assert "P@5" in table and "R@10" in table and "MRR" in table and "FP@5" in table


class TestFormatLanguageBreakdown:
    def test_includes_every_language(self):
        by_lang = aggregate_by_language([_qr(language="en"), _qr(language="it")])
        breakdown = format_language_breakdown(by_lang)
        assert "en" in breakdown
        assert "it" in breakdown

    def test_empty_is_empty_string(self):
        assert format_language_breakdown({}) == ""


class TestFormatReport:
    def test_healthy_guard_line(self):
        run = RunResult(
            configs=["a"], query_results=[_qr(config="a", false_positives_at_5=0)]
        )
        report = format_report(run)
        assert "healthy (0)" in report

    def test_unhealthy_guard_line_flags_count(self):
        run = RunResult(
            configs=["a"], query_results=[_qr(config="a", false_positives_at_5=2)]
        )
        report = format_report(run)
        assert "2 false positive" in report

    def test_error_summary_present_when_errors_exist(self):
        run = RunResult(
            configs=["a"],
            query_results=[_qr(config="a", error="boom"), _qr(config="a", error=None)],
        )
        report = format_report(run)
        assert "1 query failed" in report

    def test_expansion_latency_line_only_when_present(self):
        with_latency = RunResult(
            configs=["a"], query_results=[_qr(config="a", expansion_latency_ms=250.0)]
        )
        assert "Expansion latency" in format_report(with_latency)

        without_latency = RunResult(configs=["a"], query_results=[_qr(config="a")])
        assert "Expansion latency" not in format_report(without_latency)


class TestToJson:
    def test_round_trips_valid_json_with_expected_keys(self):
        run = RunResult(configs=["a"], query_results=[_qr(config="a")])
        payload = json.loads(to_json(run))
        assert payload["configs"] == ["a"]
        assert len(payload["aggregates"]) == 1
        assert "en" in payload["by_language"]
        assert len(payload["query_results"]) == 1
        assert payload["query_results"][0]["case_id"] == "c1"
