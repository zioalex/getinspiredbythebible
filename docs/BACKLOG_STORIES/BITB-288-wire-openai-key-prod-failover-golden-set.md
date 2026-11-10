# BITB-288: Wire OPENAI_API_KEY Into Production and Validate the OpenAI Moderation Failover on the 11-Language Golden Set

**Status:** 🎯 Todo
**Priority:** P1
**Size:** S
**Created:** 2026-11-10
**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 slice 1 ships the ML failover, but it is a no-op in production until `OPENAI_API_KEY` is present in the Container App (the startup warning `no OPENAI_API_KEY` fires today). The failover classifier must also pass the multilingual golden set before it is trusted.

## Acceptance criteria

- [ ] Add `OPENAI_API_KEY` (Key Vault / secret reference) to the backend Container App in `deployment/main.tf` and pass it through `.github/workflows/azure-deploy.yml`; `scripts/validate-env.py` stays green
- [ ] Run a live golden set (crisis + threat + Bible narrative, en/it/de/es/fr/pt/ar/ru/zh/hi/ko) against `omni-moderation-latest` and record per-language results in this story
- [ ] Owner step: add the secret value, confirm OpenAI data-retention is acceptable, then deploy; the startup warning no longer appears
- [ ] Owner step: a forced Llama Guard failure on a staging revision shows `content_safety.failover_total{outcome=decided}`

## Notes

Owner-only steps (secret value, retention sign-off) stay unticked acceptance criteria here.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
