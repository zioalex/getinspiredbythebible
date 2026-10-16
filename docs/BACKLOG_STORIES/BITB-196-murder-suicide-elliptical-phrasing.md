# BITB-196: Murder-Suicide Elliptical Phrasing Takes the Compassionate Path

**Status:** 🔍 In Review
**Size:** M
**Created:** 2026-10-13

## Problem

Follow-up to BITB-185 v2: "I want to kill myself and my family", "...and take everyone with me" and the fr/pt/ar equivalents match a self-harm span, and the remaining words ("my family", "everyone") are not violence keywords, so the fallback takes the compassionate path without consulting the classifier. Decide whether to route these to the ambiguity branch (classifier plus crisis default) and implement it.

## Acceptance criteria

- [x] Decision recorded: route murder-suicide phrasing to the ambiguous branch (or document why not)
- [x] Elliptical phrasings blocked or classified in all 11 languages (parametrized)
- [x] Plain self-harm ("I want to kill myself") stays compassionate without an LLM call

## Decision (2026-10-16)

Route murder-suicide / elliptical third-party phrasing to the **ambiguous branch** of
`_full_keyword_fallback`: the classifier is consulted (SELF_HARM -> compassionate); any other
verdict, or classifier disabled/down -> crisis-resources block. They are deliberately NOT
hard-violence terms (no classifier skip), because "my family" after a self-harm span is often
benign. Plain self-harm ("I want to kill myself") is unchanged: compassionate, no LLM call.

## Implementation

- `api/utils/security.py`: `MURDER_SUICIDE_PATTERNS` (all 11 languages) matching only the
  third-party part (`and my family`, `and everyone`, `take everyone with me`, `murder-suicide`,
  ...), a clause-end guard (so "my family doesn't care" does not match), lookbehinds (so
  "pray for me and my family" does not match), `find_murder_suicide_matches()`. Added de
  (`mich und meine Familie umbringen`) and zh (`带着全家一起死`) self-harm patterns for split/
  non-contiguous forms.
- `api/utils/content_safety.py`: branch (b) adds those matches to the ambiguity set without the
  self-harm-span containment filter; log field `murder_suicide`.
- `api/tests/test_murder_suicide_fallback.py`: parametrized across 11 languages.

## Known limitations

- Phrasings without a clause end after the target ("...and my family because ...") are not caught.
- Patterns are not native-speaker reviewed.

## Note (from BITB-185 v2 verification)

Optionally also refuse a SELF_HARM override when a third-party target follows a method word
(`kill|murder|shoot` + `my|his|her|them|everyone|people`). Verifier examples: "kill myself and
kill my wife", "get a gun to shoot my coworkers".
