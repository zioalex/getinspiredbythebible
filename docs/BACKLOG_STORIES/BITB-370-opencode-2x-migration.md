---
id: BITB-370
status: in-progress
priority: P1
size: L
created: 2026-11-26
prs: [1347]
follow_ups: [BITB-371]
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
4. Read-only research spike before any code changes (delivered — see
   *Phase 1 findings*)

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
  `@opencode/plugin` / `@opencode/cli` — the old `opencode-ai` package line
  stops at 1.19.6 and there is **no `opencode-ai@2` on npm**
- This pod has **no cluster API access** (kubectl connection refused) —
  image build/push, `kubectl apply`, pod restarts are owner-only steps
- Canonical manifests: `k8s/kubeopencode/` (BITB-285; `deployment/kubeopencode/`
  is an obsolete stub)

## Phase 1 findings (research spike, 2026-11-26)

Delivered by [T-370A] infra-engineer and [T-370B] fullstack-engineer
(read-only; full reports in the PR #1347 discussion). Summary of what
changed in the plan:

1. **Image build is a GO — no patch needed.** The upstream
   kubeopencode `agents/opencode` Dockerfile already downloads from
   `anomalyco/opencode`; the FILENAME pattern (`opencode-linux-<arch>.tar.gz`)
   matches v2.4.2 assets exactly; the tarball contains a single top-level
   `opencode` binary; the 2.x binary is Bun-compiled and self-contained
   (no Node requirement; glibc bookworm fine; the build self-verifies with
   `--version`). Exact command recorded in *Phase 3* below.
2. **The KubeOpenCode controller is the new critical risk.** Controller
   v0.1.9 (latest upstream release, 2026-07-19) hardcodes `GET
   /session/status` as startup+readiness probe and submits tasks over 1.x
   routes (`POST /session`, `/session/:id/prompt_async`, `GET /event`).
   2.x serves `/api/*` routes with `{data}` envelopes. kubeopencode PR #349
   ("support OpenCode 2.x", xNok) — closed unmerged, superseded by the
   author's fork — re-points probes to `/api/info` and adds legacy 404
   fallbacks, implying the legacy routes are gone in 2.x. **Unverified
   directly** (nobody ran a 2.4.2 server against the legacy routes) —
   the Phase 2 live gate resolves this empirically before any cluster
   change. If legacy routes are gone, a 2.x-capable controller is a hard
   prerequisite → tracked as **BITB-371** (blocked on upstream or the fork).
3. **The current generated config is already dual-schema-valid.** The v1
   shapes we emit (`plugin`, `provider`, `agent` + per-agent `tools` +
   `permission`) are accepted by BOTH 1.18.31 and the 2.4.2 schema; the v2
   plurals are the incompatible ones pre-cutover (`plugins`/`providers`
   are silently dropped by 1.18.31 with a warning; `permissions` is FATAL
   on 1.18.31). **The dual-compat pass must NOT adopt v2 plural keys except
   the one deliberate `plugins` directory entry** (see finding 5).
4. **The runtime-fallback plugin needs 0.2.4 → 0.3.1.** 0.2.4 is a v1-API
   plugin ("V1 plugin implementations do not run in V2"); 0.3.1 supports
   OpenCode v2 and v1.18.29+ through the same package, keeps our option
   names, and keeps reading per-agent `fallback_models` (no native model
   fallback exists in 2.4.2 — `automations` is a timer/cron feature; the
   plugin stays load-bearing). On v1 hosts the entry stays in `plugin`;
   on v2 it goes in `plugins` (author's documented split).
5. **task-reliability.ts needs a dual-export rewrite + directory move.**
   2.x skips `file://` entries pointing at a single file (warning only) —
   configured local paths must be directories. Officially sanctioned dual
   shape: `export default { ...Plugin.define({id, setup}), async server()
   {...} }` — 1.18.31 (≥1.18.29) calls `server()`, 2.x calls `setup()`.
   Zero package imports (structural typing) so the 1.18.31 pod's
   `.opencode/node_modules` never needs `@opencode/plugin` pre-cutover.
   Config carries BOTH entries: v1 `plugin` file path + v2 `plugins`
   directory-package entry — each runtime skips the other's entry with a
   warning (verified non-fatal in the 1.18.31 v2-compat source).
   `client.session.abort` → `ctx.session.interrupt` in the 2.x path.
6. **Unverified items that the Phase 2 gate must exercise empirically**
   (do NOT code them blind): v1 permission action renames on 2.x
   (`bash`→`shell`, `task`→`subagent` — if not auto-remapped, the
   read-only agents' allowlists and the orchestrator's dispatch allowlist
   silently no-op); per-agent `tools`-map remap; whether 2.4.2 attempts
   the deprecated singular `plugin` entries (v1-shaped 0.2.4 would fail
   if it does); 2.x bus event shapes for the watchdog (`parentID`
   nesting, part-delta types); interrupt-mid-generation reliability.
   Note v2.4.0 removed the 5s plugin-load wait (background plugin
   loading) — the gate can no longer assume plugins are loaded before
   init; it must poll plugin evidence (`plugin.list` / `*.updated`).

## Plan (phased, each phase independently reversible)

### Phase 0 — Safety net (no changes)

Rollback anchor is the existing image tag: every phase's revert is the
one-line `agentImage` change + pod restart. The 1.18.31 image stays
pullable throughout. Lockstep pins that any migration PR must bump
together: `scripts/test-opencode-config-live.py` (`PINNED_OPENCODE_VERSION`,
cross-checked against the `oc<x.y.z>` suffix of `agentImage`),
`scripts/test_kubeopencode_manifests.py` (`CUSTOM_AGENT_IMAGE`), and the
`agentImage` tags in the Agent CRs.

### Phase 1 — Research spike ✅ DONE (2026-11-26)

See *Phase 1 findings* above.

### Phase 2 — Dual-compatible config + plugins (PR train A)

The config itself is already dual-valid, so this phase is plugin-and-gate
work:

- **task-reliability dual-export rewrite** (T-370B port map): move
  `.opencode/plugin/task-reliability.ts` into a directory
  (`.opencode/plugin/task-reliability/index.ts`, helpers stay importable),
  rewrite the module surface to `{ id, setup(ctx), server(input, options) }`
  with structural typing only; rewrite the single-export invariant test for
  the new surface; keep watchdog behavior byte-identical on the 1.18.31
  `server()` path; implement the 2.x `setup(ctx)` path with
  `ctx.session.interrupt`, `ctx.event.subscribe`, `ctx.tool.hook`
  (exact event shapes pinned empirically by the gate)
- **Generator emits dual plugin entries**: v1 `plugin` array keeps the
  file path (now the directory-internal index file) + bumps
  `opencode-runtime-fallback` to **0.3.1** (dual-host); v2 `plugins` array
  adds the directory-package entry for task-reliability + the 0.3.1
  package entry. 1.18.31 drops `plugins` with a warning (non-fatal,
  verified in its v2-compat source); 2.4.2 skips the single-file `plugin`
  entry with a warning
- **Live gate gains a 2.4.2 leg** (`scripts/test-opencode-config-live.py`):
  boot a scratch 2.4.2 instance against the committed config and
  exercise: dual plugin load evidence (poll `plugin.list` — background
  loading means no init-time guarantee), `bash`/`task` permission remap,
  `tools`-map remap, interrupt-mid-generation, and **probe the legacy
  1.x HTTP routes (`/session/status`, `POST /session`, `GET /event`) vs
  `/api/*`** — this empirically settles the controller question
  (BITB-371 go/no-go) with zero cluster changes
- **Gate classifier whitelists the expected compat warnings** (1.18.31
  "omitted plugins" diagnostic; 2.4.2 "skipped single-file plugin"
  warning) so the dual-entry design doesn't trip the failure heuristics
- All existing guards stay green; the pod keeps running 1.18.31
  throughout (the `server()` path is behavior-identical)

### Phase 3 — Custom 2.x image + wf3 canary (owner-heavy)

- Owner builds and publishes
  `ghcr.io/zioalex/kubeopencode-agent-opencode:v0.2.0-oc2.4.2`
  (verified recipe, no Dockerfile patch needed):

  ```bash
  git clone https://github.com/kubeopencode/kubeopencode && cd kubeopencode/agents
  docker login ghcr.io
  make AGENT=opencode OPENCODE_VERSION=2.4.2 IMG_ORG=zioalex \
       VERSION=v0.2.0-oc2.4.2 buildx
  ```

- **Precondition — controller verdict from the Phase 2 gate:** if the
  2.4.2 scratch server 404s the legacy routes, applying the image to wf3
  under controller v0.1.9 will crashloop (startup probe kills at ~62 s)
  and task submission 404s — the canary is then blocked until **BITB-371**
  (controller upgrade) lands. If legacy routes are served, proceed
- Owner applies the `agentImage` bump to **wf3 only**; canary pod restart
- Orchestrator runs smoke dispatches under 2.x (FREE lanes first, then
  one paid verifier run) and verifies: plugin loads (task-registry lines
  appear), fallback routing works, `question` deny holds, permission
  remaps hold (read-only agents stay read-only), no loader errors in the
  runtime log
- Rollback: repoint wf3 `agentImage` to `v0.1.9-oc1.18.31` (Agent-spec
  field, survives reconciles)

### Phase 4 — wf2 cutover (the primary workspace)

- Owner applies the `agentImage` bump to wf2; pod restarts onto 2.x
- Owner runs the `make sync-opencode-configmap` ritual post-restart
- Orchestrator dispatches the verifier for full suites + live-config gate
  on 2.4.2; confirms task-reliability registry lines and smoke dispatches
- Rollback: repoint wf2 `agentImage` (config stays dual-compatible with
  1.x — that is the point of Phase 2)

### Phase 5 — Cleanup & hardening (PR train B)

- Drop deprecated shapes kept for dual-compat: per-agent `tools` maps
  (re-verify the permission remap first), reconsider `small_model`
  steering
- Post-cutover the plugin can adopt real `@opencode/plugin` imports in
  `.opencode/package.json` (structural typing was a transition
  constraint)
- Update docs that pin 1.18.31 knowledge: `custom-opencode-image.md`
  (new image + asset verification), `k8s/kubeopencode/README.md`
  runbook, `agents.md` model table, `AGENTS.md` loader-contract section
  (re-pin the empirical contract to 2.4.2; `session.abort` →
  `session.interrupt`), `sync-opencode-workspace.sh`
- `dev-image` needs NO change (carries no opencode binary — verified)

## Acceptance criteria

- [x] Phase 1 findings for both research dispatches recorded in this story
- [ ] task-reliability plugin loads on BOTH 1.18.31 and 2.4.2 scratch
      instances (dual-export surface; single-export test rewritten)
- [ ] Committed `opencode.json` boots green on BOTH 1.18.31 and 2.4.2
      scratch instances (CI live-gate legs, BITB-280 pattern), with the
      expected compat warnings whitelisted in the classifier
- [ ] Live gate on 2.4.2 empirically records: legacy-route probe results
      (controller verdict), `bash`/`task` permission remap behavior,
      `tools`-map remap, interrupt-mid-generation result
- [ ] All existing guards green: `verify-opencode-config` (12 agents,
      fallback_models, runtime-fallback plugin), live-gate self-test,
      `test-opencode-plugin`, manifest/netpol tests
- [ ] Owner step: v0.2.0-oc2.4.2 image built and published to GHCR
- [ ] Owner step (conditional on controller verdict): wf3 `agentImage`
      applied; canary green (plugin loads, fallback routes, question-deny
      holds, permission remaps hold, smoke dispatches succeed)
- [ ] Owner step: wf2 `agentImage` applied + post-restart sync runbook run
- [ ] Orchestrator: verifier dispatch green on the 2.x pod; registry lines
      present; live-config gate green against the pod's actual version
- [ ] Docs updated (custom-opencode-image.md, README runbook, agents.md,
      AGENTS.md) with no stale 1.18.31-only claims left as live truth
- [ ] Rollback path documented (one-line `agentImage` revert + restart)
- [ ] BITB-371 outcome recorded (controller upgraded / confirmed
      compatible / blocked)

## Out of scope

- `agent-desktop.yaml` (suspended; upgrades by the same recipe when
  reactivated)
- KubeOpenCode controller upgrade work itself → **BITB-371**
- Adopting new 2.x features (automations, policies, enterprise, layout) —
  follow-up stories after the migration lands
- llama.cpp server / provider fleet changes (BITB-365 track)
- The `impaginai` project (separate tree)

## Open questions (post-research; all resolvable by the Phase 2 gate)

1. ~~2.x release-asset naming~~ — RESOLVED: pattern matches, no patch
   needed (T-370A)
2. ~~Plugin loader contract / file:// support~~ — RESOLVED: 2.x requires
   directory entries; dual-entry plan adopted (T-370B)
3. ~~runtime-fallback 2.x compat / native fallback~~ — RESOLVED: bump to
   0.3.1; no native fallback exists (T-370B)
4. ~~`tools` redundancy on 1.18.31~~ — RESOLVED: `tools` maps are an
   enablement overlay on 1.x (dropping them changes exposed tool sets);
   keep through the dual phase, drop at Phase 5 after remap verification
5. ~~`setCacheKey`/provider options~~ — RESOLVED: all still defined in the
   2.4.2 schema (T-370B)
6. **Does 2.4.2 serve the legacy 1.x HTTP routes?** — settles whether
      controller v0.1.9 can run a 2.x agent unmodified (BITB-371
      go/no-go). Phase 2 gate probes this empirically
7. **Are v1 permission action names remapped on 2.x** (`bash`→`shell`,
      `task`→`subagent`)? If not, read-only agents and the orchestrator's
      dispatch allowlist silently degrade — gate must verify before any
      cluster change
8. **2.x bus event shapes** for the watchdog (`parentID` nesting,
      part-delta equivalents) — pinned empirically during the gate work

## Follow-ups

- **BITB-371** — KubeOpenCode controller 2.x compatibility (probe path +
  API routes; xNok fork PR #349 vs upstream wait). Blocks Phase 3/4 iff
  the Phase 2 gate proves legacy routes are gone.
