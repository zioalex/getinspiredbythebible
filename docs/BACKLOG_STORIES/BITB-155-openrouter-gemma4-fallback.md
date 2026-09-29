# BITB-155: OpenRouter Model Refresh — Paid Llama 3.3 Primary + Gemma 4 31B Cross-Provider Fallback

**Status:** 🚧 In Progress
**Priority:** P1 (High) — the configured primary model no longer exists on OpenRouter
**Size:** S (< 4 hrs — config + docs + scripts, no app-logic change)
**Created:** 2026-09-15
**Follow-up to:** BITB-154 (same resilience theme, applied to the app's own LLM provider)

## User Story

As an operator of the Vox Quieta Bible-study app, I want the configured OpenRouter
primary and fallback models to actually exist and stay within our Zero Data
Retention (ZDR) posture, so that chat requests succeed and user data is never used
for model training.

## Problem / Motivation

`OPENROUTER_MODEL` defaulted to `meta-llama/llama-3.3-70b-instruct:free`, which
OpenRouter removed from its catalog (July 2026 deprecation wave — verified absent
from both the live `/api/v1/models` endpoint and models.dev). Every fresh deploy
therefore pointed its primary at a non-existent model.

The fallback default (`meta-llama/llama-3.3-70b-instruct`, paid) still exists but
is the *same model on the same provider* — a Meta-side outage defeats both tiers.
Same-provider fallback is not resilience.

Hard constraint (operator requirement): **ZDR must be preserved — no training on
user data.** This eliminates most free models: all NVIDIA free tiers demand a
training opt-in, and all Google free tiers demand a ZDR waiver (verified live with
the production API key). The only free models that pass ZDR are the three
`inclusionai/ling-3.0-flash-*:free` variants.

## Research (evidence)

Full model-by-model audit against live OpenRouter + models.dev (368 OpenRouter
models checked). Headline results:

| Model | Status | Notes |
|---|---|---|
| `meta-llama/llama-3.3-70b-instruct:free` (old primary) | ❌ Removed | July 2026 deprecation wave |
| `google/gemma-2-9b-it:free`, `mistralai/mistral-7b-instruct:free` (verify-script refs) | ❌ Removed | Same wave |
| `meta-llama/llama-3.3-70b-instruct` (paid) | ✅ Exists | $0.10/$0.32 per 1M tokens, ZDR ✅ |
| `google/gemma-4-31b-it` (paid) | ✅ Exists | $0.09/$0.34 per 1M, ZDR ✅, 262K ctx, 140+ langs |
| `inclusionai/ling-3.0-flash-sante:free` | ✅ Exists, ZDR ✅ | Only free ZDR-compatible family |

Live biblical-Q&A test (Prodigal Son / forgiveness, EN + DE + IT) with reasoning
disabled:

- **Paid Gemma 4 31B**: flawless DE/IT, theologically accurate verse citations
  (Luke 15:20-24, Romans 5:8, Acts 3:19…), ~$0.00019 per chat. 9–14 s per answer.
- **Free Ling Sante**: good quality, minor DE vocabulary quirks, 2.5–2.9 s.
  Viable zero-cost alternative; kept as the documented free option, not the default.

Rejected: Nemotron 3 Ultra free (55B active but 82 s / 3 tok/s — unusable for
chat); Nemotron 3.5 Lightning free (blocked by training opt-in under ZDR);
Gemma 4 31B free (blocked by ZDR waiver under ZDR).

## Decision

- **Primary:** `meta-llama/llama-3.3-70b-instruct` (paid, same quality as before)
- **Fallback:** `google/gemma-4-31b-it` (paid, Google provider → genuine
  cross-provider resilience, near-identical pricing, tested EN/DE/IT)

Fallback cost at ~5% activation is negligible (~$0.02 / 100 chats).

## Changes

- `api/config.py`, `api/providers/openrouter.py` — defaults + comments
- `scripts/env-manifest.yaml`, all `docker-compose*.yml`, `.env.*.example`,
  `api/.env.example`, `.github/workflows/test_update.yml` — env defaults
- `deployment/variables.tf`, `deployment/terraform.tfvars{,.example}`,
  `deployment/README.md` — infra defaults + docs
- `scripts/verify_openrouter_models.py` — DEFAULT_MODELS pointed at three dead
  models; now primary + fallback + free ZDR-compatible alt
- `scripts/test_openrouter_fallback.py` — rewritten for paid-primary → paid-fallback
- `README.md` — LLM_MODEL line

Historical references (`docs/DONE/*`, BITB-068 story) intentionally untouched.
Test fixtures in `api/tests/test_providers.py` are arbitrary constructor strings
(no live calls) — untouched.

## Acceptance Criteria

- [x] No `llama-3.3-70b-instruct:free`, `gemma-2-9b-it:free`,
  `mistral-7b-instruct:free` references in live config (grep-clean)
- [x] `OPENROUTER_MODEL` default = paid Llama 3.3 70B (exists, ZDR ✅)
- [x] `OPENROUTER_FALLBACK_MODELS` default = paid Gemma 4 31B (exists, ZDR ✅,
  different provider, live-tested EN/DE/IT)
- [x] Backend provider tests pass (`test_providers*.py`)
- [ ] PR merged
