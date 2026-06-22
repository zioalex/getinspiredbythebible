# BITB-053: Ground Unquoted / Paraphrased Verse Citations

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — scripture fidelity; closes the largest remaining grounding gap
**Size:** M (1-2 days)
**Created:** 2026-06-19
**Parent / related:** verse grounding (`api/chat/verse_grounding.py`), BITB-038 (verbatim quoting)

## User Story

As a user reading a Bible answer in any language, I want the scripture the assistant
presents to match the real verse **even when it is not wrapped in quotation marks**, so
that paraphrased "citations" can't drift from the canonical text.

## Problem

Post-generation grounding (`ground_response` in `api/chat/verse_grounding.py`) only rewrites
text that `extract_inline_quotes` finds **inside quotation marks adjacent to a reference**.
When the model presents scripture as an *unquoted paraphrase* — e.g. Italian
`In Isaia 41:10 Dio ci dice di non temere perché Lui ci rende forti` — there is no quoted
span to compare or replace, so grounding does nothing and the paraphrase reaches the user as
if it were the verse.

This is the largest remaining class of "the citation doesn't match the DB" once the
parenthesized-reference parsing bug is fixed (the paren fix ensures the verse *resolves*;
this story ensures *unquoted* renderings are also handled).

## Scope

In scope:

1. Detect reference-adjacent verse prose that is **not** quoted (a sentence that names a
   reference and then renders its content), language-aware.
2. Decide and implement the action: either (a) wrap + correct the rendered span to canonical
   text, or (b) append/surface the canonical verse (e.g. a quoted clause) so the user sees the
   real wording — with the reference preserved.
3. **Strong false-positive guards** — must never alter ordinary discussion *about* a verse
   ("John 3:16 is about God's love"); only a passage that actually restates the verse.
4. Reuse `_normalize_for_compare` / similarity from `verse_grounding.py`; keep the function
   pure (no DB) consistent with the existing design.

Out of scope:

- Re-architecting the quoted-span path (works today).
- Forcing the model to always quote (a prompt-only lever, separate).

## Acceptance Criteria

- [ ] Unquoted, reference-adjacent paraphrase of a resolved verse is corrected/surfaced to
      canonical text, with the reference preserved.
- [ ] Ordinary discussion *about* a verse is never altered (negative tests).
- [ ] **Parametrized cross-language tests across all 11 languages** (per AGENTS.md
      "Multilingual & Multi-Version Correctness"), incl. CJK/RTL, plus version-faithfulness.
- [ ] Integration test through `chat()` / `chat_stream()` proving end-to-end behaviour.

## Files / Config

| Item | Location |
|---|---|
| Grounding logic | `api/chat/verse_grounding.py` |
| Inline detection helpers | `api/utils/verse_parser.py` |
| Wiring | `api/chat/service.py` (`_apply_verse_grounding`) |
| Tests | `api/tests/test_verse_grounding.py`, `api/tests/test_chat_coverage.py` |

## Related

- **BITB-038** — verbatim quoting of *quoted* verses (prompt-only).
- Parenthesized-reference parsing fix (this story's prerequisite — ensures the verse resolves).
