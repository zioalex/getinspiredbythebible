# BITB-283: Agent Manifest Coverage Gap — `default-wf3` Absent From the Canonical Deployment Folder; `desktop` Manifest Unverified and Unpinned

**Status:** 🔄 In progress — PR #1272 (`agent-wf3.yaml` + parity tests added; desktop verification is an unticked owner step)
**Priority:** P2
**Size:** S
**Created:** 2026-11-09
**Incident:** 2026-11-09 ~09:10–09:56 UTC (the outage that exposed the gap)
**Sibling stories:** BITB-282 (probe budget), BITB-284 (controller ownership)

## Problem Statement (checked against the repo, 2026-11-09)

The cluster runs **three** `Agent` instances. The repo state is more nuanced
than "manifests missing" — the gap is *where* they live and whether they
are verified:

| Agent | Deployment | `k8s/kubeopencode/` (home-cluster runbook tree) | `deployment/kubeopencode/` (canonical deployment folder) | Verified vs live? | `agentImage` |
| --- | --- | --- | --- | --- | --- |
| `default-wf2` | `default-wf2-server` | `agent-default-wf2.yaml` | `agent.yaml` | yes (test-enforced parity, BITB-171/172) | pinned `…:v0.1.9-oc1.18.31` |
| `default-wf3` | `default-wf3-server` | `agent-default-wf3.yaml` | ➕ **`agent-wf3.yaml` added in this PR** | yes after this PR: the 2026-11-09 live export matches the k8s twin **field-for-field** (verified while transcribing), and a new test pins the two copies together | pinned `…:v0.1.9-oc1.18.31` |
| `desktop` | `desktop-server` | `agent-desktop.yaml` — an **"Example" sketch** (k8s README's word), unverified | none | **no** — only fragments of the live object are known (name, serviceAccountName, derived deployment/service names) | **UNPINNED — no `agentImage` set**, so `opencode-init` runs `kubeopencode-agent-opencode:latest` |

The incident-shaped problem: **the canonical folder is the blind spot.**
`deployment/kubeopencode/` is the folder its own README describes as
holding the Agent manifests ("this folder holds only the cluster-side
wiring") and the one an operator follows during an incident. During the
2026-11-09 outage, recovery analysis ("what does `default-wf3` actually
run?") had to query the live cluster for what only a manifest in the
home-cluster tree (`k8s/kubeopencode/agent-default-wf3.yaml`) knew —
recovering from the *deployment* runbook meant the second workflow agent
was invisible. `desktop` is worse: its only repo presence is an example
sketch whose fidelity to the live object is unknown.

This is the same converge-with-live discipline BITB-172 established for
`default-wf2` ("repo applies converge with live"), extended to the rest
of the fleet.

## default-wf3: canonical manifest added in this PR

`deployment/kubeopencode/agent-wf3.yaml` is transcribed from the
**verified live spec** (`kubectl -n kubeopencode-system get agent
default-wf3 -o yaml`, exported 2026-11-09): pinned
`agentImage` (`ghcr.io/zioalex/kubeopencode-agent-opencode:v0.1.9-oc1.18.31`),
`ghcr-pull` pull secret, `configRef` → `opencode-config`, credentials
(OPENCODE_API_KEY / GITHUB_TOKEN / OPENROUTER_API_KEY), persistence
(workspace 20Gi, sessions 2Gi), service account, workspace dir. While
transcribing, it was cross-checked against the existing
`k8s/kubeopencode/agent-default-wf3.yaml`: the two are **field-for-field
identical** — both faithful to the same live object.

Because two manifests now declare the same object — the exact BITB-171
shape that once stripped persistence from the live wf2 when a stale copy
was applied — the PR also extends `scripts/test_kubeopencode_manifests.py`
(the repo's established anti-drift tool):

- **T8 parity tests (new)**: `deployment/kubeopencode/agent-wf3.yaml` must
  target the same object (name/namespace) and carry a **whole-spec-identical**
  spec to `k8s/kubeopencode/agent-default-wf3.yaml`. Full-spec equality is
  deliberate: both copies claim the same live object, so any difference
  means one is stale (the wf2 parity tests use a field subset because wf2
  and wf3 are *different* objects allowed to diverge; a same-object pair is
  not).
- **T7 pin test extended**: `agent-wf3.yaml` joins the
  `test_agent_image_pinned_with_pull_secret` parametrize — no Agent
  manifest may regress to an unpinned `:latest` or lose the `ghcr-pull`
  secret.
- **T3 documentation tests extended**: every credential secret/env var
  wired in `agent-wf3.yaml` must be documented in the deployment README
  (parametrized over both deployment manifests).
- Drift-detection self-check performed (BITB-280's "a blind gate fails"
  standard): the parity assertion was verified to fail on an injected
  image-tag drift.

**Applying the manifest is deliberately an unticked owner step** (no
cluster access in this session): the first apply must be a provable
no-op —

```bash
kubectl -n kubeopencode-system diff -f deployment/kubeopencode/agent-wf3.yaml   # expect: no diff
kubectl apply -f deployment/kubeopencode/agent-wf3.yaml
kubectl -n kubeopencode-system get agent default-wf3
```

## desktop: an example sketch is not a verified manifest (owner steps)

`k8s/kubeopencode/agent-desktop.yaml` exists but the k8s README itself
calls it an **"Example `desktop` Agent"** — a design sketch (strict-tier
egress annotations, sessions-only persistence, 30m standby, **no
configRef/config, no credentials, no `agentImage`**), with no evidence it
matches the live object. The 2026-11-09 review of the live cluster knows
only fragments (name `desktop`, `serviceAccountName:
kubeopencode-agent`, derived `desktop-server` deployment / `desktop`
service) — nothing confirms the sketch's persistence/standby/annotations
are what live actually runs.

**Applying the sketch as-is would be destructive** — a `kubectl apply` of
a manifest missing fields that exist live removes them (client-side
apply diffs against last-applied; this is precisely how BITB-171 stripped
persistence from live wf2). So no manifest is added for desktop in this
PR, and none should be drafted from the sketch or from memory.

**Owner steps (unticked, in order):**

1. Export the live spec:

   ```bash
   kubectl -n kubeopencode-system get agent desktop -o yaml > /tmp/desktop-agent.yaml
   ```

2. **Diff the live export against `k8s/kubeopencode/agent-desktop.yaml`**
   and reconcile the sketch with reality: update the sketch to the
   verified live spec (stripping status/managed fields), or note where the
   sketch was never applied. Also check what the live object's config
   story is — the sketch has no `configRef`/`config`, so if faithful,
   desktop runs opencode's *default* config (no 12-agent roster, no
   fallback plugin) — confirm that is intended.
3. **Pin `spec.agentImage`** — desktop currently runs the **unpinned**
   `kubeopencode-agent-opencode:latest`, a binary-version contract risk:
   an upstream opencode bump changes the config/plugin-loader contract
   (the 2026-11-08 `Plugin export is not a function` incident class,
   BITB-269/280), and `:latest` + `IfNotPresent` makes what actually runs
   depend on the node's image cache
   (`k8s/kubeopencode/custom-opencode-image.md` → *Notes*). Recommended:
   pin to the same `ghcr.io/zioalex/kubeopencode-agent-opencode:v0.1.9-oc1.18.31`
   the other two agents run (keeps the fleet on the version the BITB-280
   live-config gate tests), unless desktop intentionally runs a different
   opencode — the owner decides while exporting.
4. Commit the verified+pinned manifest (update the k8s sketch; promote a
   copy to `deployment/kubeopencode/agent-desktop.yaml` so the canonical
   folder covers the whole fleet, mirroring what this PR did for wf3).
5. Verify convergence: `kubectl -n kubeopencode-system diff -f <manifest>`
   (expect no diff except the deliberate `agentImage` pin), apply, and
   confirm `desktop-server` stays/rolls healthy and the
   `opencode-init` log reports the pinned version
   (`kubectl -n kubeopencode-system logs <desktop-pod> -c opencode-init |
   grep -i version`).

## Rollback anchors (README addition in this PR)

`deployment/kubeopencode/README.md` gains a **"Known-good image digests
(rollback anchors)"** note recording
`kubeopencode-agent-devbox@sha256:1be2d086…` — verified working through the
2026-11-09 outage **and** verified equal to the current upstream
`:latest` tag (GHCR API check, 2026-11-09) — with the one-command
rollback pattern
(`kubectl set image deployment/<d> opencode-server=…@sha256:<digest>`)
**and** the incident caveat that a controller reconcile may revert a
deployment-level patch (cross-ref BITB-284), plus the durable
Agent-spec-level alternative (`spec.executorImage` pin), which *does*
survive reconciles.

## Requirements

1. Commit `agent-wf3.yaml` in the canonical folder from the verified
   live spec (done in this PR).
2. Keep the same-object manifest pair drift-proof: extend the manifest
   test suite with whole-spec parity + pin + documentation coverage for
   the new file (done in this PR — the BITB-171 pattern).
3. Document the `desktop` gap accurately: an unverified example sketch
   exists in the k8s tree; do **not** apply it blindly (destructive-apply
   risk); export-first owner steps above (done in this story).
4. Flag `desktop`'s unpinned `agentImage:latest` binary-contract risk and
   recommend pinning at export time (done in this story).
5. Add the rollback-anchors note to the README with the
   reconcile-reversion caveat (done in this PR; BITB-284 documents the
   mechanism).
6. Update the README `Files` and `Apply` sections so the new manifest
   and the desktop gap are discoverable (done in this PR).

## Acceptance Criteria

- [x] `deployment/kubeopencode/agent-wf3.yaml` committed, matching the
      verified live spec field-for-field (and verified identical to its
      k8s twin), formatted/annotated consistently with `agent.yaml`
- [x] Manifest test suite extended: same-object parity tests for the new
      pair (whole-spec equality + name/namespace), image-pin/pull-secret
      coverage for `agent-wf3.yaml`, credential-documentation coverage
      for both deployment manifests — all 30 tests green, and the parity
      assertion proven to fail on injected drift
- [x] `desktop` gap documented accurately (example sketch, unverified,
      destructive-apply risk) with diff-then-pin owner steps
- [x] `desktop` unpinned `agentImage:latest` binary-contract risk flagged
      with a pin recommendation
- [x] README rollback-anchors note added (known-good devbox digest,
      one-command rollback pattern, reconcile-reversion caveat
      cross-ref BITB-284, Agent-spec-level durable alternative)
- [x] README `Files`/`Apply` sections updated for `agent-wf3.yaml` and the
      desktop gap
- [ ] (owner) `kubectl -n kubeopencode-system diff -f
      deployment/kubeopencode/agent-wf3.yaml` → no diff, then apply and
      confirm `default-wf3` still converges (the apply must be a no-op)
- [ ] (owner) export the live `desktop` spec, diff it against
      `k8s/kubeopencode/agent-desktop.yaml`, reconcile the sketch, pin
      `agentImage` (recommended: `…:v0.1.9-oc1.18.31`), commit, diff-verify,
      apply — per the steps above
- [ ] (owner) confirm the `desktop` opencode binary version after the pin
      matches the pinned tag's `oc<x.y.z>` suffix (opencode-init log)
- [ ] (owner, optional) extend the manifest tests to the desktop pair
      once the verified `deployment/kubeopencode/agent-desktop.yaml` copy
      exists (whole-spec parity with the reconciled k8s sketch, mirroring
      the wf3 T8 pattern) — deferred until the export lands because a
      parity test against an unverified sketch would enforce fiction

## Out of Scope

- Changing any live agent (no cluster access in this session; all
  cluster actions are the unticked owner steps above)
- The startup-probe budget (BITB-282) and the controller-ownership
  documentation (BITB-284) — siblings in the same PR
- Restructuring the two manifest trees (one canonical folder vs the k8s
  runbook is a repo-layout question this story deliberately does not
  open; the parity tests make the duplication safe, as they already do
  for wf2)

## References

- Verified live spec source: `kubectl -n kubeopencode-system get agent
  default-wf3 -o yaml` export, 2026-11-09 (transcribed into
  `agent-wf3.yaml`; cross-checked field-for-field against
  `k8s/kubeopencode/agent-default-wf3.yaml` — identical)
- Digest verification (GHCR API, 2026-11-09):
  `sha256:1be2d086185e06572622d2ab87aa6eb93e6031c7c18953c0551869a396617669`
  == running-healthy == upstream `:latest` (image content never broken)
- BITB-171 (two manifests, one object → drift strips live fields; the
  parity-test pattern this PR extends), BITB-172 (commit hand-wired live
  state so repo applies converge; the wf2/wf3 manifests)
- BITB-128 (persistence rationale, mirrored in the manifest comments)
- `k8s/kubeopencode/custom-opencode-image.md` (why `:latest` is
  dangerous with `IfNotPresent`; why only `agentImage` carries the
  opencode binary)
- BITB-269/280 (the opencode loader/config contract that an unpinned
  binary can break)
- BITB-284 (why a deployment-level `set image` rollback can be reverted
  by a reconcile)
