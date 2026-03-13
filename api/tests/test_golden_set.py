"""Tests for the golden set testing system.

Validates YAML data integrity, evaluator correctness, loader, runner, and reviewer.
"""

import json
from unittest.mock import patch

import pytest

from golden_set.evaluators import (
    check_expected_books,
    check_forbidden_content,
    check_response_language,
    check_response_length,
    check_scripture_presence,
    check_situation_acknowledgment,
    check_source_statement,
    run_all_checks,
)
from golden_set.loader import (
    filter_by_category,
    filter_by_tags,
    get_case_ids,
    load_test_cases,
)
from golden_set.models import (
    AutomatedScore,
    Expectations,
    GoldenSetCase,
    GoldenSetInput,
    HumanScore,
)

# ==================== Data Validation Tests ====================


@pytest.mark.golden_set
class TestYamlDataIntegrity:
    """Validate that all YAML test case files load correctly."""

    def test_all_yaml_files_parse(self):
        cases = load_test_cases()
        assert len(cases) > 0, "No test cases loaded from YAML files"

    def test_all_cases_have_valid_structure(self):
        cases = load_test_cases()
        for case in cases:
            assert isinstance(case, GoldenSetCase)
            assert case.id, f"Case missing id: {case}"
            assert case.category, f"Case {case.id} missing category"
            assert case.name, f"Case {case.id} missing name"
            assert case.input.message, f"Case {case.id} missing input message"

    def test_unique_case_ids(self):
        cases = load_test_cases()
        ids = get_case_ids(cases)
        duplicates = [x for x in ids if ids.count(x) > 1]
        assert len(duplicates) == 0, f"Duplicate case IDs found: {set(duplicates)}"

    def test_required_categories_present(self):
        cases = load_test_cases()
        categories = {c.category for c in cases}
        required = {"encouragement", "verse_lookup", "prayer_lookup", "theological"}
        missing = required - categories
        assert not missing, f"Missing required categories: {missing}"

    def test_minimum_cases_per_category(self):
        cases = load_test_cases()
        categories = {}
        for case in cases:
            categories.setdefault(case.category, 0)
            categories[case.category] += 1
        for category, count in categories.items():
            assert count >= 3, f"Category '{category}' has only {count} cases (minimum 3)"

    def test_encouragement_cases_require_situation_acknowledgment(self):
        cases = load_test_cases()
        enc_cases = filter_by_category(cases, "encouragement")
        for case in enc_cases:
            assert (
                case.expectations.must_acknowledge_situation
            ), f"Encouragement case {case.id} should require situation acknowledgment"

    def test_verse_lookup_cases_require_source_statement(self):
        cases = load_test_cases()
        verse_cases = filter_by_category(cases, "verse_lookup")
        for case in verse_cases:
            assert (
                case.expectations.source_statement_required
            ), f"Verse lookup case {case.id} should require source statement"

    def test_prayer_non_biblical_has_must_not_contain(self):
        cases = load_test_cases()
        prayer_cases = filter_by_category(cases, "prayer_lookup")
        non_biblical = [c for c in prayer_cases if c.expectations.source_is_biblical is False]
        assert len(non_biblical) > 0, "No non-biblical prayer cases found"


# ==================== Loader Tests ====================


@pytest.mark.golden_set
class TestLoader:
    """Test the YAML loader functionality."""

    def test_load_returns_golden_set_cases(self):
        cases = load_test_cases()
        assert all(isinstance(c, GoldenSetCase) for c in cases)

    def test_filter_by_category(self):
        cases = load_test_cases()
        enc_cases = filter_by_category(cases, "encouragement")
        assert all(c.category == "encouragement" for c in enc_cases)
        assert len(enc_cases) > 0

    def test_filter_by_category_nonexistent(self):
        cases = load_test_cases()
        result = filter_by_category(cases, "nonexistent_category")
        assert result == []

    def test_filter_by_tags(self):
        cases = load_test_cases()
        comfort_cases = filter_by_tags(cases, ["comfort"])
        assert len(comfort_cases) > 0
        assert all(any("comfort" in t for t in c.tags) for c in comfort_cases)

    def test_filter_by_tags_empty(self):
        cases = load_test_cases()
        result = filter_by_tags(cases, ["nonexistent_tag_xyz"])
        assert result == []

    def test_get_case_ids(self):
        cases = load_test_cases()
        ids = get_case_ids(cases)
        assert len(ids) == len(cases)
        assert all(isinstance(i, str) for i in ids)


# ==================== Evaluator Tests ====================


@pytest.mark.golden_set
class TestScripturePresenceCheck:
    """Test scripture presence evaluator."""

    def test_detects_verse_reference(self):
        response = "As John 3:16 tells us, God so loved the world."
        exp = Expectations(must_contain_scripture=True, min_verses_cited=1)
        passed, detail = check_scripture_presence(response, exp)
        assert passed

    def test_detects_numbered_book(self):
        response = "In 1 Corinthians 13:4, Paul writes about love."
        exp = Expectations(must_contain_scripture=True, min_verses_cited=1)
        passed, detail = check_scripture_presence(response, exp)
        assert passed

    def test_fails_when_no_reference(self):
        response = "God loves you very much and wants the best for you."
        exp = Expectations(must_contain_scripture=True, min_verses_cited=1)
        passed, detail = check_scripture_presence(response, exp)
        assert not passed

    def test_skips_when_not_required(self):
        response = "No verses here."
        exp = Expectations(must_contain_scripture=False)
        passed, detail = check_scripture_presence(response, exp)
        assert passed

    def test_min_verses_cited(self):
        response = "See John 3:16 and Romans 8:28 for guidance."
        exp = Expectations(must_contain_scripture=True, min_verses_cited=3)
        passed, detail = check_scripture_presence(response, exp)
        assert not passed
        assert "2" in detail


@pytest.mark.golden_set
class TestExpectedBooksCheck:
    """Test expected book match evaluator."""

    def test_finds_expected_book(self):
        response = "In the book of Psalms, we find comfort."
        exp = Expectations(expected_books=["Psalms", "Isaiah"])
        passed, detail = check_expected_books(response, exp)
        assert passed

    def test_fails_when_no_match(self):
        response = "In Exodus 20, God gives the commandments."
        exp = Expectations(expected_books=["Psalms", "Isaiah"])
        passed, detail = check_expected_books(response, exp)
        assert not passed

    def test_skips_when_no_books_specified(self):
        response = "Any response."
        exp = Expectations(expected_books=[])
        passed, detail = check_expected_books(response, exp)
        assert passed


@pytest.mark.golden_set
class TestForbiddenContentCheck:
    """Test forbidden content evaluator."""

    def test_detects_forbidden_phrase(self):
        response = "You should just pray about it and everything will be fine."
        exp = Expectations(must_not_contain=["just pray about it"])
        passed, detail = check_forbidden_content(response, exp)
        assert not passed

    def test_case_insensitive(self):
        response = "JUST PRAY ABOUT IT."
        exp = Expectations(must_not_contain=["just pray about it"])
        passed, detail = check_forbidden_content(response, exp)
        assert not passed

    def test_passes_when_clean(self):
        response = "I understand your concern. Let me share some scripture."
        exp = Expectations(must_not_contain=["just pray about it"])
        passed, detail = check_forbidden_content(response, exp)
        assert passed

    def test_skips_when_empty(self):
        response = "Any response."
        exp = Expectations(must_not_contain=[])
        passed, detail = check_forbidden_content(response, exp)
        assert passed


@pytest.mark.golden_set
class TestSourceStatementCheck:
    """Test source statement evaluator."""

    def test_detects_biblical_source(self):
        response = "This is from the Bible, specifically John 3:16. It tells us..."
        exp = Expectations(source_statement_required=True, source_is_biblical=True)
        passed, detail = check_source_statement(response, exp)
        assert passed

    def test_detects_non_biblical_source(self):
        response = "The Hail Mary is not from the Bible. It is a Catholic prayer..."
        exp = Expectations(source_statement_required=True, source_is_biblical=False)
        passed, detail = check_source_statement(response, exp)
        assert passed

    def test_fails_when_missing(self):
        response = "The Hail Mary is a beautiful prayer that many people recite."
        exp = Expectations(source_statement_required=True, source_is_biblical=False)
        passed, detail = check_source_statement(response, exp)
        assert not passed

    def test_skips_when_not_required(self):
        response = "Any response."
        exp = Expectations(source_statement_required=False)
        passed, detail = check_source_statement(response, exp)
        assert passed

    def test_detects_found_in_scripture(self):
        response = "This passage is found in the Bible, in Matthew chapter 6."
        exp = Expectations(source_statement_required=True, source_is_biblical=True)
        passed, detail = check_source_statement(response, exp)
        assert passed

    def test_detects_not_in_scripture(self):
        response = "This prayer is not found in scripture. It was written..."
        exp = Expectations(source_statement_required=True, source_is_biblical=False)
        passed, detail = check_source_statement(response, exp)
        assert passed

    def test_any_source_when_biblical_is_none(self):
        response = "This is from the Bible. John 3:16 says..."
        exp = Expectations(source_statement_required=True, source_is_biblical=None)
        passed, detail = check_source_statement(response, exp)
        assert passed


@pytest.mark.golden_set
class TestResponseLanguageCheck:
    """Test response language evaluator."""

    def test_english_response(self):
        response = (
            "I understand you are going through a difficult time. "
            "The Bible offers us comfort in many places."
        )
        exp = Expectations(response_language="en")
        passed, detail = check_response_language(response, exp)
        assert passed

    def test_italian_response(self):
        response = (
            "Capisco che stai attraversando un momento difficile. "
            "La Bibbia ci offre conforto in molti passi."
        )
        exp = Expectations(response_language="it")
        passed, detail = check_response_language(response, exp)
        assert passed

    def test_wrong_language(self):
        response = (
            "Capisco che stai attraversando un momento difficile. "
            "La Bibbia ci offre conforto in molti passi."
        )
        exp = Expectations(response_language="en")
        passed, detail = check_response_language(response, exp)
        assert not passed


@pytest.mark.golden_set
class TestResponseLengthCheck:
    """Test response length evaluator."""

    def test_within_limit(self):
        response = "Short response."
        exp = Expectations(max_response_length=100)
        passed, detail = check_response_length(response, exp)
        assert passed

    def test_exceeds_limit(self):
        response = "A" * 1001
        exp = Expectations(max_response_length=1000)
        passed, detail = check_response_length(response, exp)
        assert not passed

    def test_no_limit(self):
        response = "A" * 10000
        exp = Expectations(max_response_length=None)
        passed, detail = check_response_length(response, exp)
        assert passed


@pytest.mark.golden_set
class TestSituationAcknowledgmentCheck:
    """Test situation acknowledgment evaluator."""

    def test_acknowledges_situation(self):
        response = "I hear that you are feeling anxious about your job. That can be overwhelming."
        exp = Expectations(must_acknowledge_situation=True)
        passed, detail = check_situation_acknowledgment(
            response, exp, "I've been feeling very anxious about my job lately"
        )
        assert passed

    def test_fails_when_not_acknowledged(self):
        response = "Here are some Bible verses for you to read."
        exp = Expectations(must_acknowledge_situation=True)
        passed, detail = check_situation_acknowledgment(
            response, exp, "I'm dealing with grief after losing my mother"
        )
        assert not passed

    def test_skips_when_not_required(self):
        response = "Here are some Bible verses."
        exp = Expectations(must_acknowledge_situation=False)
        passed, detail = check_situation_acknowledgment(response, exp, "Any input")
        assert passed


@pytest.mark.golden_set
class TestRunAllChecks:
    """Test the combined evaluator."""

    def test_all_checks_pass(self):
        response = (
            "This is from the Bible. I understand your anxiety about work. "
            "In Philippians 4:6-7 we read: 'Do not be anxious about anything.'"
        )
        exp = Expectations(
            must_contain_scripture=True,
            min_verses_cited=1,
            expected_books=["Philippians"],
            must_not_contain=["just pray about it"],
            response_language="en",
            source_statement_required=True,
            source_is_biblical=True,
            must_acknowledge_situation=True,
        )
        score = run_all_checks(response, exp, "I'm anxious about work")
        assert isinstance(score, AutomatedScore)
        assert score.passed
        assert score.total_checks == 7
        assert score.passed_checks == 7
        assert score.failed_checks == []

    def test_some_checks_fail(self):
        response = "Just pray about it and everything will be fine."
        exp = Expectations(
            must_contain_scripture=True,
            min_verses_cited=1,
            must_not_contain=["just pray about it"],
            response_language="en",
        )
        score = run_all_checks(response, exp)
        assert not score.passed
        assert "scripture_presence" in score.failed_checks
        assert "forbidden_content" in score.failed_checks

    def test_returns_details(self):
        response = "A simple response."
        exp = Expectations()
        score = run_all_checks(response, exp)
        assert isinstance(score.details, dict)
        assert "scripture_presence" in score.details
        assert "forbidden_content" in score.details


# ==================== Model Tests ====================


@pytest.mark.golden_set
class TestModels:
    """Test Pydantic model construction."""

    def test_golden_set_case_minimal(self):
        case = GoldenSetCase(
            id="test-001",
            category="test",
            name="Test case",
            input=GoldenSetInput(message="Hello"),
            expectations=Expectations(),
        )
        assert case.id == "test-001"

    def test_golden_set_case_full(self):
        case = GoldenSetCase(
            id="test-002",
            category="test",
            name="Full test",
            input=GoldenSetInput(
                message="What does John 3:16 say?",
                include_search=True,
                preferred_translation="kjv",
            ),
            expectations=Expectations(
                must_contain_scripture=True,
                min_verses_cited=1,
                expected_books=["John"],
                source_statement_required=True,
                source_is_biblical=True,
            ),
            reference_response="This is the reference.",
            tags=["test", "verse-lookup"],
        )
        assert case.expectations.source_is_biblical is True
        assert len(case.tags) == 2

    def test_human_score_validation(self):
        score = HumanScore(
            relevance=4,
            scripture_accuracy=5,
            tone_quality=3,
            source_attribution=4,
            overall=4,
            notes="Good response",
        )
        assert score.overall == 4

    def test_human_score_rejects_out_of_range(self):
        with pytest.raises(Exception):
            HumanScore(
                relevance=6,
                scripture_accuracy=5,
                tone_quality=3,
                source_attribution=4,
                overall=4,
            )

    def test_expectations_defaults(self):
        exp = Expectations()
        assert exp.must_contain_scripture is True
        assert exp.min_verses_cited == 0
        assert exp.response_language == "en"
        assert exp.source_statement_required is False
        assert exp.source_is_biblical is None
        assert exp.must_acknowledge_situation is False

    def test_automated_score(self):
        score = AutomatedScore(
            passed=True,
            total_checks=7,
            passed_checks=7,
        )
        assert score.passed
        assert score.failed_checks == []


# ==================== Runner Tests ====================


@pytest.mark.golden_set
class TestMockRunner:
    """Test the mock runner."""

    @pytest.mark.asyncio
    async def test_run_mock_returns_eval_run(self):
        from golden_set.runner import run_mock

        run = await run_mock()
        assert run.mode == "mock"
        assert run.provider == "mock"
        assert len(run.results) > 0

    @pytest.mark.asyncio
    async def test_run_mock_produces_case_results(self):
        from golden_set.runner import run_mock

        run = await run_mock()
        for result in run.results:
            assert result.case_id
            assert result.actual_response
            assert result.automated_score is not None

    @pytest.mark.asyncio
    async def test_run_mock_with_specific_cases(self):
        from golden_set.runner import run_mock

        cases = load_test_cases()
        subset = [c for c in cases if c.category == "verse_lookup"][:2]
        run = await run_mock(cases=subset)
        assert len(run.results) == 2

    @pytest.mark.asyncio
    async def test_mock_encouragement_passes(self):
        """Mock encouragement response should pass encouragement checks."""
        from golden_set.runner import run_mock

        cases = load_test_cases()
        enc_cases = [c for c in cases if c.category == "encouragement"][:1]
        run = await run_mock(cases=enc_cases)
        # Mock response has Philippians and Psalms refs + situation acknowledgment
        assert run.results[0].automated_score.passed

    @pytest.mark.asyncio
    async def test_mock_verse_lookup_passes(self):
        """Mock verse lookup response should pass verse lookup checks."""
        from golden_set.runner import run_mock

        cases = load_test_cases()
        verse_cases = [c for c in cases if c.category == "verse_lookup"][:1]
        run = await run_mock(cases=verse_cases)
        assert run.results[0].automated_score.passed


@pytest.mark.golden_set
class TestRunnerPersistence:
    """Test saving and loading runs."""

    @pytest.mark.asyncio
    async def test_save_and_load_run(self, tmp_path):
        from golden_set.runner import load_run, run_mock, save_run

        run = await run_mock()
        path = save_run(run, directory=tmp_path)
        assert path.exists()

        loaded = load_run(path)
        assert loaded.run_id == run.run_id
        assert len(loaded.results) == len(run.results)

    @pytest.mark.asyncio
    async def test_save_creates_json(self, tmp_path):
        from golden_set.runner import run_mock, save_run

        run = await run_mock()
        path = save_run(run, directory=tmp_path)
        assert path.suffix == ".json"

        with open(path) as f:
            data = json.load(f)
        assert data["run_id"] == run.run_id

    @pytest.mark.asyncio
    async def test_list_runs(self, tmp_path):
        from golden_set.runner import list_runs, run_mock, save_run

        run1 = await run_mock()
        run2 = await run_mock()
        save_run(run1, directory=tmp_path)
        save_run(run2, directory=tmp_path)

        runs = list_runs(directory=tmp_path)
        assert len(runs) == 2

    def test_list_runs_empty_dir(self, tmp_path):
        from golden_set.runner import list_runs

        runs = list_runs(directory=tmp_path)
        assert runs == []

    def test_list_runs_nonexistent_dir(self, tmp_path):
        from golden_set.runner import list_runs

        runs = list_runs(directory=tmp_path / "nonexistent")
        assert runs == []

    @pytest.mark.asyncio
    async def test_get_latest_run(self, tmp_path):
        import time

        from golden_set.runner import get_latest_run, run_mock, save_run

        run1 = await run_mock()
        save_run(run1, directory=tmp_path)
        time.sleep(0.1)  # Ensure different mtime
        run2 = await run_mock()
        save_run(run2, directory=tmp_path)

        latest = get_latest_run(directory=tmp_path)
        assert latest is not None
        assert latest.run_id == run2.run_id

    def test_get_latest_run_empty(self, tmp_path):
        from golden_set.runner import get_latest_run

        result = get_latest_run(directory=tmp_path)
        assert result is None


@pytest.mark.golden_set
class TestPrintSummary:
    """Test the summary printer."""

    @pytest.mark.asyncio
    async def test_print_summary_runs(self, capsys):
        from golden_set.runner import print_summary, run_mock

        run = await run_mock()
        print_summary(run)
        captured = capsys.readouterr()
        assert "Golden Set Run" in captured.out
        assert "mock" in captured.out


# ==================== Reviewer Tests ====================


@pytest.mark.golden_set
class TestReviewer:
    """Test reviewer utility functions."""

    def test_prompt_score_with_default(self):
        """Test _prompt_score returns default on empty input."""
        from golden_set.reviewer import _prompt_score

        with patch("builtins.input", return_value=""):
            score = _prompt_score("Test", default=4)
        assert score == 4

    def test_prompt_score_with_value(self):
        from golden_set.reviewer import _prompt_score

        with patch("builtins.input", return_value="5"):
            score = _prompt_score("Test")
        assert score == 5

    def test_prompt_score_retries_on_invalid(self):
        from golden_set.reviewer import _prompt_score

        with patch("builtins.input", side_effect=["abc", "7", "3"]):
            score = _prompt_score("Test")
        assert score == 3

    @pytest.mark.asyncio
    async def test_review_run_quit_immediately(self):
        """Test that quit saves progress."""
        from golden_set.reviewer import review_run
        from golden_set.runner import run_mock

        run = await run_mock()

        with patch("builtins.input", return_value="q"):
            updated = review_run(run)

        # Should have no human scores since we quit immediately
        scored = [r for r in updated.results if r.human_score is not None]
        assert len(scored) == 0

    @pytest.mark.asyncio
    async def test_review_run_skip_cases(self):
        """Test that skip works."""
        from golden_set.reviewer import review_run
        from golden_set.runner import run_mock

        cases = load_test_cases()[:2]
        run = await run_mock(cases=cases)

        # Skip first, quit on second
        with patch("builtins.input", side_effect=["s", "q"]):
            updated = review_run(run)

        scored = [r for r in updated.results if r.human_score is not None]
        assert len(scored) == 0

    @pytest.mark.asyncio
    async def test_review_run_score_case(self):
        """Test scoring a single case then quitting."""
        from golden_set.reviewer import review_run
        from golden_set.runner import run_mock

        cases = load_test_cases()[:1]
        run = await run_mock(cases=cases)

        # Approve, enter all defaults, empty notes, then we're done (only 1 case)
        inputs = ["a", "", "", "", "", "", ""]
        with patch("builtins.input", side_effect=inputs):
            updated = review_run(run)

        scored = [r for r in updated.results if r.human_score is not None]
        assert len(scored) == 1
        assert scored[0].human_score.overall == 3  # default

    def test_select_run_no_runs(self, tmp_path):
        """Test select_run with no saved runs."""
        from golden_set.reviewer import select_run

        with patch("golden_set.reviewer.list_runs", return_value=[]):
            result = select_run()
        assert result is None
