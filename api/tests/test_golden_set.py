"""Tests for the golden set testing system.

Validates YAML data integrity, evaluator correctness, and loader functionality.
"""

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
