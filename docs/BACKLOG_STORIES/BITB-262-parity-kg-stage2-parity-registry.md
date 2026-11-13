---
id: BITB-262
status: in-progress
priority: P2
size: L
rank: 180
created: 2026-10-30
prs: [1258]
---

# BITB-262: Parity KG Stage 2 — Capability × Client Parity Registry

**Status note:** (PR #1258)
**Part of:** BITB-260 — Stage 2 of 3 (registry layer)

## User Story

**As the** maintainer, **I want** a single validated registry of every user-facing capability and
its per-client parity status, **so that** drift like BITB-042 surfaces as a red row that CI keeps
visible instead of living in a prose paragraph — and so the iOS port (BITB-087) draws its spec
sheets from derived, always-current data instead of hand-copied file lists.

## Registry design (`docs/parity/registry.yaml`)

- **clients:** `api`, `web`, `android`, `ios` (marked `planned`, BITB-087)
- **contracts:** `chat-stream-sse` (truth: `api/chat/service.py`; consumers listed),
  `citations-spans` (BITB-086 contract; BITB-109 web proof), `verse-grammar` (truth:
  `tests/fixtures/verse_grammar.json`), `strings-catalog` (11 locales), `telemetry-os-enum`
  (BITB-247), `platform-flags` (BITB-242, when it lands), permissions, legal URLs
- **capabilities:** each with `parity_status(client) ∈ {synced, drifted, partial, absent,
  obligated, n/a}` plus evidence refs (file, PR, story)
- **negative obligations are first-class rows**: e.g. `ios: no-verse-regex` (BITB-087's CI grep),
  `ios: no-donate-entry` (BITB-085's recorded decision)

Illustrative row (the first red row the registry must surface):

```yaml
capability: feedback-rethink        # BITB-042
web:      {status: synced, since: "web rethink shipped"}
android:  {status: drifted, story: BITB-042}
ios:      {status: absent, note: "pre-v1"}
```

## Seed sources

1. `docs/WIP/android-feature-parity-plan.md` GAP-001..N — **every row re-verified against current
   code before entering** (the plan is a 2026-03-12 snapshot and stale by definition). Afterwards
   the WIP doc gets a pointer to the registry or is deleted — the AGENTS.md
   documentation-completeness rule applies to whichever.
2. BITB-087's Tier 1 / Tier 2 capability tables (the iOS parity obligations, with their Android
   reference files as evidence)
3. A web-feature inventory from `frontend/` (flags, screens, components)

## Tooling (`tools/parity-graph/`, following the `tools/repo-metrics/` convention: `analyze.py` + `render.py` + README + tests)

- `analyze.py`: schema validation; a strings cross-check that **reuses the same source of truth
  as the Android `translation-validation` CI job** (`.github/workflows/android-ci.yml`) — never a
  second validator that can disagree with the first; emits `docs/parity/graph.json` (consumed by
  BITB-263's importer); `--check` freshness mode.
- `render.py`: emits `docs/parity/landscape.md` — a Mermaid container diagram (backend + clients +
  contracts; GitHub renders it natively) plus the rendered capability×client status matrix.
- CI (extends the stage-1 parity job): schema validation + freshness check fail; **drifted rows
  are the payload, not the failure** — they render in the job summary and the landscape and stay
  red until their story closes.

## Seeding & trust gate

Rows are filled by reading code — two specialist passes (Android inventory; web + backend
inventory) — and an **independent verifier re-checks a random sample of ≥10 rows against the
code** before merge, with findings resolved. A plausible-but-wrong edge is worse than a missing
one (BITB-260's non-goal); this independent review is the stage's hard gate.

## Acceptance Criteria

- [ ] `registry.yaml` validates; coverage ≥ BITB-087's Tier 1+2 tables + every WIP-plan GAP
      (statused, with evidence, after re-verification against current code)
- [ ] BITB-042 appears as a `drifted` Android row with its story link — surfaced, not buried
      — **see re-verification note 1 below: the drift closed 2026-06-06 (PR #685, completed
      #783), before this story was filed; the row is recorded truthfully as `synced` with
      the BITB-042 story link and fixing PRs, per this story's own "rows must be TRUE" rule.
      The live red row today is BITB-267 (`verse-reference-detection` · api).**
- [ ] `docs/parity/graph.json` and `docs/parity/landscape.md` are emitted, committed, and
      regenerated/freshness-checked by CI
- [ ] The strings cross-check shares `translation-validation`'s source of truth (no forked
      validator that can disagree)
- [ ] The independent verifier has re-checked a sample of ≥10 rows against the code, and
      findings are resolved
- [ ] CI green; the diff touches only `tools/parity-graph/`, `docs/parity/`, `docs/WIP/`
      (the pointer), the CI files, and `Makefile` (+ its audit json)

## Re-verification notes (2026-11-08, PR #1258)

Recorded per the seed rule ("every row re-verified against current code before entering —
the plan is a 2026-03-12 snapshot and stale by definition"):

1. **BITB-042's Android drift no longer exists.** `android/.../FeedbackControls.kt:69`
   (`FEEDBACK_RETHINK_MS`) implements the rethink window, maintainer notice, reason chips and
   single-send, landed 2026-06-06 in PR #685 (fix-ups #692, #696; completed #783, 2026-07-03);
   `feedback_maintainer_notice` exists in all 11 Android locales. The registry therefore
   records `feedback-rethink` android: **synced** with the story link and PRs as evidence —
   the truthful status. The AC's premise ("appears as a drifted Android row") was written
   2026-10-30 against a drift that had closed four months earlier.
2. **Every WIP-plan GAP-001..012 has shipped on Android** (verified individually against the
   code — ChatRequestDto, EventSourceParser, FeedbackControls, MarkdownText, ShareCompat,
   isBackendWarming, scroll FAB, church finder, contact form, injectVerseLinks, VersesPanel,
   values-{ru,zh,hi,ko}). All 12 rows are synced with their fixing evidence; the WIP doc now
   carries the superseded pointer.
3. **The live drift at seeding time is BITB-267** (backend verse-parser boundary gap:
   `**`, `—`, `¿` starts) — recorded as `verse-reference-detection` api: **drifted** and
   surfaced in the landscape drift watch and the CI job summary.
4. The remaining ACs (independent ≥10-row verification, CI green) are for the Verify stage;
   the checkboxes stay unticked until then.

## Out of Scope

- The Neo4j import (BITB-263)
- The PR drift bot (follow-up candidate)
- openapi-generated clients (follow-up candidate)
- Any code-level AST mining (gated stage-4 candidate per BITB-260)

## Related

- **BITB-260** — the decision record (stage 2 of 3)
- **BITB-261** — stage 1 (its CI job is extended here)
- **BITB-263** — stage 3 (consumes this stage's `graph.json`)
- **BITB-042**, **BITB-087**, **BITB-242** — the rows, obligations, and future contracts above
