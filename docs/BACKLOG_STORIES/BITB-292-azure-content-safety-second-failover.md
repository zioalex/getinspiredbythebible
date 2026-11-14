# BITB-292: Azure Content Safety as an Ordered Second ML Failover

**Status:** 🔍 In Review
**Priority:** P1
**Size:** M
**Created:** 2026-11-10
**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 slice 1 fails over only to OpenAI Moderation. If both OpenRouter and OpenAI are down the keyword fallback runs. Azure Content Safety (already implemented as a provider for hybrid mode) can be a third ML classifier.

## Acceptance criteria

- [x] Configurable ordered failover list for `ml_only` (e.g. `openai_moderation,azure`), default unchanged
- [x] Azure is tried only after OpenAI Moderation fails; keyword fallback only when every configured classifier failed; unit + integration tests across the 11 languages
- [x] Metrics reuse `content_safety.failover_total` with a `to_stage` label per hop
- [x] Cost and data-retention for Azure documented

## Implementation

- New setting `CONTENT_SAFETY_ML_FAILOVER_CHAIN` (`content_safety_ml_failover_chain`, default
  `openai_moderation`); comma-separated, whitespace/case-insensitive, de-duplicated, unknown
  entries fail at `Settings()` startup (`parse_ml_failover_chain` in `api/config.py`; parsed list
  via `Settings.ml_failover_chain`). `CONTENT_SAFETY_ML_FAILOVER_ENABLED` remains the master switch.
- `ContentSafetyService._ml_failover` walks the chain in order. A hop is configured if
  `openai_moderation` has `OPENAI_API_KEY`, or `azure` has a provider from
  `_get_azure_provider()`; **unconfigured hops are skipped silently**. First decision wins
  (reason gets ` (failover)`); later hops are not called.
- New `_try_azure` (mirrors `_try_openai_moderation`; never falls back itself; logs only a text
  hash). The hybrid Stage 3 reuses it with unchanged behaviour and metrics.
- Metrics: one `content_safety.failover_total` increment per attempted hop (`from_stage` =
  previously attempted stage, starting at `llama_guard`; `to_stage`; `outcome`; original Llama
  Guard `reason`/`failure_class` on every hop). `fallback_total` `failover` label:
  `disabled` | `unconfigured` | `<last attempted hop>_failed` (default chain still
  `openai_moderation_failed`).
- `log_failover_config_warning` also warns when `azure` is listed with incomplete Azure settings
  and when no hop in the chain is configured.
- Azure help-seeking fix (found in verification): `AzureContentSafetyProvider` no longer caps
  help-seeking at `self_harm < threshold`; help-seeking = self_harm > 0, no violence/hate, and
  sexual < threshold. A severe self-harm-only message is now allowed with the compassionate
  response instead of blocked. This also changes **hybrid-mode** behaviour for such messages.
- Azure calls are bounded by `AZURE_CONTENT_SAFETY_TIMEOUT` (`azure_content_safety_timeout`,
  default 3 s, `asyncio.wait_for`); a timeout raises and counts as a failed hop.
- Empty/whitespace chain = default chain; an OpenAI hop with the key set but an unbuildable
  provider counts as an attempted failed hop (`openai_moderation_failed`), as before.
- Tests: `api/tests/test_ml_failover_chain.py` (config parsing, ordering, metrics labels,
  11-language Azure verdict, startup warnings). Docs: `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md`
  (chain, cost, data retention).

## Notes

Requires the Azure Content Safety resource and key in production.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.

## Follow-ups

- BITB-294 — provision Azure Content Safety in production and enable the `openai_moderation,azure` chain.
