---
id: BITB-288
status: in-review
priority: P1
size: S
rank: 140
created: 2026-11-10
---

# BITB-288: Wire OPENAI_API_KEY Into Production and Validate the OpenAI Moderation Failover on the 11-Language Golden Set

**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 slice 1 ships the ML failover, but it is a no-op in production until `OPENAI_API_KEY` is present in the Container App (the startup warning `no OPENAI_API_KEY` fires today). The failover classifier must also pass the multilingual golden set before it is trusted.

## Acceptance criteria

- [x] Add `OPENAI_API_KEY` (Key Vault / secret reference) to the backend Container App in `deployment/main.tf` and pass it through `.github/workflows/azure-deploy.yml`; `scripts/validate-env.py` stays green
- [ ] Run a live golden set (crisis + threat + Bible narrative, en/it/de/es/fr/pt/ar/ru/zh/hi/ko) against `omni-moderation-latest` and record per-language results in this story
- [ ] Owner step: add the secret value, confirm OpenAI data-retention is acceptable, then deploy; the startup warning no longer appears
- [ ] Owner step: a forced Llama Guard failure on a staging revision shows `content_safety.failover_total{outcome=decided}`

## Implementation

Mirrors the BITB-067 gap #6 out-of-band pattern (`monitor_probe_secret`), because the backend app has
`lifecycle { ignore_changes = [secret] }` and must not be replaced on rotation (cert-unbind risk).

- `deployment/variables.tf`: `openai_api_key` (sensitive, default `""`) only gates whether the ACA secret exists.
- `deployment/main.tf`: gated `OPENAI_API_KEY` env `secretRef` -> `openai-api-key`; `dynamic "secret"` with the
  bootstrap placeholder; deliberately NOT in `backend_secret_trigger`.
- `.github/workflows/azure-deploy.yml`: `TF_VAR_openai_api_key` in the tf-plan, deploy and destroy job envs; the
  populate step (renamed *Populate out-of-band secrets in backend Container App*) also sets `openai-api-key`;
  new pre-apply step *Pre-seed openai-api-key secret on existing backend app* (see risk below).
- Docs: `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md` (*Production wiring*), `deployment/README.md`,
  `deployment/terraform.tfvars.secrets.example`, `scripts/env-manifest.yaml` description.
- Tests: `api/tests/test_openai_key_prod_wiring.py`.

**Rollout risk handled:** `ignore_changes = [secret]` means Terraform will not add the new `openai-api-key`
secret to the already-existing app, but it does add the env `secretRef` to the template, so the new revision
could reference a missing secret and fail to provision before the post-apply populate step runs. The pre-apply
seed step sets the secret on the live app first (no-op if the repo secret is empty or the app does not exist).

## Golden set outcome

Not done. The existing harness (`scripts/run_golden_set.py`, `golden-set-live.yml`) drives the chat API and
evaluates answers; it cannot target OpenAI Moderation, and no OpenAI key exists in the build sandbox. Building a
moderation-classifier golden set (crisis + threat + Bible narrative x 11 languages vs `omni-moderation-latest`)
is remaining work, filed as BITB-293; the second acceptance criterion stays unticked.

## Notes

Owner-only steps (secret value, retention sign-off) stay unticked acceptance criteria here.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.

## Follow-ups

- BITB-293 — 11-language safety golden set for a single moderation classifier (AC 2).
