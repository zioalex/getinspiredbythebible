---
id: BITB-287
status: in-progress
priority: P2
size: M
rank: 50
created: 2026-11-09
---

# BITB-287: Process & Cost Tooling — BACKLOG union driver, registry cost telemetry, budget guardrail

**Status note:** (PR to follow)
**Follow-up to:** BITB-286 (session cost retrospective)

## Requirements

### 1. BACKLOG.md union merge driver

> **Superseded by BITB-313 (2026-11-13):** GitHub computes PR mergeability and performs squash
> merges server-side and ignores `.gitattributes` merge drivers, so a driver cannot fix PR
> conflicts. BITB-313 removes the conflict source instead: story front matter is the source of
> truth and `docs/BACKLOG.md` is a stub. Do not implement this requirement.

The `docs/BACKLOG.md` changelog is append-only, one entry per line. Same-day same-position additions cause mechanical conflicts that consume orchestrator turns. A union merge driver (or a targeted custom driver) should make same-position append-only conflicts auto-resolvable.

**Constraints:**

- The changelog section is strictly append-only, newest-first
- Conflicts occur when two branches add entries at the same position (top of the list)
- Union must preserve both entries, newest-first
- Other sections (P0/P1/P2/P3, legend, retrospectives) should use normal merge
- A blanket `merge=union` on the whole file is risky (could duplicate non-changelog edits)
- **Design decision**: implement a custom merge driver script that detects changelog-section conflicts and applies a hunk-wise union; falls back to normal merge elsewhere. Alternative: simple `.gitattributes merge=union` if testing proves it's safe for the entire file (the changelog is the only collision hotspot).

### 2. Registry cost telemetry

The task-reliability plugin already tracks child sessions (created/status lines). Extend it to record per-dispatch token/cost telemetry by reading the session events from the opencode bus (which carry `cost`, `tokens_input`, `tokens_output`, `tokens_cache_read`, `tokens_cache_write`, `tokens_reasoning`).

**Acceptance criteria:**

- Each child session's `created` registry line includes `cost`, `tokens_input`, `tokens_output`, `tokens_cache_read`, `tokens_cache_write`, `tokens_reasoning` (or sums on `status: idle`)
- A new `cost` kind in the registry line schema
- Aggregated per-dispatch cost visible in the registry
- The orchestrator's arc retrospectives can query total cost per arc from the registry

### 3. Budget guardrail (`make check-llm-budget`)

A make target that queries OpenRouter's `/api/v1/credits` or `/api/v1/key` endpoint with `OPENROUTER_API_KEY` and warns if remaining credits drop below a threshold (default: $5). Outputs JSON for CI consumption and a human-readable line.

**Acceptance criteria:**

- `make check-llm-budget` exits 0 if credits > threshold, 1 if below
- Output includes remaining balance, usage today, and threshold
- Works with `OPENROUTER_API_KEY` from env or `.env`
- Documented in Makefile help

## Acceptance Criteria

- [x] ~~BACKLOG.md union driver implemented and tested~~ — superseded by BITB-313, not needed
- [ ] Registry records per-dispatch cost in new `kind: "cost"` lines (or enriched `created`/`status` lines)
- [ ] `make check-llm-budget` exists, works with env var, outputs JSON + human line, exits non-zero below threshold
- [ ] All tests pass: generator suite, plugin suite, `make verify-opencode-config`, `make pre-commit`
- [ ] PR opened with conventional commit, green CI, awaiting review

## Out of Scope

- Upstreaming the probe-budget fix (BITB-282) — separate issue
- Modifying the upstream kubeopencode controller — tracked in BITB-284

## References

- BITB-286 (retrospective) for the full ledger and rationale
- BITB-284 for the controller behavior context
- OpenRouter API docs: <https://openrouter.ai/docs/api-reference/credits>
- opencode registry format: `.opencode/plugin/task-reliability.ts`
