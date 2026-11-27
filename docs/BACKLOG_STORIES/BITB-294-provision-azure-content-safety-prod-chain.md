---
id: BITB-294
status: in-review
priority: P1
kind: nfr
milestone: R1
size: M
rank: 200
created: 2026-11-11
follow_ups: [BITB-353]
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

- [x] Terraform `azurerm_cognitive_account` (kind `ContentSafety`, F0 or S0 — decide on cost) in the app's region
- [x] Endpoint + key wired as backend container env (key as a secret), plus `CONTENT_SAFETY_ML_FAILOVER_CHAIN` variable (default `openai_moderation`; prod `openai_moderation,azure`)
- [ ] Startup log shows no "azure ... incomplete" warning in prod
- [ ] Golden-set check (BITB-293 harness) of Azure verdicts across the 11 languages, esp. self-harm-only → help-seeking (BITB-292 D1 fix)
- [ ] Owner step: choose the SKU (F0 free, only one F0 per subscription, vs S0 paid)
- [ ] Owner step: set `enable_azure_content_safety = true` in `deployment/terraform.tfvars` after BITB-353 (privacy policy disclosure) lands
- [ ] Owner step: confirm Azure Content Safety is available in northeurope, else set `azure_content_safety_location`
- [ ] Owner step: run `scripts/run_safety_golden_set.py --classifier azure` against the provisioned resource
- [ ] Owner step: `terraform apply` + verify one forced double-outage request takes the Azure hop (`failover_total{to_stage="azure"}`)

## Implementation (shipped switched off)

Flag `enable_azure_content_safety` (default false), count-gated account, key as an out-of-band ACA
secret (placeholder pre-seed before apply, real value from the sensitive `azure_content_safety_key`
output after apply). Guarded by `api/tests/test_azure_content_safety_prod_wiring.py`. The startup-log
AC can only be confirmed after the owner enables it.

## Follow-ups

- BITB-353: privacy policy must disclose Azure AI Content Safety before the flag is enabled.

## Notes

- The Azure SDK call runs in a thread pool; `asyncio.wait_for` (BITB-292) bounds the request but does not cancel the worker thread. Fine at current volume; revisit if Azure timeouts become frequent.
- Conflicts likely with BITB-288 (#1280) in `deployment/main.tf` / `variables.tf` — land after it.

## Related

BITB-272, BITB-288, BITB-292, BITB-293, BITB-353.
