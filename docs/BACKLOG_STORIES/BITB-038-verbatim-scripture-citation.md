# BITB-038: Quote Scripture Verbatim — Never Paraphrase a Cited Verse

**Status:** ✅ Done
**Size:** S (< 4 hours)
**Priority:** P1
**Created:** 2026-06-04
**Completed:** 2026-06-09

## Problem

An Italian user received a response quoting Galatians 5:22-23 as *"la frutta dello
Spirito"* (plural/wrong gender) when the Italian Bible reads *"il frutto dello Spirito"*
(singular/correct). The LLM was re-wording — or re-translating — verse text it received
in the Scripture Context, subtly altering the meaning.

Root cause: the system prompts told the LLM to use scripture from the context but did
not explicitly forbid paraphrasing. Without a hard rule, the model regularly re-phrases
cited verses.

## Implementation

Added `SCRIPTURE_FIDELITY_GUIDANCE` constant (`api/chat/prompts.py`) and appended it to
all three prompt-builder functions:

- `get_system_prompt()` — general chat
- `get_verse_lookup_prompt()` — direct verse requests
- `get_prayer_lookup_prompt()` — prayer / passage requests

The guidance:

- Requires verbatim reproduction of verse text from the Scripture Context
- Forbids paraphrasing, re-wording, modernising, summarising, or re-translating
- Calls out singular/plural and grammatical agreement explicitly
- Includes the Italian "il frutto" example as a concrete illustration
- Instructs the model not to invent verse text when no context is provided

Also added an inline bullet to `SYSTEM_PROMPT_TEMPLATE` and a step in
`VERSE_LOOKUP_SYSTEM_PROMPT` reinforcing the verbatim rule so it appears twice in
the assembled prompt.

## Tests

`TestScriptureFidelityGuidance` class in `api/tests/test_chat_coverage.py` — 10 tests:

| Test | Asserts |
|------|---------|
| `test_guidance_constant_forbids_paraphrase` | "verbatim" and "paraphrase" in guidance |
| `test_guidance_constant_requires_exact_wording` | "EXACTLY" and "Scripture Context" in guidance |
| `test_guidance_covers_translation_and_number` | re-translate and singular/plural covered |
| `test_system_prompt_contains_fidelity_guidance_english` | English system prompt has guidance |
| `test_system_prompt_fidelity_guidance_for_all_languages` | All 11 locales include guidance |
| `test_verse_lookup_prompt_contains_fidelity_guidance` | Verse-lookup prompt has guidance |
| `test_prayer_lookup_prompt_contains_fidelity_guidance` | Prayer-lookup prompt has guidance |
| `test_inline_bullet_reinforces_verbatim_rule` | "Quote them verbatim" in system prompt |
| `test_verse_lookup_step_reinforces_verbatim_rule` | "VERBATIM" in verse-lookup prompt |
| `test_guidance_mentions_italian_example` | "il frutto" present in guidance |
| `test_guidance_forbids_inventing_verse` | no-fabrication rule present in guidance |

## Acceptance Criteria

- [x] All three prompt builders include the verbatim quoting rule
- [x] Prompt instructs the model not to fabricate verse wording when absent
- [x] Italian "il frutto" example is explicit in the guidance
- [x] Unit tests assert the verbatim rule in all three prompt builders
- [x] Full backend test suite passes
