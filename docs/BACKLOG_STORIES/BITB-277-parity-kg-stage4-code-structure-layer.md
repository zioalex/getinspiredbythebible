---
id: BITB-277
status: todo
priority: P2
size: L
rank: 70
created: 2026-11-08
depends_on: [BITB-262]
---

# BITB-277: Parity KG Stage 4 — Application Code-Structure Layer

**Status note:** gated on BITB-262 landing (needs the registry schema + graph.json format)
**Part of:** BITB-260 — Stage 4 (promoted from "gated candidate" 2026-11-08: the owner's requirement
for an application knowledge graph to improve development is the demonstrated query need)

## User Story

**As the** maintainer, **I want** per-client code-structure facts (files, classes/functions, modules,
import edges, test→subject, string-key references) merged into the same parity graph, **so that** I can
ask impact, coverage, and onboarding questions of the codebase itself — and AI build agents get cheap,
always-current context instead of re-reading every file.

## Adopted per-client extractors (survey [T-260B], licenses verified)

| Client | Tool | License | Role |
|---|---|---|---|
| frontend/ | **dependency-cruiser** (7.3k★, active) | MIT | emits the TS module import graph as JSON (and Mermaid) directly; rules engine doubles as CI policy |
| api/ | **grimp** (BSD-2, active) | BSD-2-Clause | Python import graph; Python API + JSON serialization inside pytest-covered tooling |
| android/ | **tree-sitter-kotlin** or **Semgrep CE** rules | MIT / LGPL-2.1 | declaration + annotation facts (`@Composable`, `@Dao`, `@Entity`, `@HiltViewModel`); test→subject via JUnit naming |
| android/ (precise refs, optional) | **scip-java** (Kotlin merged in; Apache-2.0) | Apache-2.0 | **pilot first** on `android/` — Kotlin/Compose version compatibility is the risk item |

**Rejected:** jQAssistant (GPL, needs compiled artifacts, own embedded Neo4j store fights the
git-artifact architecture); Joern (Medium Kotlin maturity, own graph store); CodeQL (no Kotlin).

## Design constraints

- Feeds the SAME `graph.json` (BITB-262's format) — no separate store; the Neo4j lens (BITB-263) shows
  it automatically.
- **Reliable edge classes only**: imports, package/module structure, annotation facts, test→subject
  naming, exact string-key references. **Fine-grained call-graph resolution stays out of scope** (BITB-260's
  non-goal: heuristic edges are worse than none).
- CI: extraction regenerated + `--check` freshness, same pattern as stages 1–2.
- scip-java adoption is a pilot decision inside this story — run it on `android/` first, fall back to
  tree-sitter/Semgrep-only if the pilot fails.

## Acceptance Criteria

- [ ] Extraction for all three clients emits into `graph.json`; freshness-checked in CI
- [ ] The graph answers: blast radius of a file (transitive import fan-in), untested classes/functions
      (no test→subject edge), which composables reference a given string key
- [ ] Android rows verified by android-expert review; ≥10 edges spot-checked by the verifier (stage-2
      trust-gate pattern)
- [ ] No application code changes outside `tools/parity-graph/`, docs, CI files

**Related:** BITB-260 (decision), BITB-262 (format owner), BITB-263 (lens), BITB-087 (the iOS port
this ultimately serves).
