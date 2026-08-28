"""Tests for scripts/check_verse_topic_coverage.py (BITB-105).

Pure functions over synthetic counts -- zero DB dependency. These tests ARE
the negative rehearsal BITB-105's Verification section requires: they prove
the empty/out-of-band classification and the resulting warning annotation
actually fire, not just that the code exists. For a live rehearsal against a
real database, see the "Negative rehearsal" section of
docs/HOW-TO-POPULATE-VERSE-TOPICS.md.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "check_verse_topic_coverage.py"


@pytest.fixture(scope="module")
def coverage_module():
    spec = importlib.util.spec_from_file_location("check_verse_topic_coverage", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestEvaluateCoverage:
    def test_zero_tagged_verses_alarms(self, coverage_module):
        """The negative rehearsal: the literal BITB-105 production condition
        (verse_topics empty for a translation with verses loaded) must alarm."""
        result = coverage_module.evaluate_coverage("kjv", "en", 31_100, 0)
        assert result.status == coverage_module.STATUS_EMPTY
        assert result.alarm is True

    def test_empty_alarm_message_names_the_translation_and_counts(self, coverage_module):
        result = coverage_module.evaluate_coverage("kjv", "en", 31_100, 0)
        assert "kjv" in result.message
        assert "31,100" in result.message

    def test_kjv_measured_coverage_is_in_band(self, coverage_module):
        # BITB-044 measured ~18.3% for KJV.
        result = coverage_module.evaluate_coverage("kjv", "en", 31_100, 5_691)
        assert result.status == coverage_module.STATUS_OK
        assert result.alarm is False

    def test_luther_measured_coverage_is_in_band(self, coverage_module):
        # BITB-044 measured ~12.3% for Luther 1912.
        result = coverage_module.evaluate_coverage("luther1912", "de", 31_102, 3_825)
        assert result.status == coverage_module.STATUS_OK
        assert result.alarm is False

    def test_coverage_below_floor_alarms(self, coverage_module):
        result = coverage_module.evaluate_coverage("web", "en", 31_100, 933)  # 3.0%
        assert result.status == coverage_module.STATUS_BELOW_FLOOR
        assert result.alarm is True

    def test_coverage_just_above_floor_does_not_alarm(self, coverage_module):
        result = coverage_module.evaluate_coverage("web", "en", 31_100, 1_600)  # 5.1%
        assert result.status == coverage_module.STATUS_OK
        assert result.alarm is False

    def test_coverage_above_ceiling_alarms(self, coverage_module):
        result = coverage_module.evaluate_coverage("web", "en", 31_100, 20_000)  # ~64%
        assert result.status == coverage_module.STATUS_ABOVE_CEILING
        assert result.alarm is True

    def test_small_corpus_ratio_is_not_alarmed(self, coverage_module):
        result = coverage_module.evaluate_coverage("partial", "en", 200, 5)  # 2.5%, under min
        assert result.status == coverage_module.STATUS_SMALL_SAMPLE
        assert result.alarm is False

    def test_small_corpus_with_zero_tags_still_alarms(self, coverage_module):
        result = coverage_module.evaluate_coverage("partial", "en", 200, 0)
        assert result.status == coverage_module.STATUS_EMPTY
        assert result.alarm is True

    def test_translation_with_no_verses_is_not_alarmed(self, coverage_module):
        result = coverage_module.evaluate_coverage("unseeded", "en", 0, 0)
        assert result.status == coverage_module.STATUS_NO_VERSES
        assert result.alarm is False

    def test_thresholds_are_overridable(self, coverage_module):
        result = coverage_module.evaluate_coverage("kjv", "en", 31_100, 5_691, floor_pct=100.0)
        assert result.alarm is True
        assert result.status == coverage_module.STATUS_BELOW_FLOOR


class TestEvaluateAll:
    def test_evaluates_every_row(self, coverage_module):
        rows = [
            {
                "code": "kjv",
                "language_code": "en",
                "verse_count": 31_100,
                "tagged_verse_count": 5_691,
            },
            {"code": "cuv", "language_code": "zh", "verse_count": 31_100, "tagged_verse_count": 0},
        ]
        results = coverage_module.evaluate_all(rows)
        assert [r.translation for r in results] == ["kjv", "cuv"]
        assert results[1].alarm is True


class TestRendering:
    def test_alarms_render_as_github_warning_annotations(self, coverage_module):
        results = [
            coverage_module.evaluate_coverage("kjv", "en", 31_100, 0),
            coverage_module.evaluate_coverage("web", "en", 31_100, 5_691),
        ]
        annotations = coverage_module.render_annotations(results)
        assert len(annotations) == 1
        assert annotations[0].startswith("::warning::")
        assert "kjv" in annotations[0]

    def test_no_annotations_when_everything_is_in_band(self, coverage_module):
        results = [coverage_module.evaluate_coverage("kjv", "en", 31_100, 5_691)]
        assert coverage_module.render_annotations(results) == []

    def test_summary_table_lists_every_translation_including_ok_ones(self, coverage_module):
        results = [
            coverage_module.evaluate_coverage("kjv", "en", 31_100, 5_691),
            coverage_module.evaluate_coverage("cuv", "zh", 31_100, 0),
        ]
        summary = coverage_module.render_summary(results)
        assert "kjv" in summary
        assert "cuv" in summary


class TestExitCode:
    def test_exit_code_is_zero_when_alarms_present_by_default(self, coverage_module):
        results = [coverage_module.evaluate_coverage("kjv", "en", 31_100, 0)]
        assert coverage_module.exit_code(results, strict=False) == 0

    def test_exit_code_is_one_when_strict_and_alarms_present(self, coverage_module):
        results = [coverage_module.evaluate_coverage("kjv", "en", 31_100, 0)]
        assert coverage_module.exit_code(results, strict=True) == 1

    def test_exit_code_is_zero_when_strict_and_no_alarms(self, coverage_module):
        results = [coverage_module.evaluate_coverage("kjv", "en", 31_100, 5_691)]
        assert coverage_module.exit_code(results, strict=True) == 0


class TestArgParsing:
    def test_defaults(self, coverage_module):
        args = coverage_module._build_parser().parse_args([])
        assert args.strict is False
        assert args.floor == coverage_module.DEFAULT_FLOOR_PCT
        assert args.ceiling == coverage_module.DEFAULT_CEILING_PCT
        assert args.min_verses == coverage_module.DEFAULT_MIN_VERSES_FOR_RATIO
        assert args.translation is None

    def test_translation_is_repeatable(self, coverage_module):
        args = coverage_module._build_parser().parse_args(
            ["--translation", "kjv", "--translation", "web"]
        )
        assert args.translation == ["kjv", "web"]

    def test_strict_flag(self, coverage_module):
        args = coverage_module._build_parser().parse_args(["--strict"])
        assert args.strict is True
