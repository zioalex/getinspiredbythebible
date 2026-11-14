---
id: BITB-294
status: todo
priority: P1
size: M
rank: 200
created: 2026-11-11
---

# BITB-294: Provision Azure Content Safety in Production and Enable the `openai_moderation,azure` Chain

**Prompted by:** BITB-292 (code-only: the ordered ML failover chain ships, but production has nothing to fail over to).

## Problem

BITB-292 added `CONTENT_SAFETY_ML_FAILOVER_CHAIN` and the Azure hop, but `deployment/main.tf` /
`deployment/variables.tf` define no Azure AI Content Safety resource and wire none of
`AZURE_CONTENT_SAFETY_ENABLED`, `AZURE_CONTENT_SAFETY_ENDPOINT`, `AZURE_CONTENT_SAFETY_KEY`,
`AZURE_CONTENT_SAFETY_TIMEOUT` or `CONTENT_SAFETY_ML_FAILOVER_CHAIN` into the backend container
(verified 2026-11-11: only `CONTENT_SAFETY_ENABLED` / `CONTENT_SAFETY_MODE` are set). So in
production the Azure hop is always skipped as unconfigured. Same gap shape as BITB-288 (OpenAI key).

## Acceptance criteria

- [ ] Terraform `azurerm_cognitive_account` (kind `ContentSafety`, F0 or S0 — decide on cost) in the app's region
- [ ] Endpoint + key wired as backend container env (key as a secret), plus `CONTENT_SAFETY_ML_FAILOVER_CHAIN` variable (default `openai_moderation`; prod `openai_moderation,azure`)
- [ ] Startup log shows no "azure ... incomplete" warning in prod
- [ ] Golden-set check (BITB-293 harness) of Azure verdicts across the 11 languages, esp. self-harm-only → help-seeking (BITB-292 D1 fix)
- [ ] Owner step: `terraform apply` + verify one forced double-outage request takes the Azure hop (`failover_total{to_stage="azure"}`)

## Notes

- The Azure SDK call runs in a thread pool; `asyncio.wait_for` (BITB-292) bounds the request but does not cancel the worker thread. Fine at current volume; revisit if Azure timeouts become frequent.
- Conflicts likely with BITB-288 (#1280) in `deployment/main.tf` / `variables.tf` — land after it.

## Related

BITB-272, BITB-288, BITB-292, BITB-293.
