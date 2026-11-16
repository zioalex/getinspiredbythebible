---
id: BITB-326
status: in-review
priority: P2
size: XS
created: 2026-11-16
---

# BITB-326: Turn On Blocked-Message Capture in Production via Terraform

## Problem

`make export-blocked-samples` returned nothing against production (2026-11-16). The capture in
`api/feedback/blocked_samples.py` is gated by `blocked_sample_capture_enabled`, which defaults
to `False` (`api/config.py`). It was never wired into Terraform or `scripts/env-manifest.yaml`,
so production has never stored a blocked message. False positives (BITB-293's concern) cannot be
reviewed.

## Fix

- `deployment/variables.tf`: `blocked_sample_capture_enabled` (bool, default `false`).
- `deployment/main.tf`: mapped to `BLOCKED_SAMPLE_CAPTURE_ENABLED` in `backend_env_vars`.
- `deployment/terraform.tfvars`: `true` for production. `terraform.tfvars.example`: `false`.
- `scripts/env-manifest.yaml`: declared `required_in: remote`. docker-compose keeps the code
  default (off).
- `docs/HOW-TO-EXPORT-BLOCKED-SAMPLES.md`: the Terraform switch, plus the Postgres firewall
  step (`make az-pg-add-ip`) that made the export hang.

Privacy is unchanged and already enforced by the capture code: text capped at 500 chars,
dedup by hash, session-id hash only (no IP, user id or UA), retention 30 days after the
last occurrence, with the daily pg_cron purge.

## Acceptance criteria

- [x] `api/tests/test_blocked_sample_capture_plumbing.py` pins: variable type and default, the
      env mapping, production tfvars `true`, example `false`, the manifest entry, and the
      Settings default and override.
- [x] `python3 scripts/validate-env.py` passes.
- [x] CI `terraform fmt -check` / `validate` green (tf-validate on PR #1303).
- [ ] Owner step: after the deploy, the backend Container App has
      `BLOCKED_SAMPLE_CAPTURE_ENABLED=true`
      (`az containerapp show -n bible-app-backend -g bible-app-rg --query "properties.template.containers[0].env[?name=='BLOCKED_SAMPLE_CAPTURE_ENABLED']"`).
- [ ] Owner step: after the next prod-monitor run (its probe message is blocked on purpose),
      `make az-pg-add-ip`, then `DATABASE_URL=… make export-blocked-samples ARGS="--limit 5"`
      returns at least one row; then remove the firewall rule.
