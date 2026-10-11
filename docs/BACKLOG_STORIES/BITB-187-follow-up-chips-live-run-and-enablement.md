# BITB-187: Live-Run the Follow-Up Chip Set Against a Real LLM, Then Decide on Enabling Chips

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-11
**Prompted by:** BITB-182 follow-up — the golden set and runner were only smoke-tested with a faked model.

## User Story

**As** the product owner, **I want** the 77-case follow-up chip golden set run against a real LLM
in all 11 languages, **so that** I can decide, with evidence, whether to turn chips on in production.

BITB-182 shipped the set (`api/golden_set/test_cases/follow_ups.yaml`) and the live runner
(`make follow-up-eval`, `scripts/run_follow_up_eval.py`). `chat_follow_ups_enabled` is still
`false` in production (`api/config.py`; Terraform variable `chat_follow_ups_enabled`, default
`false`). This is an owner task.

This is its own story, not an unticked owner AC on BITB-182, because the live run and the
enablement decision were explicitly out of scope for BITB-182 and enablement is a deferred product
decision; the product owner chose a separate story on 2026-10-11.

## Functional Requirements

- FR1 Run the set against a backend with a real LLM and `CHAT_FOLLOW_UPS_ENABLED=true` (local stack
  or local-prod, see `docs/FOLLOW_UPS_TESTING.md`), covering all 11 languages.
- FR2 Record pass rates by language and by scenario.
- FR3 Triage failures into prompt fixes versus evaluator fixes.
- FR4 Check the interaction with the 10-message session limit (BITB-024,
  `rate_limit_session_max_requests`) before rollout; this is the open BITB-080 criterion
  "Interaction with the 10-message session limit (BITB-024) checked before rollout"
  (`docs/BACKLOG.md`, BITB-080 entry).
- FR5 Decide go/no-go; if go, set `chat_follow_ups_enabled = true` in the production tfvars.
- FR6 The `crisis-ml` cases need an ML safety classifier configured: run with one, or read them
  separately.

## Acceptance Criteria

- [ ] Live-run report saved (attached to this story or under `docs/`) with per-language and per-scenario results
- [ ] Any failing scenario has a filed story or a fix
- [ ] Interaction with the 10-message session limit (BITB-024) checked, closing the open BITB-080 criterion
- [ ] Go/no-go recorded in this story with the reason
- [ ] If go: production flag enabled, and the Android and web chips checked on a device via the `--checklist` output

## Out of Scope

- Changing the chip UI.
- The runner's session tracking (BITB-188).
