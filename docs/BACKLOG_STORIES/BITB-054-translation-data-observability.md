# BITB-054: Per-Translation Data Observability + Honest Handling of Unresolvable Citations

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — correctness/observability; prevents silent ungrounded scripture
**Size:** M (1-2 days)
**Created:** 2026-06-19
**Parent / related:** verse grounding (`api/chat/verse_grounding.py`), `scripts/load_bible.py`

## User Story

As the maintainer, I want to know — and the app to behave honestly — when a cited verse
cannot be resolved in the user's translation, so that a missing/incomplete translation never
shows up as silently hallucinated scripture.

## Problem

When a cited reference does not resolve to DB text for the user's translation (the translation
isn't loaded, is partially loaded, or has no embeddings so semantic search returns nothing),
two things happen silently:

1. Search yields **no Scripture Context**, so the model free-generates the verse from memory.
2. `_resolve_cited_verses` returns nothing → grounding classifies the quote `unresolved` and,
   with `grounding_strip_unresolved=False` (default), **leaves the model's text untouched**.

There is no easy way to confirm what's actually loaded (the diagnostic is a manual SQL snippet
in `NEXT_STEPS.md`), and the `unresolved` path is invisible to users. This was the leading
hypothesis while debugging the Italian "citation doesn't match the DB" report.

## Scope

In scope:

1. **Diagnostic** — a queryable surface (admin route and/or startup log) reporting, per
   translation: total verses and verses-with-embeddings (reuse the SQL in `NEXT_STEPS.md`:
   `SELECT translation, COUNT(*), COUNT(embedding) FROM verses GROUP BY translation`).
2. **Startup / CI guard** — warn (loudly, with a metric) when a *supported* UI language's
   translation has zero verses or zero embeddings, so an unloaded language can't ship unnoticed.
3. **Behaviour decision for `unresolved` citations** — pick and implement one of:
   fall back to a default translation's canonical text, strip the unverifiable quote
   (`grounding_strip_unresolved`), or surface "this verse isn't available in <language> yet".
   Make it configurable; default chosen for least user harm.

Out of scope:

- Actually sourcing/loading missing translation data (operational; tracked separately).

## Acceptance Criteria

- [ ] Per-translation verse + embedding counts available via a diagnostic (route or log).
- [ ] Startup/CI warning + metric when a supported language has no usable verse data.
- [ ] `unresolved` citations handled per the chosen, configurable behaviour (with tests for
      each mode), across all 11 languages.
- [ ] Grounding `reason=unresolved` is observable (metric/log already emitted — assert it).

## Files / Config

| Item | Location |
|---|---|
| Grounding (`unresolved` path) | `api/chat/verse_grounding.py`, `api/chat/service.py` |
| Settings | `api/config.py` (`grounding_strip_unresolved`, new behaviour flag) |
| Repository / counts | `api/scripture/repository.py` |
| Loader | `scripts/load_bible.py`, `NEXT_STEPS.md` (diagnostic SQL) |
| Tests | `api/tests/` |

## Related

- Verse grounding feature; surfaced while debugging the Italian citation report.
- **BITB-052** — reference normalization (versification can also cause resolution misses).
