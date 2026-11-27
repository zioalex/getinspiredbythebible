"""Offline tests for the safety golden set and its single-classifier runner (BITB-293, BITB-322).

No network and no credentials: providers are replaced by fakes. The dataset checks run on the
committed fixture, parametrized over all 11 UI languages. BITB-322 adds the gray-zone hard
cases (indirect crisis, veiled/conditional threats, graphic Bible passages) and the `hate`
category, and recalibrates the threshold defaults; these tests pin all three.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "run_safety_golden_set.py"
_DATASET = Path(__file__).parent / "fixtures" / "safety_golden_set.json"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_safety_golden_set", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()

from providers.azure_content_safety import ContentSafetyResult  # noqa: E402

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
CATEGORIES = ["crisis", "threat", "hate", "bible_narrative"]


@pytest.fixture(scope="module")
def dataset():
    return json.loads(_DATASET.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- dataset


def test_dataset_is_valid(dataset):
    assert runner.validate_dataset(dataset) == []


def test_ids_unique(dataset):
    ids = [c["id"] for c in dataset["cases"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("category", CATEGORIES)
def test_each_language_has_eight_cases_per_category(dataset, language, category):
    n = [c for c in dataset["cases"] if c["language"] == language and c["category"] == category]
    assert len(n) >= 8


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_language_has_the_bitb_322_hard_case_ids(dataset, language):
    """The gray-zone / hard additions are identifiable ids, not just an inflated count."""
    ids = {c["id"] for c in dataset["cases"] if c["language"] == language}
    expected = (
        {f"crisis-{language}-{i:02d}" for i in range(5, 9)}  # indirect crisis phrasings
        | {f"threat-{language}-{i:02d}" for i in range(5, 9)}  # conditional / veiled threats
        | {f"bible-{language}-{i:02d}" for i in range(5, 9)}  # graphic Bible passages
        | {f"hate-{language}-{i:02d}" for i in range(1, 9)}  # protected-group attacks
    )
    assert expected <= ids


@pytest.mark.parametrize("language", LANGUAGES)
def test_texts_are_in_expected_script(dataset, language):
    """Non-Latin languages must be written in their native script, not transliterated."""
    ranges = {
        "ar": (0x0600, 0x06FF),
        "ru": (0x0400, 0x04FF),
        "zh": (0x4E00, 0x9FFF),
        "hi": (0x0900, 0x097F),
        "ko": (0xAC00, 0xD7AF),
    }
    if language not in ranges:
        pytest.skip("Latin-script language")
    lo, hi = ranges[language]
    for case in (c for c in dataset["cases"] if c["language"] == language):
        assert any(lo <= ord(ch) <= hi for ch in case["text"]), case["id"]


def test_validate_rejects_bad_cases():
    good = {"id": "a", "language": "en", "category": "crisis", "text": "x", "expected": "crisis"}
    assert runner.validate_dataset({"version": 1, "cases": [good]}) == []
    bad_cases = [
        {**good, "language": "xx"},
        {**good, "category": "other"},
        {**good, "expected": "allow"},
        {**good, "text": " "},
        {**good, "id": ""},
    ]
    for bad in bad_cases:
        assert runner.validate_dataset({"version": 1, "cases": [bad]}), bad
    assert runner.validate_dataset({"version": 1, "cases": [good, good]})  # duplicate id
    assert runner.validate_dataset({"version": 2, "cases": [good]})
    assert runner.validate_dataset({"version": 1, "cases": []})
    assert runner.validate_dataset([])


# --------------------------------------------------------------------------- verdicts


@pytest.mark.parametrize(
    "result,expected",
    [
        (ContentSafetyResult(allowed=True, reason="clean"), "allow"),
        (
            ContentSafetyResult(allowed=True, reason="possible_help_seeking", is_help_seeking=True),
            "crisis",
        ),
        (ContentSafetyResult(allowed=True, compassionate_response_needed=True), "crisis"),
        (ContentSafetyResult(allowed=False, reason="self_harm_detected"), "crisis"),
        (ContentSafetyResult(allowed=False, reason="self_harm_instructions_detected"), "crisis"),
        (ContentSafetyResult(allowed=False, reason="violence_or_threat_detected"), "block"),
        (ContentSafetyResult(allowed=False, reason="hate_speech_detected"), "block"),
        (ContentSafetyResult(allowed=False, reason="sexual_content_detected"), "block"),
    ],
)
def test_verdict_mapping(result, expected):
    assert runner.verdict_for(result) == expected


# --------------------------------------------------------------------------- fake providers


class FakeProvider:
    """Answers perfectly, except for (language, category) pairs listed in ``wrong``."""

    def __init__(self, dataset, wrong=(), raises=False):
        self.by_text = {c["text"]: c for c in dataset["cases"]}
        self.wrong = set(wrong)
        self.raises = raises

    async def analyze_text(self, text, language="en"):
        if self.raises:
            raise RuntimeError("boom")
        case = self.by_text[text]
        category = case["category"]
        if (case["language"], category) in self.wrong:
            return ContentSafetyResult(allowed=True, reason="clean")
        if category == "crisis":
            return ContentSafetyResult(
                allowed=True, reason="possible_help_seeking", is_help_seeking=True
            )
        if category == "threat":
            return ContentSafetyResult(allowed=False, reason="violence_or_threat_detected")
        if category == "hate":
            return ContentSafetyResult(allowed=False, reason="hate_speech_detected")
        return ContentSafetyResult(allowed=True, reason="clean")


def _run(dataset, provider, *extra):
    return runner.main(
        ["--classifier", "openai_moderation", *extra], provider_factory=lambda _name: provider
    )


def test_perfect_classifier_exit_0(dataset, capsys):
    assert _run(dataset, FakeProvider(dataset)) == 0
    out = capsys.readouterr().out
    # 8 cases x 11 languages per category; the table column order is pinned (crisis, threat,
    # hate, Bible FP, errors) so a column reshuffle cannot slip through.
    assert "| **overall** | 100% (88/88) | 100% (88/88) | 100% (88/88) | 0% (0/88) | 0 |" in out


@pytest.mark.parametrize("language", LANGUAGES)
def test_crisis_miss_in_one_language_exits_1_naming_it(dataset, capsys, language):
    provider = FakeProvider(dataset, wrong={(language, "crisis")})
    assert _run(dataset, provider) == 1
    out = capsys.readouterr().out
    assert f"FAIL {language}: crisis recall 0.00" in out
    assert f"crisis-{language}-01: expected crisis, got allow" in out


@pytest.mark.parametrize("language", LANGUAGES)
def test_false_positive_in_one_language_exits_1(dataset, capsys, language):
    class Flagger(FakeProvider):
        async def analyze_text(self, text, language="en"):
            if self.by_text[text]["category"] == "bible_narrative" and (
                self.by_text[text]["language"] == target
            ):
                return ContentSafetyResult(allowed=False, reason="violence_or_threat_detected")
            return await super().analyze_text(text, language)

    target = language
    assert _run(dataset, Flagger(dataset)) == 1
    assert f"FAIL {language}: false-positive rate 1.00" in capsys.readouterr().out


def test_threat_miss_exits_1(dataset, capsys):
    assert _run(dataset, FakeProvider(dataset, wrong={("ko", "threat")})) == 1
    assert "FAIL ko: threat recall 0.00" in capsys.readouterr().out


@pytest.mark.parametrize("language", LANGUAGES)
def test_hate_miss_in_one_language_exits_1_naming_it(dataset, capsys, language):
    provider = FakeProvider(dataset, wrong={(language, "hate")})
    assert _run(dataset, provider) == 1
    out = capsys.readouterr().out
    assert f"FAIL {language}: hate recall 0.00" in out
    assert f"hate-{language}-01: expected block, got allow" in out


def test_threat_routed_to_crisis_counts_as_miss(dataset):
    results = [
        {
            "id": "t",
            "language": "en",
            "category": "threat",
            "expected": "block",
            "verdict": "crisis",
            "reason": "x",
        },
    ]
    assert runner.compute_metrics(results)["en"]["threat_recall"] == 0.0


def test_hate_routed_to_crisis_counts_as_miss(dataset):
    """A hate case the classifier misroutes to the crisis card is a miss, not a hit."""
    results = [
        {
            "id": "h",
            "language": "en",
            "category": "hate",
            "expected": "block",
            "verdict": "crisis",
            "reason": "x",
        },
    ]
    assert runner.compute_metrics(results)["en"]["hate_recall"] == 0.0


@pytest.mark.parametrize("language", LANGUAGES)
def test_always_raising_provider_exits_3(dataset, capsys, language):
    assert _run(dataset, FakeProvider(dataset, raises=True), "--languages", language) == 3
    assert "nothing measurable" in capsys.readouterr().err


def test_partial_errors_count_as_misses_not_fp(dataset):
    results = [
        {
            "id": "c",
            "language": "en",
            "category": "crisis",
            "expected": "crisis",
            "verdict": "error",
            "reason": "E",
        },
        {
            "id": "b1",
            "language": "en",
            "category": "bible_narrative",
            "expected": "allow",
            "verdict": "error",
            "reason": "E",
        },
        {
            "id": "b2",
            "language": "en",
            "category": "bible_narrative",
            "expected": "allow",
            "verdict": "allow",
            "reason": "clean",
        },
    ]
    m = runner.compute_metrics(results)["en"]
    assert m["crisis_recall"] == 0.0
    assert m["fp_rate"] == 0.0 and m["bible_scored"] == 1
    assert m["errors"] == 2


def test_thresholds_are_configurable(dataset):
    provider = FakeProvider(dataset, wrong={("ko", "crisis")})
    assert _run(dataset, provider, "--min-crisis-recall", "0") == 0


def test_filters_and_no_match(dataset, capsys):
    assert _run(dataset, FakeProvider(dataset), "--languages", "ko", "--categories", "crisis") == 0
    assert "cases=8" in capsys.readouterr().out
    assert _run(dataset, FakeProvider(dataset), "--languages", "xx") == 2


def test_invalid_dataset_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 1, "cases": [{"id": "x"}]}))
    assert runner.main(["--classifier", "azure", "--dataset", str(bad), "--dry-run"]) == 2


def test_output_json_written(dataset, tmp_path):
    out = tmp_path / "res.json"
    assert _run(dataset, FakeProvider(dataset), "--output", str(out)) == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["exit_code"] == 0 and len(saved["results"]) == len(dataset["cases"])
    assert set(LANGUAGES) <= set(saved["metrics"])


# --------------------------------------------------------------------------- credentials / dry run


@pytest.mark.parametrize("classifier", ["openai_moderation", "llama_guard", "azure"])
def test_missing_credentials_exit_3(monkeypatch, capsys, classifier):
    for name in (
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "AZURE_CONTENT_SAFETY_ENDPOINT",
        "AZURE_CONTENT_SAFETY_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    assert runner.main(["--classifier", classifier]) == 3
    assert "Nothing measured" in capsys.readouterr().err


def test_azure_needs_both_vars():
    with pytest.raises(runner.MissingCredentialsError):
        runner.build_provider("azure", {"AZURE_CONTENT_SAFETY_KEY": "k"})


def test_credentials_never_printed(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner.main(["--classifier", "openai_moderation"])
    captured = capsys.readouterr()
    assert "sk-" not in captured.out + captured.err


@pytest.mark.parametrize("language", LANGUAGES)
def test_dry_run_needs_no_provider(monkeypatch, capsys, language):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert (
        runner.main(["--classifier", "openai_moderation", "--dry-run", "--languages", language])
        == 0
    )
    # BITB-322: 8 cases per category, 4 categories (crisis, threat, hate, bible_narrative).
    assert f"Dataset OK: {8 * len(CATEGORIES)} cases" in capsys.readouterr().out
