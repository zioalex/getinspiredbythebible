---
id: BITB-369
status: in-review
priority: P2
size: S
created: 2026-11-26
prs: [1346]
---

# BITB-369: Codify the delegation-hygiene lessons from the llama.cpp arc (CI-poll discipline + address-masking hazard)

## User story

As the owner, I want the two process lessons observed during the
2026-11-26 llama.cpp arc codified into the repo's delegation rules
(`AGENTS.md` + the orchestrator agent definition), so no future
orchestrator session repeats them: builder subagents must not burn paid
session time polling CI to green, and dispatch briefs must never carry raw
host addresses through agent context.

## Context — the 2026-11-26 llama.cpp arc

Three PRs, all built by the infra-engineer lane, all merged:
#1342 (netpol `agent-egress-llama` + `make verify-llama-egress`, BITB-362),
#1343 (llama.cpp provider in the generated config, opt-in, BITB-363),
#1344 (mechanical lanes on llama, BITB-365). Egress and provider verified
live end-to-end from the agent pod before merge.

### Lesson 1 — CI-poll discipline

- The first brief (T-331B) told the builder to "poll CI cheaply — max ~10
  polls, sleep 30 between": the child ran 14 bounded status reads over
  ~7 minutes of paid session time, purely waiting.
- The follow-up briefs (T-331C/D/E) changed the contract to: ONE status
  read after push to confirm CI started, then return. Every subsequent
  red check was closed by the orchestrator with single bounded reads —
  which is where CI watching belongs (its own budget, or a free-tier
  lane if delegated at all).

### Lesson 2 — the address-masking hazard

- A redaction middleware masks every IP address in agent tool output
  before it reaches model context. The same filter also rejects tool
  calls whose arguments carry address-shaped literals: the first brief
  (raw endpoint URL + address-shaped regex patterns in its text) was
  rejected with "Request blocked by content filter: redaction would
  produce invalid tool call arguments" — twice, on dispatch AND on the
  child's resume, because the poisoned brief text stays in the child's
  context.
- The rewritten briefs carried no literals — placeholder token + runtime
  shell extraction — and shipped all three PRs cleanly.
- Rule: real host addresses move ONLY by shell expansion from an on-disk
  file (jq/cut out of the committed manifest or the workspace config)
  into a placeholder in authored files. Never as literal text in a brief,
  a tool argument, a commit message, a PR body, or prose.
- File-side half is already enforced: the netpol T9 suite
  (`scripts/test_kubeopencode_netpol.py`) fails if the llama host appears
  anywhere outside its manifest.

## Acceptance criteria

- [x] `AGENTS.md` → Subagent Delegation Reliability carries both lessons
- [x] `.opencode/agents/orchestrator.md` → Dispatch hygiene carries both
      lessons (the generator feeds this file into the orchestrator prompt)
- [x] `opencode.json` regenerated (`make gen-opencode-config`) — diff is
      exactly the orchestrator prompt delta
- [x] Gates green in-pod: `make verify-opencode-config`,
      `make test-opencode-config-live`,
      `make test-opencode-config-live-selftest`,
      `make pre-commit`
- [ ] CI green on the PR and merged (the PR itself is the remaining step)

## Owner steps

None — this is orchestrator self-improvement; the agent-definition edits
are the deliverable. (The pod-side promotion of merged config changes
follows the standing BITB-269 sync runbook and is not part of this story.)

## Follow-ups

None known at PR time.
