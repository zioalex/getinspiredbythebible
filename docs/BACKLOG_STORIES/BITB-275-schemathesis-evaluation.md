---
id: BITB-275
status: todo
priority: P3
size: S
rank: 20
created: 2026-11-08
---

# BITB-275: Schemathesis Conformance Fuzzing — Evaluate and Decide

**Size note:** /M (spike + decision)
**Follow-up to:** BITB-261 (named in its Out of Scope)

## User Story

**As the** maintainer, **I want** to know whether Schemathesis (runtime conformance fuzzing from the
OpenAPI spec) earns its place in CI, **so that** "spec says X, server returns Y" drift is caught before
clients hit it — a category the static oasdiff artifact diff cannot cover.

## Requirements

1. Run the MIT-licensed engine (`schemathesis/schemathesis`, v4.x, active) against the local
   `docker-compose` API stack using the committed `docs/parity/openapi.json` as the schema source.
   **Do NOT adopt the community GitHub Action** — its repo has no LICENSE file (survey [T-260B],
   2026-11-07); run the CLI in a compose job instead.
2. Measure: does it find real conformance gaps in the 22-path surface? False-positive rate on the
   Turnstile-protected POSTs (they need `X-Turnstile-Token` — define auth handling or skip those paths)?
3. Record a go/no-go with evidence in the story; if go, wire a non-blocking (warn-only) CI job.

## Acceptance Criteria

- [ ] Spike run completed against local stack with findings documented
- [ ] Go/no-go decision recorded with rationale (cost, noise, value vs. the static oasdiff gate)

**Related:** BITB-261/273 (the contract artifact it fuzzes), BITB-277.
