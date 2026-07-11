# BITB-068: Per-Language Model Fallback Chain

**Status:** 📋 Backlog
**Priority:** P2 (Medium) — quality follow-up to the qwen-endpoint override-resilience fix
**Size:** S–M (config schema change + override routing + language util + tests)
**Created:** 2026-07-11
**Follow-up to:** override-resilience fix on `claude/qwen-endpoint-error-wbypd2`
(`api/providers/openrouter.py` — overrides now flow through `_get_model_and_extra_body`
with a fallback array; commit `56f58d6`)

## User Story

As an operator serving non-English users, I want each language's model override to fall
back to *another model that also serves that language well* — not the global default —
so that when the preferred model (e.g. Qwen for Arabic) is unavailable, users still get a
high-quality answer in their language instead of a degraded one from a model with weak
support for it.

## Problem / Motivation

The override-resilience fix stopped Arabic requests from hard-failing when Qwen was routed
to a flaky/incompatible upstream (DeepInfra `429`, Novita `400 "does not support endpoint:
completions"`). It did so by giving the override the same server-side `models` fallback
array + client-side safety net the default path has.

But the fallback target is the **global** `openrouter_fallback_models`
(`meta-llama/llama-3.3-70b-instruct`), which is language-agnostic. For Arabic that is
exactly the model the override exists to avoid — the language-expansion research picked Qwen
*because* Llama 3.3's Arabic coverage is weak (`docs/language-expansion-research.md:212-223`).
So today's behaviour is:

- **Qwen healthy** → great Arabic answer ✅
- **Qwen unavailable** → degrades to Llama 3.3 → a *worse* Arabic answer (but no error) ⚠️

The degrade-to-working-model tradeoff was the right call for the urgent fix, but the ideal
is a fallback that stays in-language.

### Current shape

- `api/config.py:53` — `language_model_overrides: str = "ar=qwen/qwen-2.5-72b-instruct"`,
  a flat comma-separated `lang=model` map (one model per language).
- `api/utils/language.py:464` — `get_model_override_for_language()` parses that map and
  returns a single model string (or `None`).
- `api/providers/openrouter.py` — `_get_model_and_extra_body(primary_override=...)` puts the
  override first, then appends `self.fallback_models` (the global list). There is no
  per-language fallback concept.

## Proposed Approach

1. **Config schema.** Support a per-language fallback chain. Two candidate encodings
   (decide during grooming):
   - Extend the existing value with a chain separator, e.g.
     `ar=qwen/qwen-2.5-72b-instruct>cohere/command-r-plus` (primary `>` fallback[s]); or
   - Add a sibling setting `language_fallback_models` mapping `lang=model[,model...]`,
     leaving `language_model_overrides` as the primary map.
   Prefer whichever keeps the env-var UX simplest and is easiest to validate.
2. **Language util.** Return the resolved *chain* for a language (primary + its fallbacks),
   not just the primary. Keep `get_model_override_for_language()` returning the primary for
   back-compat, and add a `get_model_fallback_chain_for_language()` (or return a small
   dataclass/tuple). Empty/malformed entries fall through to today's behaviour.
3. **Override routing.** Thread the language-specific fallback chain into
   `_get_model_and_extra_body` so, when an override is active, the server-side `models`
   array and the client-side fallback loop use the language chain, falling through to the
   global `fallback_models` only as a last resort. Reuse the existing de-dupe so no model is
   listed twice.
4. **Default config.** Seed a sensible Arabic fallback (an in-language-capable model from
   the research doc) so the default deployment benefits without extra env config.

## Acceptance Criteria

- [ ] Per-language fallback chains are configurable via env (no code change to add a
      language or reorder its chain).
- [ ] When a language override's primary model is unavailable (429 / `does not support
      endpoint` 400 / 404 / timeout), the request falls back to the *language-specific*
      fallback(s) first, and only then to the global `fallback_models`.
- [ ] `get_model_override_for_language()` behaviour is unchanged for callers that only need
      the primary; the chain is exposed via a new accessor.
- [ ] The circuit breaker still only tracks the true default primary (unchanged from the
      qwen fix) — language chains never pollute it.
- [ ] Tests: language util resolves chains (including empty/malformed → fallthrough); the
      OpenRouter override path builds the `models` array from the language chain and, on a
      primary failure, falls back client-side through the language chain before the global
      list. Mirror the existing override/fallback tests in
      `api/tests/test_providers_coverage.py` and the override tests in
      `api/tests/test_language.py`.

## Out of Scope

- Provider-level pinning/ignoring specific upstreams (e.g. `provider.ignore: ["Novita"]`) —
  a different lever, tracked separately if the endpoint-incompatibility recurs.
- Adding new languages or changing which model is each language's *primary* override.

## Notes

- Research reference for in-language fallback candidates:
  `docs/language-expansion-research.md` (§ model coverage/pricing table).
- The urgent resilience fix this builds on: `_get_model_and_extra_body(primary_override=...)`
  + breaker-scoping-to-true-primary + treating `"does not support endpoint"` as
  model-unavailable, in `api/providers/openrouter.py`.
