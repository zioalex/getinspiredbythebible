# BITB-263: Parity KG Stage 3 — On-Demand Local Neo4j Lens

**Status:** 🎯 Todo — gated on BITB-262 landing (it imports stage 2's `graph.json`)
**Priority:** P2
**Size:** M
**Created:** 2026-10-30
**Part of:** BITB-260 — Stage 3 of 3 (serving layer)

## User Story

**As the** maintainer, **on my development laptop** I want to spin up a local Neo4j instance with
one command, import the parity graph, run a saved query pack, and tear it down, **so that** I can
explore cross-client relationships interactively — with no standing infrastructure, no hosting
cost, and no CI dependency.

## Owner-set constraints (2026-10-30)

- **On-demand and local only.** Docker on the development laptop; never started by the existing
  compose stacks (`docker-compose*.yml` must not gain the service implicitly); never required by
  CI; nothing hosted.
- **The database is a disposable view.** The git artifact stays the store of record (BITB-260);
  deleting the volume loses nothing — a re-import restores the identical graph.
- Re-import after any registry change; the import is idempotent (clear + load, reproducible).

## Requirements

1. **`docker-compose.graph-lens.yml`** (or a dedicated compose profile): Neo4j Community Edition,
   local ports (browser 7474, bolt 7687), named volume. **Memgraph is the recorded drop-in
   alternative** — Neo4j CE chosen for its browser UI and Cypher maturity; the swap is documented
   as a one-line change so the choice stays reversible.
2. **`tools/parity-graph/import_neo4j.py`**: loads `docs/parity/registry.yaml` +
   `docs/parity/graph.json` into Neo4j (bolt or HTTP), mapping nodes and edges to idempotent
   `MERGE`s. Runs against the local instance only.
3. **`docs/parity/cypher-recipes.md`** — the saved query pack:
   - capabilities drifted or partial, per client (the BITB-042 row must appear)
   - contracts consumed by ≥2 clients — change blast radius (implementations + tests + clients)
   - capabilities with no iOS obligation (unplanned for the port)
   - capabilities with no test edge (coverage gaps)
4. **Makefile:** `graph-lens-up` / `graph-lens-import` / `graph-lens-down` (+ `graph-lens-purge`
   to remove the volume), registered per the make-target audit convention.
5. **`docs/parity/README.md`** gains the lens section — zero-to-running from a fresh clone
   (AGENTS.md documentation-completeness rule).

## Acceptance Criteria

- [ ] Fresh clone → `make graph-lens-up && make graph-lens-import` → the Neo4j browser at
      `localhost:7474` shows clients / capabilities / contracts / parity edges
- [ ] Every recipe in `cypher-recipes.md` returns a correct answer; spot-check: the
      drifted-capabilities query lists BITB-042's row
- [ ] `make graph-lens-down` tears down; a subsequent re-import reproduces an identical graph
      (idempotency proven)
- [ ] No CI workflow requires Neo4j, and no existing compose target starts it implicitly
- [ ] Zero-to-running is documented and observed on the development laptop (implementer records
      the observed run; owner re-runs it)
- [ ] No application code changed

## Out of Scope

- Hosted or clustered Neo4j / Aura (cloud account — explicitly declined for now)
- The PR drift bot (separate follow-up candidate)
- Graph auto-refresh watchers or background sync daemons
- Code-level edges via AST mining (gated stage-4 candidate per BITB-260)

## Files Likely to Change

| Path | Change |
|---|---|
| `docker-compose.graph-lens.yml` | New — on-demand local Neo4j CE service |
| `tools/parity-graph/import_neo4j.py` | New — idempotent graph importer |
| `docs/parity/cypher-recipes.md` | New — saved query pack |
| `docs/parity/README.md` | Updated — lens section, zero-to-running |
| `Makefile` + `scripts/make_target_audit.json` | `graph-lens-*` targets |

## Related

- **BITB-260** — the decision record (store-of-record vs disposable-view contract)
- **BITB-262** — the artifact this imports
- **BITB-087** — the iOS port whose spec sheets this exploration cross-checks
