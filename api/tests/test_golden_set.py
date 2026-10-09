"""Tests for the golden set testing system.

Validates YAML data integrity, evaluator correctness, and loader functionality.
"""

import pytest

from golden_set.evaluators import (
    check_expected_books,
    check_forbidden_content,
    check_required_alternatives,
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
from utils.translation_registry import EXTRA_REVERSE_MAPPINGS, TRANSLATION_REGISTRY
from utils.verse_parser import extract_references

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
class TestRequiredAlternativesCheck:
    """must_contain_any: one alternative from EVERY group must appear (BITB-178)."""

    GROUPS = [["1:78", "1,78", "verse 78"], ["messiah", "christ"]]

    def test_passes_when_every_group_has_a_match(self):
        exp = Expectations(must_contain_any=self.GROUPS)
        passed, _ = check_required_alternatives("See Luke 1,78: the Messiah.", exp)
        assert passed

    def test_fails_and_names_the_group_without_a_match(self):
        exp = Expectations(must_contain_any=self.GROUPS)
        passed, detail = check_required_alternatives("See verse 78 about John.", exp)
        assert not passed
        assert "messiah" in detail
        assert "1:78" not in detail  # the satisfied group is not reported

    def test_one_alternative_is_not_enough_for_two_groups(self):
        exp = Expectations(must_contain_any=self.GROUPS)
        passed, _ = check_required_alternatives("1:78 and also 1,78 and verse 78", exp)
        assert not passed

    def test_case_insensitive_including_non_ascii(self):
        exp = Expectations(must_contain_any=[["gesù", "cristo"], ["aurora"]])
        passed, _ = check_required_alternatives("L'AURORA è GESÙ.", exp)
        assert passed

    @pytest.mark.parametrize("response", ["الآية ٧٨ تتحدث عن المسيح", "79节讲到弥赛亚，见78节"])
    def test_non_latin_alternatives(self, response):
        groups = [["١:٧٨", "٧٨", "78节"], ["المسيح", "弥赛亚"]]
        passed, _ = check_required_alternatives(response, Expectations(must_contain_any=groups))
        assert passed

    def test_skips_when_empty(self):
        passed, _ = check_required_alternatives("Any response.", Expectations())
        assert passed

    def test_registered_in_run_all_checks(self):
        exp = Expectations(must_contain_scripture=False, must_contain_any=self.GROUPS)
        score = run_all_checks("Only verse 78 is mentioned.", exp)
        assert "required_alternatives" in score.details
        assert "required_alternatives" in score.failed_checks
        ok = run_all_checks("Verse 78 shows it is the Messiah.", exp)
        assert "required_alternatives" not in ok.failed_checks
        assert ok.passed


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
        assert score.total_checks == 9
        assert score.passed_checks == 9
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


# ==================== Interpretation Category (BITB-178) ====================

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
REV2_VERSES = {
    ("Luke", 1, 48),
    ("John", 1, 11),
    ("Luke", 2, 34),
    ("Psalms", 23, 4),
    ("1 Samuel", 17, 45),
    ("Matthew", 11, 3),
}


def _interpretation_cases() -> list[GoldenSetCase]:
    return filter_by_category(load_test_cases(), "interpretation")


def _first_reference(case: GoldenSetCase):
    """The reference the case is about: the message, else the first user turn of the history."""
    text = case.input.message
    if case.input.conversation_history:
        first_user = next(m for m in case.input.conversation_history if m["role"] == "user")
        text = first_user["content"]
    refs, _ = extract_references(text)
    return refs[0] if refs else None


def _book_names(book: str) -> set[str]:
    """Every localized name and alias of a book, lowercased."""
    names = {book.lower()}
    for mapping in TRANSLATION_REGISTRY.values():
        if mapping and book in mapping:
            names.add(mapping[book].lower())
    names.update(
        alias.lower() for alias, english in EXTRA_REVERSE_MAPPINGS.items() if english == book
    )
    return names


def _satisfied(group: list[str], text: str) -> bool:
    lowered = text.lower()
    return any(alt.lower() in lowered for alt in group)


def _is_multi_turn(case: GoldenSetCase) -> bool:
    return bool(case.input.conversation_history)


@pytest.mark.golden_set
class TestInterpretationCases:
    """The `interpretation` category: referents, speakers and stability under pushback."""

    def test_case_count_and_unique_ids(self):
        cases = _interpretation_cases()
        ids = [c.id for c in cases]
        assert len(cases) == 81
        assert len(set(ids)) == len(ids)
        assert ids == [f"interp-{n:03d}" for n in range(1, 82)]

    def test_core_luke_1_79_case_exists_in_all_languages(self):
        langs = {
            c.input.language
            for c in _interpretation_cases()
            if not _is_multi_turn(c) and "luke-1-79" in c.tags
        }
        assert langs == set(LANGUAGES)

    def test_every_single_turn_message_parses_to_a_reference(self):
        for case in _interpretation_cases():
            if _is_multi_turn(case):
                continue
            refs, _ = extract_references(case.input.message)
            assert refs, f"{case.id}: no verse reference parsed from {case.input.message!r}"

    def test_every_pushback_case_has_a_referenced_first_user_turn(self):
        pushback = [c for c in _interpretation_cases() if any("pushback" in t for t in c.tags)]
        assert len(pushback) >= 30
        for case in pushback:
            history = case.input.conversation_history
            assert history, f"{case.id}: pushback case without history"
            assert history[0]["role"] == "user", f"{case.id}: history must start with the user"
            assert any(m["role"] == "assistant" for m in history), f"{case.id}: no answer"
            refs, _ = extract_references(history[0]["content"])
            assert refs, f"{case.id}: first user turn does not parse: {history[0]['content']!r}"
            # the challenge itself names no verse: it must rely on carry-over
            assert not extract_references(case.input.message)[0], case.id

    @pytest.mark.parametrize("stance", ["pushback-user-right", "pushback-user-wrong"])
    def test_luke_1_79_pushback_stances_cover_all_languages(self, stance):
        langs = {
            c.input.language
            for c in _interpretation_cases()
            if stance in c.tags and "luke-1-79" in c.tags
        }
        assert langs == set(LANGUAGES)

    def test_rev2_verses_present_in_en_de_it(self):
        found: dict[tuple, set] = {}
        for case in _interpretation_cases():
            if _is_multi_turn(case):
                continue
            ref = _first_reference(case)
            key = (ref.book, ref.chapter, ref.verse_start)
            found.setdefault(key, set()).add(case.input.language)
        for verse in REV2_VERSES:
            assert found.get(verse) == {"en", "de", "it"}, f"{verse}: {found.get(verse)}"

    def test_case_language_matches_expected_response_language(self):
        for case in _interpretation_cases():
            assert case.input.language in LANGUAGES, case.id
            assert case.input.language == case.expectations.response_language, case.id
            assert case.input.language in case.tags, case.id

    def test_non_latin_cases_do_not_rely_on_the_ascii_reference_regex(self):
        for case in _interpretation_cases():
            if case.input.language in ("ar", "ru", "zh", "hi", "ko"):
                assert case.expectations.must_contain_scripture is False, case.id

    def test_every_case_has_required_alternatives(self):
        for case in _interpretation_cases():
            groups = case.expectations.must_contain_any
            assert groups and all(groups), f"{case.id}: empty must_contain_any"
            assert all(alt.strip() for group in groups for alt in group), case.id

    def test_no_vacuous_groups(self):
        """FR4.2: a check may not pass just because the question or the history echoes it."""
        problems = []
        for case in _interpretation_cases():
            groups = case.expectations.must_contain_any
            message = case.input.message
            if _is_multi_turn(case):
                transcript = " ".join(
                    [m["content"] for m in case.input.conversation_history] + [message]
                )
                if all(_satisfied(g, transcript) for g in groups):
                    problems.append(f"{case.id}: every group is satisfied by message + history")
            else:
                problems += [
                    f"{case.id}: group {g} is satisfied by the question itself"
                    for g in groups
                    if _satisfied(g, message)
                ]
        assert not problems, "\n".join(problems)

    def test_no_alternative_is_a_substring_of_the_books_name(self):
        problems = []
        for case in _interpretation_cases():
            ref = _first_reference(case)
            assert ref is not None, case.id
            names = _book_names(ref.book)
            for group in case.expectations.must_contain_any:
                for alt in group:
                    clash = sorted(n for n in names if alt.lower() in n)
                    if clash:
                        problems.append(f"{case.id}: {alt!r} is part of the book name(s) {clash}")
        assert not problems, "\n".join(problems)

    def test_pushback_user_wrong_forbids_capitulation_and_promises(self):
        wrong = [c for c in _interpretation_cases() if "pushback-user-wrong" in c.tags]
        assert wrong
        for case in wrong:
            assert len(case.expectations.must_not_contain) >= 4, case.id

    def test_pushback_user_right_forbids_promises_not_agreement(self):
        right = [c for c in _interpretation_cases() if "pushback-user-right" in c.tags]
        assert right
        for case in right:
            assert case.expectations.must_not_contain, case.id
            forbidden = " ".join(case.expectations.must_not_contain).lower()
            for agreement in ("you are right", "you're right", "tienes razón", "hai ragione"):
                assert agreement not in forbidden, case.id
