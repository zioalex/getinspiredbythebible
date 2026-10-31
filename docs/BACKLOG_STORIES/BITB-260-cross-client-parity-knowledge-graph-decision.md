# BITB-260: Cross-Client Parity Knowledge Graph — Decision Record

**Status:** 🎯 Decision recorded 2026-10-30 (owner-approved) — implementation gated per the stage stories below
**Priority:** P2
**Size:** S (this story is the record; it ships no implementation)
**Created:** 2026-10-30

## Decision

Four clients of the same backend — `api/` (backend), `frontend/` (web), `android/`, and `ios/`
(planned, BITB-087) — must stay behaviorally in sync. This record decides to build a
**cross-client parity knowledge graph**: a validated registry of every capability, contract, and
per-client parity status, stored as a **committed git artifact** (the store of record) with an
**on-demand, local-only graph database as an exploration lens** (owner requirement, 2026-10-30),
built on adopted open-source tooling at every layer rather than hand-rolled extraction.

## Why this exists

The sync cost is structural, not incidental, and the repo's own history is the evidence:

- **Three verse parsers drifted for months** — backend, frontend, and Android regexes with
  different boundary behavior — until shared fixtures + parity tests forced them together
  (BITB-113, BITB-164, BITB-179).
- **BITB-042's feedback rethink shipped web-only**; its story says "Android/iOS parity still
  open." The gap is tracked in a prose paragraph. Nothing pokes it.
- **255 strings × 11 locales × N clients = 2,805+ translation obligations**, each client guarded
  by a separately hand-built CI job.
- **BITB-249/250**: cross-browser behavioral parity defects (read-aloud) found by a user, not by
  any check.

The pattern in every case: enforcement won over reviewer diligence, but each enforcement was
built *reactively*, one invariant at a time, after drift hurt. This decision generalizes the
proven pattern — spec + CI enforcement — into a systematic registry of **all** cross-client
obligations instead of a scattered set of one-off greps.

**Predecessor:** `docs/WIP/android-feature-parity-plan.md` (2026-03-12) — a hand-built web→Android
gap analysis in exactly the GAP-001..N "web does / Android does" shape. It proves both the format
and its limitation: a frozen snapshot that went stale. The registry (BITB-262) is its living,
CI-validated successor.

## What the graph models

Nodes: `Client` (api, web, android, ios) · `Capability` · `Contract` · `Implementation` · `Test` ·
`Obligation` — **including negative obligations** ("iOS ships no verse regex" is a row, not a
footnote). The edge that pays for the system is `parity_status(Capability, Client)` with statuses
`synced | drifted | partial | absent | obligated | n/a` plus evidence refs (file, PR, story).

Illustrative rows (shape, not final schema — BITB-262 owns that):

```yaml
clients: [api, web, android, ios(planned, BITB-087)]
contracts:
  chat-stream-sse:  {truth: api/chat/service.py, consumers: [web, android, ios-obligated]}
  citations-spans: {truth: BITB-086 contract, web-proof: BITB-109}
  verse-grammar:   {truth: tests/fixtures/verse_grammar.json}
  strings-catalog: {locales: 11}
capabilities:
  feedback-rethink: {web: synced, android: drifted(BITB-042), ios: absent}   # the first red row
  verse-citations:  {web: synced, android: synced, ios: obligated, negative: ios-no-regex}
```

**Explicit non-goal: this is not a code-understanding graph.** No AST mining, no call graphs, no
heuristic semantic edges — a plausible-but-wrong edge is worse than a missing one, because the
iOS port would trust it and be wrong (this is why Joern/tree-sitter extraction is a gated
stage-4 candidate, not a foundation). The trustworthy edges come from adopted tooling (OpenAPI
diff, fixture validation, strings validation) and from specialist agents reading code with an
independent verifier re-checking rows (BITB-262's trust gate).

## Tooling decision per layer (build/adopt/defer)

| Layer | Open-source / free solution | Decision |
|---|---|---|
| API contract truth | FastAPI's built-in OpenAPI export + **oasdiff** breaking-change detection | **Adopt** — stage 1 (BITB-261) |
| Client↔backend consumption | **openapi-generator** (TS/Kotlin/Swift) | **Candidate follow-up** after stage 1 proves the artifact; pilot: web client. Generating the client API layer makes endpoint-shape drift structurally impossible |
| Behavioral contract testing | **Pact** + broker (Swift/JVM/TS consumers, pact-python provider) | **Candidate, selective** — REST endpoints only; SSE stays fixture-tested. Filed when stage 2 lands |
| Translations (255 × 11 × N) | **Weblate** (GPL self-host; free hosted tier for libre projects — repo has a LICENSE and is public, likely eligible) | **Optional** — evaluate only if translation churn justifies the ops; natively speaks `strings.xml`, `.xcstrings`, `messages/*.json` |
| Code-level fact extraction | Semgrep / Joern / tree-sitter | **Deferred, gated** — Kotlin support is the weak spot; only on a demonstrated query need the registry cannot answer |
| Developer portal | **Backstage** | **Rejected** — right shape, wrong scale: a running multi-service platform for a single-maintainer repo |
| Graph store / interactive queries | **Neo4j Community Edition** (Memgraph as recorded drop-in) | **Adopt, on-demand, local-only** — the owner's development-laptop lens (BITB-263). Not standing infra, not in CI, not hosted |
| Visualization | **Mermaid** (GitHub renders natively) | **Adopt** — the landscape is a container diagram + status matrix in `docs/parity/landscape.md` (BITB-262) |
| Parity registry itself | — no market solution exists | **Build, thin** — `docs/parity/registry.yaml` + `tools/parity-graph/` validate/render; small because every edge it references is sourced from the adopted tools above |

## Stage gates

| Stage | Story | Gate |
|---|---|---|
| 1 — Contract layer | BITB-261 | Dispatchable immediately: OpenAPI artifact + stale-check + oasdiff CI |
| 2 — Registry layer | BITB-262 | Gated on stage 1 landing; seeding needs specialist passes + independent verification |
| 3 — Serving layer | BITB-263 | Gated on stage 2 (imports its `graph.json`); the laptop lens |

**Follow-up candidates — file each when its predecessor lands, not now** (their scope depends on
what the earlier stage teaches; same reasoning as BITB-087's deferred Tier-2 story): PR drift bot
(comments parity impact on PRs touching contract artifacts); openapi-generator pilot; Pact
provider-verification matrix; Weblate evaluation; stage-4 code-level edges (gated).

## What would reverse this

- After stage 2 lands: registry upkeep exceeding its value — rows stale for more than a sprint
  with no owner action, or the sync routine costing more drift-prevention than it delivers.
- Stage 1 in practice: oasdiff noise unmanageable (the warn-vs-fail policy review).
- Stage 2 design review finding the registry merely duplicating CI greps instead of
  generalizing them.

Any of these rejects the approach for the affected stage and requires this record to be updated
with the observed evidence, not silently abandoned.

## Acceptance Criteria

- [ ] This decision record merged with the tooling matrix and stage mapping (this PR)
- [ ] Stage stories BITB-261, BITB-262, BITB-263 filed with their own acceptance criteria (this PR)
- [ ] No code, CI, or config changes in this PR — stories and record only

## Related

- **BITB-261 / BITB-262 / BITB-263** — the three stage stories
- **BITB-042** — the first red row the registry must surface
- **BITB-113 / BITB-164 / BITB-179** — the parser-unification precedent (fixtures + parity tests won)
- **BITB-086 / BITB-109** — the citations contract this initiative formally captures
- **BITB-242** — platform feature flags, a future `contracts` row when it lands
- **BITB-085 / BITB-087** — the iOS delivery plan this initiative serves
- **AGENTS.md** — the three-parser sync rule this registry generalizes
