# BITB-187: Live-Run the Follow-Up Chip Set Against a Real LLM, Then Decide on Enabling Chips

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-11
**Prompted by:** BITB-182 follow-up — the golden set and runner were only smoke-tested with a faked model.

## User Story

**As** the product owner, **I want** the 73-case follow-up chip golden set run against a real LLM
in all 11 languages, **so that** I can decide, with evidence, whether to turn chips on in production.

BITB-182 shipped the set (`api/golden_set/test_cases/follow_ups.yaml`) and the live runner
(`make follow-up-eval`, `scripts/run_follow_up_eval.py`). `chat_follow_ups_enabled` is still
`false` in production (`api/config.py`; Terraform variable `chat_follow_ups_enabled`, default
`false`). This is an owner task.

## Functional Requirements

- FR1 Run the set against a backend with a real LLM and `CHAT_FOLLOW_UPS_ENABLED=true` (local stack
  or local-prod, see `docs/FOLLOW_UPS_TESTING.md`), covering all 11 languages.
- FR2 Record pass rates by language and by scenario.
- FR3 Triage failures into prompt fixes versus evaluator fixes.
- FR4 Decide go/no-go; if go, set `chat_follow_ups_enabled = true` in the production tfvars.
- FR5 The `crisis-ml` cases need an ML safety classifier configured: run with one, or read them
  separately.

## Acceptance Criteria

- [ ] Live-run report saved (attached to this story or under `docs/`) with per-language and per-scenario results
- [ ] Any failing scenario has a filed story or a fix
- [ ] Go/no-go recorded in this story with the reason
- [ ] If go: production flag enabled, and the Android and web chips checked on a device via the `--checklist` output

## Out of Scope

- Changing the chip UI.
- The runner's session tracking (BITB-188).
