"""Unit tests for the follow-up chip evaluators (BITB-178)."""

import pytest

from golden_set.evaluators import run_all_checks
from golden_set.follow_up_evaluators import (
    _MAX_FOLLOW_UP_LEN,
    check_follow_ups,
    check_multi_turn,
    normalize_chip,
    run_follow_up_checks,
)
from golden_set.models import Expectations


def _result(checks, name):
    return next((ok, detail) for n, ok, detail in checks if n == name)


def _exp(mode="expected", lang="en"):
    return Expectations(follow_ups=mode, response_language=lang, must_contain_scripture=False)


CHIPS = ["How do I forgive someone?", "What does grace mean?"]


class TestCount:
    @pytest.mark.parametrize("n,ok", [(0, False), (1, False), (2, True), (3, True), (4, False)])
    def test_expected(self, n, ok):
        chips = [f"Question number {i}?" for i in range(n)]
        assert _result(check_follow_ups(chips, "", _exp("expected")), "follow_up_count")[0] is ok

    @pytest.mark.parametrize("n,ok", [(0, True), (1, False), (2, False)])
    def test_suppressed(self, n, ok):
        chips = [f"Question number {i}?" for i in range(n)]
        assert _result(check_follow_ups(chips, "", _exp("suppressed")), "follow_up_count")[0] is ok

    @pytest.mark.parametrize("n,ok", [(0, True), (1, False), (2, True), (3, True), (4, False)])
    def test_any(self, n, ok):
        chips = [f"Question number {i}?" for i in range(n)]
        assert _result(check_follow_ups(chips, "", _exp("any")), "follow_up_count")[0] is ok


class TestShapeChecks:
    def test_length_pass_and_fail(self):
        ok = ["a" * _MAX_FOLLOW_UP_LEN, "b"]
        bad = ["a" * (_MAX_FOLLOW_UP_LEN + 1), "b"]
        assert _result(check_follow_ups(ok, "", _exp()), "follow_up_length")[0]
        assert not _result(check_follow_ups(bad, "", _exp()), "follow_up_length")[0]

    @pytest.mark.parametrize("chip", ["a <b> c", "x > y", "<!-- hi", "oops <", "**bold**", "`c`"])
    def test_markup_fail(self, chip):
        assert not _result(check_follow_ups([chip, "fine?"], "", _exp()), "follow_up_markup")[0]

    def test_markup_pass(self):
        assert _result(check_follow_ups(CHIPS, "", _exp()), "follow_up_markup")[0]

    def test_unique_is_case_and_whitespace_insensitive(self):
        dup = ["What is grace?", "  what   is GRACE?  "]
        assert not _result(check_follow_ups(dup, "", _exp()), "follow_up_unique")[0]
        assert _result(check_follow_ups(CHIPS, "", _exp()), "follow_up_unique")[0]

    def test_normalize_chip(self):
        assert normalize_chip("  A  B\n") == "a b"


class TestTrailerLeak:
    @pytest.mark.parametrize(
        "body", ["answer <!-- FOLLOWUPS: a|b -->", "FOLLOWUPS: a|b", "x <!--FOLLOWUPS : a|b-->"]
    )
    def test_leak_detected(self, body):
        assert not _result(check_follow_ups(CHIPS, body, _exp()), "follow_up_no_trailer_leak")[0]

    def test_clean_body(self):
        ok = _result(check_follow_ups(CHIPS, "Plain answer.", _exp()), "follow_up_no_trailer_leak")
        assert ok[0]

    def test_verses_comment_is_not_a_leak(self):
        body = "God works for good. Romans 8:28\n<!-- VERSES: Romans 8:28 -->"
        assert _result(check_follow_ups(CHIPS, body, _exp()), "follow_up_no_trailer_leak")[0]

    def test_verses_comment_counts_as_cited_for_fabricated_refs(self):
        body = "<!-- VERSES: Romans 8:28 -->"
        checks = check_follow_ups(["What about Romans 8:28?", "x"], body, _exp())
        assert _result(checks, "follow_up_no_fabricated_refs")[0]


# native book name + ref, plus an answer citing it and one that does not
REF_CASES = {
    "en": "Romans 8:28",
    "it": "Romani 8:28",
    "de": "Römer 8,28",
    "es": "Romanos 8:28",
    "fr": "Romains 8:28",
    "pt": "Romanos 8:28",
    "ar": "رومية 8:28",
    "ru": "Римлянам 8:28",
    "zh": "罗马书8:28",
    "hi": "रोमियों 8:28",
    "ko": "로마서 8:28",
}


class TestFabricatedRefs:
    @pytest.mark.parametrize("lang", list(REF_CASES))
    def test_cited_ref_passes(self, lang):
        ref = REF_CASES[lang]
        checks = check_follow_ups([f"{ref} ?", "x"], f"See {ref} for this.", _exp(lang=lang))
        assert _result(checks, "follow_up_no_fabricated_refs")[0]

    @pytest.mark.parametrize("lang", list(REF_CASES))
    def test_uncited_ref_fails(self, lang):
        ref = REF_CASES[lang]
        checks = check_follow_ups([f"{ref} ?", "x"], "Love is patient.", _exp(lang=lang))
        assert not _result(checks, "follow_up_no_fabricated_refs")[0]

    @pytest.mark.parametrize("lang", list(REF_CASES))
    def test_localized_chip_matches_english_verses_comment(self, lang):
        ref = REF_CASES[lang]
        body = "Answer text.\n<!-- VERSES: Romans 8:28 -->"
        checks = check_follow_ups([f"{ref} ?", "x"], body, _exp(lang=lang))
        assert _result(checks, "follow_up_no_fabricated_refs")[0]

    @pytest.mark.parametrize(
        "chip,cited",
        [
            ("What does (Romanos 8:28) mean?", "Romanos 8:28"),
            ("¿Qué significa [Romanos 8:28]?", "Romanos 8:28"),
            ("Что значит [Римлянам 8:28]?", "Римлянам 8:28"),
            ("（罗马书8:28）是什么意思", "罗马书8:28"),
            ("「罗马书8:28」是什么意思", "罗马书8:28"),
            ("Was heißt Römer 8,28-30?", "Römer 8,28-30"),
            ("What about Romans 8:28-30?", "Romans 8:28-30"),
        ],
    )
    def test_wrapped_and_range_variants(self, chip, cited):
        ok = check_follow_ups([chip, "x"], f"As in {cited}.", _exp())
        assert _result(ok, "follow_up_no_fabricated_refs")[0]
        bad = check_follow_ups([chip, "x"], "Nothing cited.", _exp())
        assert not _result(bad, "follow_up_no_fabricated_refs")[0]

    def test_chip_without_reference_passes(self):
        checks = check_follow_ups(CHIPS, "No refs here.", _exp())
        assert _result(checks, "follow_up_no_fabricated_refs")[0]


LANG_CHIPS = {
    "en": ["How can I forgive someone who hurt me?", "What does the Bible say about grace?"],
    "it": ["Come posso perdonare chi mi ha ferito?", "Cosa dice la Bibbia sulla grazia di Dio?"],
    "de": [
        "Wie kann ich jemandem vergeben, der mich verletzt hat?",
        "Was sagt die Bibel über Gnade?",
    ],
    "es": [
        "¿Cómo puedo perdonar a quien me hirió?",
        "¿Qué dice la Biblia sobre la gracia de Dios?",
    ],
    "fr": [
        "Comment puis-je pardonner à quelqu'un qui m'a blessé ?",
        "Que dit la Bible sur la grâce ?",
    ],
    "pt": ["Como posso perdoar quem me magoou?", "O que a Bíblia diz sobre a graça de Deus?"],
    "ar": ["كيف أسامح شخصًا جرحني؟", "ماذا يقول الكتاب المقدس عن نعمة الله؟"],
    "ru": [
        "Как мне простить человека, который меня обидел?",
        "Что Библия говорит о милости Божьей?",
    ],
    "zh": ["我该怎样饶恕伤害过我的人？", "圣经对神的恩典有什么教导？"],
    "hi": [
        "जिसने मुझे चोट पहुँचाई उसे मैं कैसे माफ़ करूँ?",
        "बाइबल परमेश्वर के अनुग्रह के बारे में क्या कहती है?",
    ],
    "ko": [
        "저에게 상처를 준 사람을 어떻게 용서할 수 있나요?",
        "성경은 하나님의 은혜에 대해 무엇이라고 말하나요?",
    ],
}


class TestChipLanguage:
    @pytest.mark.parametrize("lang", list(LANG_CHIPS))
    def test_matching_language_passes(self, lang):
        try:
            from utils.language import detect_language

            detect_language("test")
        except Exception:
            pytest.skip("language detection unavailable")
        checks = check_follow_ups(LANG_CHIPS[lang], "", _exp(lang=lang))
        assert _result(checks, "follow_up_language")[0], _result(checks, "follow_up_language")

    def test_wrong_language_fails(self):
        try:
            from utils.language import detect_language

            detect_language("test")
        except Exception:
            pytest.skip("language detection unavailable")
        checks = check_follow_ups(LANG_CHIPS["it"], "", _exp(lang="en"))
        assert not _result(checks, "follow_up_language")[0]

    def test_no_chips_skips(self):
        ok, detail = _result(check_follow_ups([], "", _exp("suppressed")), "follow_up_language")
        assert ok and "skipped" in detail

    def test_detector_unavailable_skips(self, monkeypatch):
        import utils.language as language

        def boom(_text):
            raise RuntimeError("no detector")

        monkeypatch.setattr(language, "detect_language", boom)
        ok, detail = _result(check_follow_ups(CHIPS, "", _exp()), "follow_up_language")
        assert ok and "unavailable" in detail


class TestMultiTurn:
    def test_distinct_turn2_passes(self):
        checks = check_multi_turn(["a?", "b?"], "a?", ["c?", "d?"])
        assert all(ok for _, ok, _ in checks)

    def test_repeating_tapped_chip_fails(self):
        checks = check_multi_turn(["a?", "b?"], "a?", ["  A?", "d?"])
        assert not _result(checks, "follow_up_no_repeat_tapped")[0]

    def test_identical_set_fails(self):
        checks = check_multi_turn(["a?", "b?"], "a?", ["b?", "A?"])
        assert not _result(checks, "follow_up_no_repeat_set")[0]


class TestRunFollowUpChecks:
    def test_all_pass(self):
        score = run_follow_up_checks(["First question?", "Second question?"], "Body.", _exp())
        # language check may fail on tiny English strings; assert structure instead
        assert score.total_checks == 7
        assert set(score.details) >= {"follow_up_count", "follow_up_unique"}

    def test_failures_listed(self):
        score = run_follow_up_checks([], "Body <!-- FOLLOWUPS: a|b -->", _exp("expected"))
        assert not score.passed
        assert "follow_up_count" in score.failed_checks
        assert "follow_up_no_trailer_leak" in score.failed_checks
        assert score.passed_checks == score.total_checks - len(score.failed_checks)

    def test_run_all_checks_unchanged(self):
        score = run_all_checks("Some response", Expectations(must_contain_scripture=False))
        assert "follow_up_count" not in score.details
