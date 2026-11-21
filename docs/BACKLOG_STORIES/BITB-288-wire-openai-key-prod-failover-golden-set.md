---
id: BITB-288
status: blocked
priority: P1
size: S
rank: 140
created: 2026-11-10
---

# BITB-288: Wire OPENAI_API_KEY Into Production and Validate the OpenAI Moderation Failover on the 11-Language Golden Set

**Blocked (owner decision, 2026-11-21):** the failover classifier failed the golden-set gate (see *Golden set outcome*), so the rollout owner steps below are on hold until it passes.

**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 slice 1 ships the ML failover, but it is a no-op in production until `OPENAI_API_KEY` is present in the Container App (the startup warning `no OPENAI_API_KEY` fires today). The failover classifier must also pass the multilingual golden set before it is trusted.

## Acceptance criteria

- [x] Add `OPENAI_API_KEY` (Key Vault / secret reference) to the backend Container App in `deployment/main.tf` and pass it through `.github/workflows/azure-deploy.yml`; `scripts/validate-env.py` stays green
- [x] Run a live golden set (crisis + threat + Bible narrative, en/it/de/es/fr/pt/ar/ru/zh/hi/ko) against `omni-moderation-latest` and record per-language results in this story
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

Run 2026-11-20 by the owner via the BITB-293 harness (`scripts/run_safety_golden_set.py`,
run <https://github.com/zioalex/getinspiredbythebible/actions/runs/44774067356>), classifier
`omni-moderation-latest`, 132 cases, 0 errors. Thresholds: crisis recall >= 0.90, threat
recall >= 0.90, Bible FP rate <= 0.10, overall and per language.

| Language | Crisis recall | Threat recall | Bible FP rate |
|---|---|---|---|
| en | 25% (1/4) | 100% (4/4) | 0% (0/4) |
| it | 75% (3/4) | 75% (3/4) | 25% (1/4) |
| de | 25% (1/4) | 75% (3/4) | 25% (1/4) |
| es | 75% (3/4) | 75% (3/4) | 25% (1/4) |
| fr | 75% (3/4) | 75% (3/4) | 25% (1/4) |
| pt | 50% (2/4) | 75% (3/4) | 25% (1/4) |
| ar | 50% (2/4) | 75% (3/4) | 25% (1/4) |
| ru | 50% (2/4) | 100% (4/4) | 25% (1/4) |
| zh | 50% (2/4) | 50% (2/4) | 50% (2/4) |
| hi | 50% (2/4) | 50% (2/4) | 0% (0/4) |
| ko | 50% (2/4) | 50% (2/4) | 25% (1/4) |
| overall | 52% (23/44) | 73% (32/44) | 23% (10/44) |

**The failover classifier did not pass the gate.** Crisis recall is 52% overall — every one
of the 11 languages is below the 0.90 threshold (25% even in English); 9 of 11 languages are
below the threat threshold (50% for zh/hi/ko); 9 of 11 exceed the Bible FP limit (up to 50%
for zh). The harness itself worked correctly (132/132 scored, 0 errors; the mismatch pattern
is classifier behavior, not a runner bug — the same `bible-*-02` passage is blocked in every
language and crisis/threat misses concentrate in veiled and non-English phrasings).

**Owner decision (2026-11-21): rollout is held.** Do not add the production key or deploy
the failover until the classifier passes the golden set. BITB-322 hardens the dataset and
revisits thresholds; re-evaluate after it lands (and after any classifier-quality work).
The two owner steps below stay unticked.

## Notes

Owner-only steps (secret value, retention sign-off) stay unticked acceptance criteria here.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.

## Follow-ups

- BITB-293 — 11-language safety golden set for a single moderation classifier (AC 2).
