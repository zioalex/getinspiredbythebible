"""Parse and sanitize the LLM's suggested-follow-up-questions trailer (BITB-080).

The system prompt (see FOLLOW_UP_SUGGESTIONS_GUIDANCE in api/chat/prompts.py)
asks the model to append a machine-readable HTML comment after its answer:

    <!-- FOLLOWUPS: question one|question two|question three -->

This module is a pure function -- no DB or network access -- so it is fast and
trivially testable, mirroring verse_grounding.py's shape.
"""

from __future__ import annotations

import re

# Matches every FOLLOWUPS trailer in the text (DOTALL so a suggestion
# containing a stray newline doesn't truncate the match), defensively -- the
# model should only ever emit one, but stripping every occurrence means a
# duplicate can never leak into the visible answer.
_FOLLOWUPS_PATTERN = re.compile(r"<!--\s*FOLLOWUPS:\s*(.*?)\s*-->", re.DOTALL)

# A suggestion this long can't fit the "one or two lines on a phone" AC, and a
# truncated question reads worse than a dropped one -- so oversized
# suggestions are dropped, never cut short. Sized in code points to be fair to
# languages whose glyphs render wider (German, CJK) than the ~60-char English
# target the prompt asks for.
_MAX_FOLLOW_UP_LEN = 120

# A raw markdown/HTML fragment slipping into a suggestion (the model echoing
# its own formatting) would render literally inside a plain chip button, so
# any suggestion containing one of these is dropped rather than sanitized.
_MARKUP_PATTERN = re.compile(r"[<>]|\*\*|__|`")

# Leading list markers ("- ", "1. ", "* ") the model sometimes adds despite
# the "|"-separated instruction.
_LEADING_MARKER_PATTERN = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")

_WHITESPACE_PATTERN = re.compile(r"\s+")


def _clean_suggestion(raw: str) -> str | None:
    """Normalize one candidate suggestion, or return None if it should be dropped."""
    text = _LEADING_MARKER_PATTERN.sub("", raw.strip())
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    if not text or len(text) > _MAX_FOLLOW_UP_LEN:
        return None
    if _MARKUP_PATTERN.search(text):
        return None
    return text


def split_follow_ups(text: str) -> tuple[str, list[str]]:
    """Strip every FOLLOWUPS trailer from *text* and parse its suggestions.

    Returns ``(body, suggestions)`` where ``body`` is *text* with all
    FOLLOWUPS comments removed (and the whitespace they leave behind
    collapsed) and ``suggestions`` is 0, 2, or 3 cleaned strings -- never 1:
    a single surviving suggestion is dropped entirely rather than shown alone,
    since the acceptance criteria call for "2-3", and one orphan chip reads
    worse than none. Never raises; a malformed or absent trailer yields an
    empty list.
    """
    matches = list(_FOLLOWUPS_PATTERN.finditer(text))
    if not matches:
        return text, []

    body = _FOLLOWUPS_PATTERN.sub("", text)
    # Collapse the blank line(s) the removed trailer(s) leave behind, but
    # don't touch other whitespace in the answer itself.
    body = re.sub(r"[ \t]*\n\s*\n\s*$", "", body).rstrip()

    # Use the first match's payload; a second FOLLOWUPS comment would be a
    # model error, not two independent suggestion sets to merge.
    payload = matches[0].group(1)
    parts = re.split(r"[|｜]", payload) if re.search(r"[|｜]", payload) else payload.splitlines()

    seen: set[str] = set()
    suggestions: list[str] = []
    for part in parts:
        cleaned = _clean_suggestion(part)
        if cleaned is None:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(cleaned)
        if len(suggestions) == 3:
            break

    if len(suggestions) < 2:
        return body, []
    return body, suggestions
