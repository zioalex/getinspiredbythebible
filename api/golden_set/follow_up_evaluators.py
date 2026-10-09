"""Automated evaluators for suggested follow-up chips (BITB-178).

Pure functions -- no network or DB. Each check returns ``(name, passed, detail)``.
``run_all_checks`` in ``evaluators.py`` is intentionally untouched: follow-up
checks only run when a caller supplies chips.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from golden_set.models import AutomatedScore, Expectations
from utils.verse_parser import extract_all_references

CheckResult = tuple[str, bool, str]


def _load_follow_up_constants() -> tuple[int, re.Pattern[str]]:
    """Read the production chip limits from the pure ``chat/follow_ups.py`` module.

    Loaded by file path, not ``from chat.follow_ups import ...``, because importing
    through the ``chat`` package runs ``chat/__init__`` and pulls in the whole chat
    service. This keeps the checks in lock-step with production without copying.
    """
    path = Path(__file__).resolve().parent.parent / "chat" / "follow_ups.py"
    spec = importlib.util.spec_from_file_location("_follow_ups_constants", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return int(module._MAX_FOLLOW_UP_LEN), module._MARKUP_PATTERN


_MAX_FOLLOW_UP_LEN, _MARKUP_PATTERN = _load_follow_up_constants()

_MIN_CHIPS = 2
_MAX_CHIPS = 3
_WHITESPACE = re.compile(r"\s+")


def normalize_chip(text: str) -> str:
    """Case-insensitive, whitespace-normalized form used for duplicate comparison."""
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _check_count(follow_ups: list[str], expectations: Expectations) -> CheckResult:
    n = len(follow_ups)
    mode = expectations.follow_ups
    if mode == "expected":
        ok = _MIN_CHIPS <= n <= _MAX_CHIPS
        want = f"{_MIN_CHIPS}-{_MAX_CHIPS}"
    elif mode == "suppressed":
        ok = n == 0
        want = "0"
    else:
        ok = n == 0 or _MIN_CHIPS <= n <= _MAX_CHIPS
        want = f"0 or {_MIN_CHIPS}-{_MAX_CHIPS}"
    return "follow_up_count", ok, f"got {n} chips, expected {want}"


def _check_length(follow_ups: list[str]) -> CheckResult:
    too_long = [c for c in follow_ups if len(c) > _MAX_FOLLOW_UP_LEN]
    if too_long:
        return "follow_up_length", False, f"{len(too_long)} chip(s) over {_MAX_FOLLOW_UP_LEN} chars"
    return "follow_up_length", True, f"all chips <= {_MAX_FOLLOW_UP_LEN} chars"


def _check_markup(follow_ups: list[str]) -> CheckResult:
    bad = [c for c in follow_ups if _MARKUP_PATTERN.search(c)]
    if bad:
        return "follow_up_markup", False, f"markup in chip(s): {bad}"
    return "follow_up_markup", True, "no markup in chips"


def _check_unique(follow_ups: list[str]) -> CheckResult:
    normalized = [normalize_chip(c) for c in follow_ups]
    if len(set(normalized)) != len(normalized):
        return "follow_up_unique", False, "duplicate chips"
    return "follow_up_unique", True, "chips are unique"


def _check_language(follow_ups: list[str], expectations: Expectations) -> CheckResult:
    name = "follow_up_language"
    if not follow_ups:
        return name, True, "no chips, language check skipped"
    try:
        from utils.language import detect_language

        detected = detect_language(" ".join(follow_ups))
    except Exception:
        return name, True, "language detection unavailable, skipping"
    if detected == expectations.response_language:
        return name, True, f"language matches: {detected}"
    return name, False, f"expected {expectations.response_language}, detected {detected}"


_TRAILER_LEAK = re.compile(r"<!--\s*FOLLOWUPS|FOLLOWUPS\s*:")


def _check_trailer_leak(response: str) -> CheckResult:
    """Only the FOLLOWUPS trailer must be stripped; the VERSES comment legitimately stays."""
    if _TRAILER_LEAK.search(response):
        return "follow_up_no_trailer_leak", False, "answer contains a FOLLOWUPS trailer"
    return "follow_up_no_trailer_leak", True, "no trailer in answer"


def _check_fabricated_refs(follow_ups: list[str], response: str) -> CheckResult:
    name = "follow_up_no_fabricated_refs"
    cited = {str(r) for r in extract_all_references(response)}
    fabricated: list[str] = []
    for chip in follow_ups:
        for ref in extract_all_references(chip):
            if str(ref) not in cited:
                fabricated.append(str(ref))
    if fabricated:
        return name, False, f"chip reference(s) not cited in answer: {fabricated}"
    return name, True, "no fabricated references"


def check_follow_ups(
    follow_ups: list[str], response: str, expectations: Expectations
) -> list[CheckResult]:
    """Run every follow-up check and return ``(name, passed, detail)`` tuples."""
    return [
        _check_count(follow_ups, expectations),
        _check_length(follow_ups),
        _check_markup(follow_ups),
        _check_unique(follow_ups),
        _check_language(follow_ups, expectations),
        _check_trailer_leak(response),
        _check_fabricated_refs(follow_ups, response),
    ]


def check_multi_turn(
    turn1_chips: list[str], tapped: str, turn2_chips: list[str]
) -> list[CheckResult]:
    """Turn 2 must not repeat the tapped question nor turn 1's chip set verbatim."""
    tapped_norm = normalize_chip(tapped)
    repeats_tapped = any(normalize_chip(c) == tapped_norm for c in turn2_chips)
    same_set = bool(turn2_chips) and {normalize_chip(c) for c in turn1_chips} == {
        normalize_chip(c) for c in turn2_chips
    }
    return [
        (
            "follow_up_no_repeat_tapped",
            not repeats_tapped,
            "turn 2 repeats the tapped chip" if repeats_tapped else "tapped chip not repeated",
        ),
        (
            "follow_up_no_repeat_set",
            not same_set,
            "turn 2 chips identical to turn 1" if same_set else "turn 2 chips differ from turn 1",
        ),
    ]


def build_score(checks: list[CheckResult]) -> AutomatedScore:
    """Fold check tuples into an ``AutomatedScore``."""
    failed = [name for name, passed, _ in checks if not passed]
    return AutomatedScore(
        passed=not failed,
        total_checks=len(checks),
        passed_checks=len(checks) - len(failed),
        failed_checks=failed,
        details={name: {"passed": passed, "detail": detail} for name, passed, detail in checks},
    )


def run_follow_up_checks(
    follow_ups: list[str], response: str, expectations: Expectations
) -> AutomatedScore:
    """Run all follow-up checks and produce an ``AutomatedScore``."""
    return build_score(check_follow_ups(follow_ups, response, expectations))
