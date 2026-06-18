# BITB-045: Typo-Tolerant Queries with Clarification Fallback

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — quality of answers on imperfect input
**Size:** S (< 4 hrs)
**Created:** 2026-06-12
**Source:** Beta tester feedback (Oliver Osthoever, 2026-06-11)

## User Story

**As a** user who types quickly and makes spelling mistakes (especially in German),
**I want** the app to understand my likely intended meaning instead of giving up,
**so that** a query like "reichsheilugtm bet el" is answered as "Reichsheiligtum Bet-El"
rather than returning a generic "I don't understand".

## Problem

A tester sent two near-identical questions:

- `"reichsheiligtum bet-el meine ich"` → produced a complete, accurate answer about Bet-El.
- `"was ist das reichsheilugtm bet el"` (one typo: *reichsheilugtm*) → produced a generic
  "Es tut mir leid, aber ich verstehe Ihre Frage nicht ganz…" non-answer.

The LLM is not instructed to interpret obvious misspellings before answering, so a single typo
derails the response. Separately, when a user highlights a **specific nuance** in their question
(see BITB-050 / the Amos example), the model gives a generic overview instead of addressing the
point raised.

## Approach

Augment the system prompts in `api/chat/prompts.py` with explicit guidance:

1. **Handling typos** — silently infer the most likely intended meaning of misspelled words and
   answer on that basis; do not comment on the typo or ask the user to retype.
2. **Clarification fallback** — only when the meaning is *still* genuinely ambiguous after typo
   interpretation, ask one short clarifying question in the user's language (this complements the
   existing "When the Request Is Unclear" guidance, which targets vague/short messages).
3. **Address the user's specific focus** — when the question raises a specific detail or nuance,
   address it directly and first, before broadening to general themes. (Shared with BITB-050.)

## Acceptance Criteria

- [ ] `"was ist das reichsheilugtm bet el"` → answered about Bet-El as a holy site, with no remark
      about the misspelling.
- [ ] A genuinely ambiguous query (multiple plausible meanings even after typo correction) →
      one short clarifying question in the user's language.
- [ ] Existing "vague/short message → ask one gentle question" behaviour is preserved.
- [ ] The typo-tolerance guidance is present in `SYSTEM_PROMPT_TEMPLATE`,
      `VERSE_LOOKUP_SYSTEM_PROMPT`, and `PRAYER_LOOKUP_SYSTEM_PROMPT`.
- [ ] Test asserts the rendered German system prompt contains the typo-tolerance instruction.

## Files / Config

| Item | Location |
|---|---|
| System prompts | `api/chat/prompts.py` (`SYSTEM_PROMPT_TEMPLATE`, `VERSE_LOOKUP_SYSTEM_PROMPT`, `PRAYER_LOOKUP_SYSTEM_PROMPT`) |
| Prompt builders | `api/chat/prompts.py` (`get_system_prompt`, `get_verse_lookup_prompt`, `get_prayer_lookup_prompt`) |
| Test | `api/tests/test_chat_coverage.py` (or a new `test_prompts_typo_tolerance.py`) |

## Implementation Notes

Insert a `## Handling Typos and Spelling Errors` section and an
`## Addressing the User's Specific Focus` section into the prompt templates. The change is
prompt-only — no routing, model, or data changes. Keep instructions language-agnostic (the
templates already enforce the response language separately).

## Testing

```python
def test_german_system_prompt_includes_typo_tolerance():
    prompt = get_system_prompt("de")
    assert "spelling" in prompt.lower() or "typo" in prompt.lower()
```

Manual: send `"was ist das reichsheilugtm bet el"` and confirm a substantive Bet-El answer.

## Related

- **BITB-050** — shares the "address the user's specific focus" prompt instruction.
