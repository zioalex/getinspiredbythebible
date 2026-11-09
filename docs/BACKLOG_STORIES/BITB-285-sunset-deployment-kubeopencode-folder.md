# BITB-285: Sunset the Obsolete `deployment/kubeopencode/` Folder — Consolidate KubeOpenCode Manifests and Docs in `k8s/kubeopencode/`

**Status:** 🎯 Todo (implementation deferred to a dedicated follow-up PR — rationale below; this PR files the story and does the BITB-283 corrections only)
**Priority:** P2
**Size:** M
**Created:** 2026-11-09
**Owner ruling:** 2026-11-09 — `k8s/kubeopencode/` is **THE canonical home** for all KubeOpenCode manifests and docs; `deployment/kubeopencode/` is **obsolete**
**Filed from:** the BITB-283 correction round on PR #1272 (which briefly added `deployment/kubeopencode/agent-wf3.yaml` under the wrong assumption that the deployment folder was canonical)

## Problem Statement

The owner has ruled: **`k8s/kubeopencode/` is the canonical home for all
KubeOpenCode manifests and docs, and `deployment/kubeopencode/` is
obsolete.** The obsolete folder still contains live-looking content that
steers every agent and operator to the wrong tree:

- `deployment/kubeopencode/agent.yaml` — a `default-wf2` Agent manifest,
  field-for-field identical to the canonical
  `k8s/kubeopencode/agent-default-wf2.yaml` (verified 2026-11-09, full
  parsed-spec equality — the twin-check found **no drift**, so removing
  the deployment copy loses nothing)
- `deployment/kubeopencode/agents.md` — the 12-agent model table
- `deployment/kubeopencode/README.md` — a ~440-line runbook that
  accumulated from merged PRs #1254 (config-sync runbook + lockstep
  plugin verification), #1259 (fallback-resilience prose), and #1260
  (pre-merge live-config checklist), with **no deprecation pointer**

Two manifests for one object is the exact BITB-171 drift shape (a stale
copy once stripped persistence from the live Agent on apply); two
*runbooks* are the same hazard for operator knowledge.

### Why agents kept landing in / looking at the wrong tree (root cause)

Three steering facts made well-intentioned work (including the original
BITB-283 pass in PR #1272) treat `deployment/kubeopencode/` as canonical:

1. **AGENTS.md's Repository Layout has no `k8s/` entry at all** — the
   tree that is actually canonical is invisible to every agent that
   reads the layout before working. (Strengthening the ruling: the
   layout's `deployment/` line already says "Terraform configs for
   Azure" — a kubeopencode subfolder there was never layout-authorized.)
2. **`deployment/kubeopencode/README.md` carries no deprecation
   pointer** — it presents itself as the deployment runbook, so an
   agent landing there has no signal that it is the wrong home.
3. **The pinned agentImage lived in `deployment/kubeopencode/agent.yaml`
   and recent docs (#1254/#1259/#1260) accumulated there** — the folder
   looked maintained and authoritative, so new work accreted to it.

Fixing AGENTS.md (layout entry + the stale pointer at ~line 300) is
therefore **root-cause prevention**, not cosmetics: without it the next
dispatched agent repeats the mistake.

## Requirements

1. **Migrate the accumulated docs** from `deployment/kubeopencode/README.md`
   into `k8s/kubeopencode/` (fitting its existing structure):
   - the ConfigMap sync runbook + lockstep plugin verification flow
     (from #1254, BITB-269) — the k8s README's *OpenCode config* section
     already has the condensed version; the full flow (pod pre-flight
     plugin tests, `make sync-opencode-configmap` ordering, post-restart
     plugin-load verification) moves in
   - the fallback-resilience prose + per-agent model table pointer
     (from #1259, BITB-279)
   - the pre-merge checklist for opencode config changes (from #1260,
     BITB-280)
   - the *Persist GitHub Copilot access* and *Persistence* sections
     (BITB-128/161 era) — check `k8s/kubeopencode/README.md` +
     `mobile-access.md` for overlap before moving; deduplicate, don't
     copy twice
2. **Reconcile the manifests** before removal (twin-checks; the k8s copy
   is canonical and wins if they differ — none differ today, verified
   2026-11-09):
   - `deployment/kubeopencode/agent.yaml` vs
     `k8s/kubeopencode/agent-default-wf2.yaml` — **verified identical**;
     safe to `git rm` the deployment copy
   - `deployment/kubeopencode/agents.md` (12-agent model table) vs the
     k8s tree — decide its canonical home (the model table mirrors the
     `agent` section of the generated `opencode.json`; either move it
     next to the k8s README's *OpenCode config* section or fold it into
     that section) and move it
3. **Replace the obsolete folder with a deprecation stub** —
   **recommendation: `git rm` the manifests and `agents.md`, keep ONLY a
   stub `deployment/kubeopencode/README.md`** that says the folder is
   obsolete, points at `k8s/kubeopencode/` (and the specific migrated
   sections), and cites this story. Rationale: the stub must remain so
   in-flight references (old PR descriptions, bookmarks, search hits)
   land somewhere truthful instead of a 404; the manifests must NOT
   remain even as "examples" — a second copy of a live object is the
   BITB-171 drift trap, and the parity tests that currently babysit the
   pair get deleted with the copy.
4. **AGENTS.md**: add the missing Repository Layout entry for `k8s/`
   (home-cluster KubeOpenCode manifests, netpols, RBAC, dev-image) and
   keep `deployment/` marked Terraform-for-Azure-only; fix the stale
   pointer at ~line 300 (the pre-merge checklist reference → its new
   location in `k8s/kubeopencode/README.md`).
5. **Repo-wide reference grep** for `deployment/kubeopencode` — every
   live hit repointed (hit list below); historical records
   (`docs/DONE/*`, merged changelog lines) are **not rewritten** — they
   document what was true at the time; the append-only changelog
   convention forbids rewording.
6. **Tests**: retarget `scripts/test_kubeopencode_manifests.py`
   constants (AGENT_YAML → `k8s/…/agent-default-wf2.yaml`, README → the
   k8s README; delete the T6 deployment↔k8s pair-parity tests with the
   copy; move the T4 readme-make-target test onto the k8s README), and
   **`scripts/test-opencode-config-live.py`** — its `AGENT_YAML`
   constant (line ~80) is the deployed-pin cross-check of the BITB-280
   live-config gate; retarget it to the k8s wf2 manifest and **re-run
   both gate modes** (`make test-opencode-config-live`,
   `--self-test`) as part of the migration PR — the gate must keep
   testing exactly what the pod runs.
7. Workflow path filters: `opencode-ci.yml` drops the
   `deployment/kubeopencode/**` entries (or keeps them harmlessly for
   the stub); `test_update.yml` drops its `!deployment/kubeopencode/**`
   exclusions.

### Repo-wide reference grep — the migration surface (re-measured 2026-11-09, after this PR's corrections)

```bash
grep -rn "deployment/kubeopencode" --exclude-dir=.git --exclude-dir=__pycache__ \
  --exclude-dir=BACKLOG_STORIES . | grep -v "^\./docs/BACKLOG.md\|^\./docs/DONE/"
```

→ **30 hits in 15 files** (the LIVE surface: code, config, workflows, and
non-story docs; the raw grep including `docs/BACKLOG_STORIES/`,
`docs/BACKLOG.md` and `docs/DONE/` history shows ~115 — those records
document what was true at the time and are not repointed, see below).
This PR's own corrections already removed the deployment-folder README
additions, so the table below is what the migration PR inherits:

| File | Hits | Action |
| --- | --- | --- |
| `scripts/test-opencode-config-live.py` | 2 + `AGENT_YAML` constant (L~80) | retarget deployed-pin cross-check to `k8s/kubeopencode/agent-default-wf2.yaml`; re-run both gate modes |
| `scripts/test_kubeopencode_manifests.py` | 4 (constants + T6 comments) | retarget constants; delete T6 pair tests; move T4 onto k8s README |
| `scripts/sync-opencode-workspace.sh` | 1 (L31 runbook pointer) | repoint to migrated runbook location |
| `scripts/generate-opencode-config.py` | 1 (L7 docstring) | historical note — reword to past tense or drop |
| `.github/workflows/opencode-ci.yml` | 3 (path filters L31/L53 + gate comment L176) | drop/keep path filters per item 7; repoint comment to k8s wf2 manifest |
| `.github/workflows/test_update.yml` | 2 (`!deployment/kubeopencode/**` L30/L53) | remove exclusions with the folder |
| `AGENTS.md` | 1 (L300 checklist pointer) | fix pointer (item 4) — the Repository Layout gap (no `k8s/` entry at L156) is a steering fact, not a grep hit |
| `Makefile` | 1 (L423 echo pointer) | repoint to k8s README |
| `.opencode/plugin/task-reliability-helpers.ts` | 1 (L106 comment) | repoint comment |
| `docs/SECURITY-KUBEOPENCODE.md` | 1 (L66) | repoint |
| `k8s/kubeopencode/README.md` | 5 (Files wf2 row, secrets comments ×2, full-runbook pointer, this PR's transitional obsolescence note) | make self-contained after migration; the transitional note self-removes with the folder |
| `k8s/kubeopencode/agent-default-wf2.yaml` | 3 (header + comments) | drop "keep in sync with deployment/…" twin language |
| `k8s/kubeopencode/role-agent.yaml` | 1 (L11 comment) | repoint |
| `k8s/kubeopencode/dev-image/README.md` | 3 (L142, L276, L280) | repoint |
| `deployment/kubeopencode/README.md` | 1 (self-reference in the apply block) | replaced by the deprecation stub |

**Open backlog stories that reference the folder (13 files, e.g.
BITB-128/154/158/161/169/170/171/172/173/236/237/269/280):** historical
narrative — leave the prose but, where a reference is load-bearing for
future work (e.g. an unticked owner step that says "update
deployment/kubeopencode/README.md"), add a one-line "(now
k8s/kubeopencode/, BITB-285)" note rather than rewriting history.

**Historical records — DO NOT touch:** `docs/DONE/*` (5 files),
`docs/BACKLOG.md` merged changelog lines, and `scripts/__pycache__/*`.

## Acceptance Criteria

- [ ] Accumulated runbook docs (sync/lockstep flow, fallback resilience,
      pre-merge checklist, copilot/persistence sections — deduplicated)
      live in `k8s/kubeopencode/` and read coherently in its structure
- [ ] `deployment/kubeopencode/` contains ONLY the stub README
      (obsolescence + pointer to `k8s/kubeopencode/` + story ref);
      `agent.yaml` and `agents.md` are `git rm`'d (or relocated for
      agents.md) — **owner-confirm the twin-check result stands at
      migration time** (re-run the parsed-spec diff; k8s copy wins on
      any drift)
- [ ] AGENTS.md Repository Layout gains the `k8s/` entry;
      `deployment/` stays Terraform-for-Azure; the ~L300 pre-merge
      checklist pointer targets the migrated location
- [ ] Repo-wide grep clean of *live* `deployment/kubeopencode`
      references (historical records excepted, per the table above)
- [ ] Manifest tests retargeted and green; the T6 deployment↔k8s pair
      tests deleted with the twin
- [ ] `scripts/test-opencode-config-live.py` retargeted to the k8s wf2
      manifest; BOTH live-gate modes re-run green in the migration PR
      (the BITB-280 gate must keep testing exactly what the pod runs)
- [ ] Conventional commits + PR; CI green
- [ ] (owner) review sign-off that the migration PR leaves no
      behavior change behind (docs + test retargets only; no cluster
      action required — the live objects already match the k8s
      manifests)

## Implementation: deferred to a dedicated follow-up PR (deliberate)

This PR (#1272) files the story and performs only the BITB-283
corrections (manifest removed, parity tests retargeted to the k8s
twins, new README sections moved into the k8s README). The migration
itself is a **separate follow-up PR**, because it rewires CI-critical
plumbing — the BITB-280 live-config gate's deployed-pin constant, ~10
manifest-test constants, two workflow path filters — plus a
~440-line runbook move, and belongs in its own reviewable, revertable
change rather than as an amendment to a review-blocked docs PR. Size
estimate: M (mostly mechanical moves + gate re-verification).

## Out of Scope

- Any cluster action (the live objects already converge with the k8s
  manifests; no apply is required by the migration)
- The desktop manifest verification/pin (BITB-283's owner steps)
- The startup-probe upstream ask (BITB-282)
- Rewriting `docs/DONE/*` history or merged changelog lines

## References

- Owner ruling 2026-11-09 (recorded in the PR #1272 correction round;
  this story is its durable record)
- BITB-171 (two-manifests-one-object drift class), BITB-172 (the
  committed-manifest convergence discipline), BITB-129 (why
  kubeopencode paths run `opencode-ci.yml` instead of the full app
  suite), BITB-280 (the live-config gate whose constant must follow the
  migration)
- BITB-283 (the correction round that surfaced the ruling; its story
  carries the wf3/wf2 twin-check verdicts: all four manifests verified
  field-for-field identical on 2026-11-09)
- Steering facts: AGENTS.md Repository Layout (no `k8s/` entry;
  `deployment/ Terraform configs for Azure`), AGENTS.md ~L300 pointer,
  the un-deprecated deployment-folder README
