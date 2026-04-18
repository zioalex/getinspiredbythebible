"""Automated evaluators for golden set test responses.

Each check function takes a response string and expectations, returns (passed, detail).
The run_all_checks function orchestrates all checks and produces an AutomatedScore.
"""

import re

from golden_set.models import AutomatedScore, Expectations

# Regex for Bible references like "John 3:16", "1 Corinthians 13:4", "Psalm 23:1"
VERSE_REFERENCE_PATTERN = re.compile(r"\b(\d\s+)?[A-Z][a-z]+(?:\s+[a-z]+)?\s+\d+:\d+(?:-\d+)?\b")

# Patterns indicating source attribution (from prompts.py lines 14-23)
SOURCE_BIBLICAL_PATTERNS = [
    re.compile(r"(?:this\s+is\s+)?from\s+the\s+bible", re.IGNORECASE),
    re.compile(r"biblical\s+(?:prayer|text|passage|verse|content)", re.IGNORECASE),
    re.compile(r"found\s+in\s+(?:the\s+)?(?:bible|scripture)", re.IGNORECASE),
    re.compile(r"(?:book\s+of|gospel\s+of|epistle|psalm)", re.IGNORECASE),
]

SOURCE_NON_BIBLICAL_PATTERNS = [
    re.compile(r"not\s+(?:from|in)\s+the\s+bible", re.IGNORECASE),
    re.compile(r"not\s+(?:a\s+)?biblical", re.IGNORECASE),
    re.compile(r"not\s+(?:found\s+)?in\s+scripture", re.IGNORECASE),
    re.compile(r"is\s+not\s+(?:from|part\s+of)\s+(?:the\s+)?(?:bible|scripture)", re.IGNORECASE),
]


def check_scripture_presence(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check if response contains Bible verse references."""
    if not expectations.must_contain_scripture:
        return True, "scripture check not required"

    refs = VERSE_REFERENCE_PATTERN.findall(response)
    count = len(refs)

    if count < expectations.min_verses_cited:
        return False, f"found {count} references, expected >= {expectations.min_verses_cited}"

    if count == 0:
        return False, "no scripture references found"

    return True, f"found {count} scripture references"


def check_expected_books(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check if response references at least one expected book."""
    if not expectations.expected_books:
        return True, "no expected books specified"

    response_lower = response.lower()
    for book in expectations.expected_books:
        if book.lower() in response_lower:
            return True, f"found expected book: {book}"

    return False, f"none of {expectations.expected_books} found in response"


def check_forbidden_content(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check that response does not contain forbidden phrases."""
    if not expectations.must_not_contain:
        return True, "no forbidden content specified"

    response_lower = response.lower()
    found = []
    for phrase in expectations.must_not_contain:
        if phrase.lower() in response_lower:
            found.append(phrase)

    if found:
        return False, f"forbidden content found: {found}"

    return True, "no forbidden content found"


def check_required_content(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check that response contains all required phrases."""
    if not expectations.must_contain:
        return True, "no required content specified"

    response_lower = response.lower()
    missing = []
    for phrase in expectations.must_contain:
        if phrase.lower() not in response_lower:
            missing.append(phrase)

    if missing:
        return False, f"required content missing: {missing}"

    return True, "all required content found"


def check_source_statement(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check that source is stated in the first 500 characters of the response."""
    if not expectations.source_statement_required:
        return True, "source statement not required"

    first_500 = response[:500]

    if expectations.source_is_biblical is True:
        for pattern in SOURCE_BIBLICAL_PATTERNS:
            if pattern.search(first_500):
                return True, "biblical source statement found"
        return False, "no biblical source statement in first 500 chars"

    if expectations.source_is_biblical is False:
        for pattern in SOURCE_NON_BIBLICAL_PATTERNS:
            if pattern.search(first_500):
                return True, "non-biblical source statement found"
        return False, "no non-biblical source statement in first 500 chars"

    # source_is_biblical is None: just check any source statement exists
    all_patterns = SOURCE_BIBLICAL_PATTERNS + SOURCE_NON_BIBLICAL_PATTERNS
    for pattern in all_patterns:
        if pattern.search(first_500):
            return True, "source statement found"

    return False, "no source statement in first 500 chars"


def check_response_language(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check that response is in the expected language."""
    try:
        from utils.language import detect_language

        detected = detect_language(response)
    except Exception:
        return True, "language detection unavailable, skipping"

    if detected == expectations.response_language:
        return True, f"language matches: {detected}"

    return False, f"expected {expectations.response_language}, detected {detected}"


def check_response_length(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check that response does not exceed max length."""
    if expectations.max_response_length is None:
        return True, "no max length specified"

    length = len(response)
    if length > expectations.max_response_length:
        return False, f"response length {length} exceeds max {expectations.max_response_length}"

    return True, f"response length {length} within limit"


def check_situation_acknowledgment(
    response: str, expectations: Expectations, input_message: str
) -> tuple[bool, str]:
    """Check that response acknowledges the user's situation early on."""
    if not expectations.must_acknowledge_situation:
        return True, "situation acknowledgment not required"

    # Extract keywords from input (words > 3 chars, not common words)
    stop_words = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "have",
        "been",
        "from",
        "about",
        "very",
        "what",
        "does",
        "tell",
        "know",
    }
    keywords = [
        w.lower()
        for w in re.findall(r"\b\w+\b", input_message)
        if len(w) > 3 and w.lower() not in stop_words
    ]

    if not keywords:
        return True, "no keywords to check"

    # Check first 500 chars of response for any input keywords
    first_500 = response[:500].lower()
    found = [kw for kw in keywords if kw in first_500]

    if found:
        return True, f"situation acknowledged with keywords: {found}"

    return False, "no input keywords found in first 500 chars of response"


def run_all_checks(
    response: str, expectations: Expectations, input_message: str = ""
) -> AutomatedScore:
    """Run all automated checks and produce an AutomatedScore."""
    checks = {
        "scripture_presence": check_scripture_presence(response, expectations),
        "expected_books": check_expected_books(response, expectations),
        "forbidden_content": check_forbidden_content(response, expectations),
        "required_content": check_required_content(response, expectations),
        "source_statement": check_source_statement(response, expectations),
        "response_language": check_response_language(response, expectations),
        "response_length": check_response_length(response, expectations),
        "situation_acknowledgment": check_situation_acknowledgment(
            response, expectations, input_message
        ),
    }

    failed = [name for name, (passed, _) in checks.items() if not passed]
    details = {name: detail for name, (_, detail) in checks.items()}

    return AutomatedScore(
        passed=len(failed) == 0,
        total_checks=len(checks),
        passed_checks=len(checks) - len(failed),
        failed_checks=failed,
        details=details,
    )
