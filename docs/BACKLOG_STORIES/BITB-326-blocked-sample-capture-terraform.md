---
id: BITB-326
status: done
priority: P2
size: XS
created: 2026-11-16
prs: [1303]
follow_ups: [BITB-328, BITB-329]
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

- **Retention fix:** a repeat of the same blocked text used to push `expires_at` another 30
  days out, so text blocked again and again (with the *first* sender's session hash) was never
  deleted. That broke the privacy policy's "up to 30 days". The expiry is now fixed at the first
  capture, and a repeat only bumps `hit_count`.
- **Privacy policy (11 languages):** two sentences said chat messages are never stored, which
  contradicts the blocked-message bullet. Both now carve out blocked messages. `lastUpdated`
  is now 2026-11-16.
- **GDPR rights section (11 languages):** "since we collect no personally identifiable
  information, clearing local history fulfils most requests" stopped being the whole story once
  capture is on, because a blocked message may contain personal data. The section now says
  blocked-message records are stored without IP, account or device details, deleted
  automatically within 30 days, and how to contact us about them. The Arabic wording is aligned
  on «نظام السلامة» throughout.
- **Exporter:** `scripts/export_blocked_samples.py` no longer returns rows past `expires_at`,
  which still exist between expiry and the next purge.

Privacy is otherwise unchanged and enforced by the capture code: text capped at 500 chars,
dedup by hash, session-id hash only (no IP, user id or UA), 30-day retention, with an hourly
in-app sweep and the daily pg_cron purge.

## Follow-ups

- BITB-328: data inventory + CI guard so the privacy policy cannot drift from what the code
  stores.
- BITB-329: the policy also contradicts what feedback (message, reply, comment, raw session id,
  no expiry) and the contact form (email, user agent) store. This predates #1303 and was found
  in its verification.

## Acceptance criteria

- [x] `api/tests/test_blocked_sample_capture_plumbing.py` pins: variable type and default, the
      env mapping, production tfvars `true`, example `false`, the manifest entry, and the
      Settings default and override.
- [x] `python3 scripts/validate-env.py` passes.
- [x] `test_blocked_samples.py`: a repeat updates only `hit_count`, never `expires_at`.
      It fails on the old code with `{'expires_at', 'hit_count'}`.
- [x] `legal-pages.test.tsx`: in all 11 languages, both chat-message bullets name the
      blocked-message exception. It fails on the old policy.
      `test_privacy_policy_states_the_configured_retention` ties the policy's "up to N days" to
      `blocked_sample_retention_days`.
- [x] `legal-pages.test.tsx`: the GDPR rights section names blocked-message records and 30 days
      in all 11 languages.
- [x] `api/tests/test_export_blocked_samples_query.py`: the export query filters
      `expires_at > now()`. It fails on the old exporter.
- [ ] Owner step: review the changed policy sentences in the 10 translations (listed in PR #1303)
      before merge.
- [x] CI `terraform fmt -check` / `validate` green (tf-validate on PR #1303).
- [ ] Owner step: after the deploy, the backend Container App has
      `BLOCKED_SAMPLE_CAPTURE_ENABLED=true`
      (`az containerapp show -n bible-app-backend -g bible-app-rg --query "properties.template.containers[0].env[?name=='BLOCKED_SAMPLE_CAPTURE_ENABLED']"`).
- [ ] Owner step: after the next prod-monitor run (its probe message is blocked on purpose),
      `make az-pg-add-ip`, then `DATABASE_URL=… make export-blocked-samples ARGS="--limit 5"`
      returns at least one row; then remove the firewall rule.
