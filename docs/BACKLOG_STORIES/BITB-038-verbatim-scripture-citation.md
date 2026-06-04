# BITB-038: Quote Scripture Verbatim — Never Paraphrase a Cited Verse

**Status:** 🎯 Todo
**Priority:** P1 (High) — correctness/trust defect in the app's core promise
**Size:** S (< 4 hours)
**Created:** 2026-06-04

## User Story

As a user who trusts this app to quote the Bible accurately, I want every Bible
verse the assistant presents as a direct quotation to match the real wording of
my selected translation, so that I am never shown an altered citation that
changes the meaning of scripture.

## Problem

A user in Italian was shown:

> "In Galati 5:22-23, la Bibbia descrive la **'frutta'** dello Spirito Santo…"

The Italian Bible reads **"il frutto dello Spirito"** (singular — *the fruit*),
not **"la frutta"** (*the fruits* / produce). The word choice changes the
meaning, and — more importantly — it is presented as a direct biblical
quotation when it is not what the Bible actually says.

### Root cause

The verse text shown to users is **LLM-generated prose**, not a stored string.
Verses are retrieved correctly and injected into the prompt under a
"Scripture Context" block by `build_search_context_prompt()`
(`api/chat/prompts.py:418`). However, the system prompts only instruct the model
to *use the provided verses as a source* and to *avoid inventing references*
(`api/chat/prompts.py:44-48`). There is **no rule forbidding the model from
re-wording, paraphrasing, or re-translating the verse text** when it quotes it.
So the model reproduces scripture from its own training/paraphrase rather than
copying the exact text supplied to it — producing "frutta" instead of "frutto".

This is a content-fidelity defect: a Bible app that misquotes the Bible
undermines its central value proposition.

## Proposed Changes

The fix is **prompt-level** and reuses the existing "append a shared guidance
block" pattern already used by `BIBLE_VERSION_GUIDANCE` (`api/chat/prompts.py:308`).

### 1. Add a shared scripture-fidelity guidance block

Add a new constant in `api/chat/prompts.py`, e.g. `SCRIPTURE_FIDELITY_GUIDANCE`,
instructing the model:

- When presenting a Bible verse as a **direct quotation**, reproduce the verse
  text **word-for-word exactly** as it appears in the "Scripture Context" — do
  **not** paraphrase, summarise, modernise, re-translate, or otherwise change
  the wording, including articles and singular/plural forms (e.g. Italian
  *"il frutto"*, never *"la frutta"*).
- The quoted words must be a real quotation of the provided verse. Only the
  surrounding warm/explanatory prose is the model's own.
- If the exact verse text is **not** present in the Scripture Context, do not
  reconstruct or guess the wording. Refer to the passage and its reference, or
  describe it, rather than presenting reconstructed text as a verbatim quote.

### 2. Append it to all three prompt builders

Wire the new block into the three builders the same way `BIBLE_VERSION_GUIDANCE`
is appended (`api/chat/prompts.py:362-415`):

- `get_system_prompt()`
- `get_verse_lookup_prompt()`
- `get_prayer_lookup_prompt()`

### 3. Tighten the inline references

Point the existing "Using Scripture Context" bullets (`prompts.py:44-48`) and the
verse-lookup "Present the verse" step (`prompts.py:95`) at the new verbatim rule
so the instruction is reinforced where verses are introduced.

## Files to Modify

| File | Change |
|---|---|
| `api/chat/prompts.py` | Add `SCRIPTURE_FIDELITY_GUIDANCE`; append it in `get_system_prompt`, `get_verse_lookup_prompt`, `get_prayer_lookup_prompt`; reinforce inline bullets at lines 44-48 and 95 |
| `api/tests/` (prompt tests) | Add a test asserting the verbatim/no-paraphrase rule is present in the output of all three `get_*_prompt(...)` builders |

## Acceptance Criteria

- [ ] All three system prompts (`get_system_prompt`, `get_verse_lookup_prompt`,
      `get_prayer_lookup_prompt`) include an explicit rule to quote scripture
      verbatim from the Scripture Context and never paraphrase/re-translate it.
- [ ] The prompt instructs the model not to fabricate verse wording when the verse
      text is absent from the Scripture Context.
- [ ] Manual check: an Italian query about the fruit of the Spirit returns the
      singular wording *"il frutto dello Spirito"* (not *"la frutta"*) when the
      Italian verse is in context.
- [ ] A unit test asserts the verbatim rule appears in all three prompt builders.
- [ ] Full backend test suite passes.

## Out of Scope

- Changing scripture retrieval, ranking, or which translation is selected.
- Post-generation verbatim enforcement (e.g. validating the model's quote against
  the DB text) — a possible follow-up if prompt-level guidance proves insufficient.
- Any Bible data/translation import changes (`data/bible/`, `scripts/load_bible.py`).

## Notes

This is a prompt-robustness fix; it strongly reduces but cannot mathematically
guarantee model behaviour. It is the correct lowest-risk first fix for the
reported defect. If misquotes recur, the out-of-scope post-generation validation
becomes a follow-up story.

## Assignee

backend-expert
