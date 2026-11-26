---
id: BITB-370
status: in-progress
priority: P1
size: L
created: 2026-11-26
prs: []
---

# BITB-370: Migrate KubeOpenCode from opencode 1.18.31 to opencode 2.4.2

## User story

As the owner, I want the KubeOpenCode agent pods (wf2, wf3) moved from
opencode 1.18.31 (custom image `ghcr.io/zioalex/kubeopencode-agent-opencode:v0.1.9-oc1.18.31`)
to opencode 2.4.2, with the generated `opencode.json` remaining loadable at
every intermediate step, so the fleet gains the 2.x runtime (new plugin API,
native surface: automations/policies/enterprise) without a broken session,
a stuck agent, or an unrecoverable state.

**Decisions confirmed with the owner (2026-11-26):**

1. Target version: **v2.4.2** (latest patch, canary absorbs soak risk)
2. Cutover: **canary** — wf3 first, wf2 after canary is green
3. Config sequencing: **dual-compatible first** — config loads on BOTH
   1.18.31 and 2.4.2 before the image changes; the image bump is then a
   single-variable change
4. Read-only research spike dispatched before any code changes

## Current state (verified 2026-11-26)

- opencode **1.18.31** pinned in three places: pod CLI, `@opencode-ai/plugin`
  dep in `.opencode/package.json`, custom agent image tag on all three Agent
  CRs (`agent-default-wf2.yaml`, `agent-default-wf3.yaml`, suspended
  `agent-desktop.yaml`)
- Generated `opencode.json` (`scripts/generate-opencode-config.py`) uses
  1.x-era shapes: per-agent `tools` maps (deprecated in the 2.x schema —
  "Use 'permission' field instead"), `fallback_models` consumed by the
  `opencode-runtime-fallback@0.2.4` npm plugin, and the task-reliability
  plugin loaded via absolute `file:///` path under the empirically-pinned
  1.18.31 single-export loader contract (BITB-269)
- Guards that must stay green throughout: `make verify-opencode-config`,
  `make test-opencode-config-live` + `--self-test`, `make test-opencode-plugin`,
  `make sync-opencode-configmap` runbook, `test_kubeopencode_manifests.py`
- 2.x facts (verified upstream): repo moved `sst/opencode` →
  `anomalyco/opencode`; 2.x GA line starts v2.2.0 (2026-10-27), v2.4.2
  released 2026-11-26; 2.x ships on npm as `@opencode/core` /
  `@opencode/plugin` ("OpenCode V2 plugin" authoring + loader support) —
  the old `opencode-ai` package line stops at 1.19.6 and there is **no
  `opencode-ai@2` on npm**; the 2.x schema keeps our top-level keys
  (`plugin`/`agent`/`command`/…, plural aliases also present) and tolerates
  `fallback_models` as an additional agent property
- This pod has **no cluster API access** (kubectl connection refused) —
  image build/push, `kubectl apply`, pod restarts are owner-only steps
- Canonical manifests: `k8s/kubeopencode/` (BITB-285; `deployment/kubeopencode/`
  is an obsolete stub)

## Plan (phased, each phase independently reversible)

### Phase 0 — Safety net (no changes)

Rollback anchor is the existing image tag: every phase's revert is the
one-line `agentImage` change + pod restart. The 1.18.31 image stays
pullable throughout.

### Phase 1 — Research spike (read-only, dispatched [T-370A]/[T-370B])

Verify the unknowns before writing code (see *Open questions*). Findings
are appended to this story; a go/no-go is recorded per question.

### Phase 2 — Dual-compatible config (PR train A)

Update `scripts/generate-opencode-config.py` so the committed `opencode.json`
loads cleanly on **both** 1.18.31 and 2.4.2:

- `tools` deprecation: if permission rules alone provably cover tool
  enablement on 1.18.31, drop `tools`; otherwise keep it (2.x still parses
  it, deprecated) and drop it in Phase 5
- `fallback_models` and the runtime-fallback plugin entry: keep unless
  research proves 2.x-native fallback should replace them (owner decision)
- `file:///` task-reliability plugin entry: keep; port path per research
- Live gate learns a second leg: boot a scratch **2.4.2** instance against
  the committed config in CI, alongside the pod-version leg

The pod and laptops keep running 1.18.31 the whole time — the config is
proven dual-loadable before anything else moves.

### Phase 3 — Custom 2.x image + wf3 canary

- Owner builds and publishes
  `ghcr.io/<ns>/kubeopencode-agent-opencode:v0.2.0-oc2.4.2` (recipe per
  `k8s/kubeopencode/custom-opencode-image.md`, adjusted per research)
- Owner applies the `agentImage` bump to **wf3 only**; canary pod restart
- Orchestrator runs smoke dispatches under 2.x (FREE lanes first, then one
  paid verifier run) and verifies: plugin loads (task-registry lines
  appear), fallback routing works, `question` deny holds, no loader errors
  in the runtime log

### Phase 4 — wf2 cutover (the primary workspace)

- Owner applies the `agentImage` bump to wf2; pod restarts onto 2.x
- Owner runs the `make sync-opencode-configmap` ritual post-restart
- Orchestrator dispatches the verifier for full suites + live-config gate
  on 2.4.2; confirms task-reliability registry lines and smoke dispatches

### Phase 5 — Cleanup & hardening (PR train B)

- Drop deprecated shapes kept for dual-compat (e.g. `tools` if retained)
- Bump `.opencode/package.json` to the 2.x plugin package if/when the
  task-reliability plugin ports
- Update docs that pin 1.18.31 knowledge: `custom-opencode-image.md`
  (new image + 2.x asset-naming notes), `k8s/kubeopencode/README.md`
  runbook, `agents.md` model table, `AGENTS.md` loader-contract section
  (re-pin empirical contract to 2.4.2), `sync-opencode-workspace.sh`
- Rebuild `k8s/kubeopencode/dev-image/` on 2.x for kind-cluster testing

## Acceptance criteria

- [ ] Phase 1 findings for both research dispatches recorded in this story
- [ ] Committed `opencode.json` boots green on BOTH 1.18.31 and 2.4.2
      scratch instances (CI live-gate legs, BITB-280 pattern)
- [ ] All existing guards green: `verify-opencode-config` (12 agents,
      fallback_models, runtime-fallback plugin), live-gate self-test,
      `test-opencode-plugin`, manifest/netpol tests
- [ ] Owner step: v0.2.0-oc2.4.2 image built and published to GHCR
- [ ] Owner step: wf3 `agentImage` applied; canary green (plugin loads,
      fallback routes, question-deny holds, smoke dispatches succeed)
- [ ] Owner step: wf2 `agentImage` applied + post-restart sync runbook run
- [ ] Orchestrator: verifier dispatch green on the 2.x pod; registry lines
      present; live-config gate green against the pod's actual version
- [ ] Docs updated (custom-opencode-image.md, README runbook, agents.md,
      AGENTS.md) with no stale 1.18.31-only claims left as live truth
- [ ] Rollback path documented (one-line `agentImage` revert + restart)
- [ ] Follow-up stories filed for anything discovered and deferred

## Out of scope

- `agent-desktop.yaml` (suspended; upgrades by the same recipe when
  reactivated)
- Adopting new 2.x features (automations, policies, enterprise, layout) —
  follow-up stories after the migration lands
- llama.cpp server / provider fleet changes (BITB-365 track)
- The `impaginai` project (separate tree)

## Open questions (Phase 1 research)

1. 2.x release-asset naming for the kubeopencode `agents/opencode` Dockerfile
   — `custom-opencode-image.md` explicitly warns the download step may break
   on a new major; what does v2.4.2 ship, and is the 2.x CLI distributed
   via `@opencode/core` npm instead of release binaries?
2. Plugin loader contract on 2.x: does the single-export rule (BITB-269,
   empirically pinned to 1.18.31) still hold? Do `file:///` plugin entries
   still load? Does `client.session.abort` now actually abort a
   mid-generation session?
3. `opencode-runtime-fallback@0.2.4` on the 2.x runtime: compatible,
   needs bump, or replaced by a native 2.x fallback feature?
4. Is per-agent `tools` fully redundant with `permission` on 1.18.31
   (i.e. can the compat pass drop `tools` immediately)?
5. Fate of `setCacheKey` and the `opencode` provider options block under 2.x
6. Any KubeOpenCode controller-side version coupling (agentImage is
   arbitrary to the controller, but confirm no contract drift in
   kubeopencode releases)

## Follow-ups

(none yet — filed per the same-PR rule as they surface)
