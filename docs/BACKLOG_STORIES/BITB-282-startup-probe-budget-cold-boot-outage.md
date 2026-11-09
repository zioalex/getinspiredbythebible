# BITB-282: Startup-Probe Budget Too Tight for Cold Boots — 2026-11-09 Agent Outage (Slow Boot + Transient Network Dip = Kill Loop)

**Status:** 🔄 In progress (constraint documented + upstream issue drafted in this PR; the probe budget itself is not fixable from this repo — it is hardcoded in the kubeopencode controller)
**Priority:** P1
**Size:** M
**Created:** 2026-11-09
**Incident:** 2026-11-09 ~09:10–09:56 UTC (KubeOpenCode rollout outage)
**Sibling stories:** BITB-283 (missing agent manifests + rollback anchors), BITB-284 (controller re-render behavior)

## Bug Report (the outage, verified timeline)

At ~09:10 UTC on 2026-11-09 the operator synced the opencode ConfigMap
(`make sync-opencode-configmap`) and deleted the agent pods so the new
config would go live. The service was not restored until ~09:56 UTC.
The full evidence chain:

1. Operator synced the ConfigMap and deleted pods for the config to go
   live.
2. New pods pulled `ghcr.io/kubeopencode/kubeopencode-agent-devbox:latest`
   (748,791,944 bytes) in **5m33.836s (~2.2 MB/s)** — a degraded-network
   window. The node had never cached the *current* `:latest`; the healthy
   14h-old pods were running an older cached digest.
3. Startup probe failures on the `opencode-server` container (probe:
   `Get http://<podIP>:4096/session/status`): first
   `connect: connection refused` for ~65s (server process not yet bound),
   then `context deadline exceeded (Client.Timeout exceeded while
   awaiting headers)` for ~50s more (port bound but `/session/status`
   not answering while opencode init continued — plugin/npm resolution on
   the same degraded network). The container was killed at **~100–115s of
   probe failures** → kill/restart loop with backoff (`RESTARTS 5`
   observed).
4. Network conditions cleared; a later attempt booted inside the probe
   budget → Ready → service restored with **no human intervention**
   (~09:56).
5. **Critical exonerating evidence:** the running-healthy digest ==
   the digest pulled during the outage == the current upstream `:latest`
   tag, verified via the GHCR API on 2026-11-09:
   `sha256:1be2d086185e06572622d2ab87aa6eb93e6031c7c18953c0551869a39a617669`.
   The image content was never broken. An earlier "upstream broke
   `:latest`" hypothesis was explicitly retracted. Root cause: **slow
   cold boot racing a tight startup-probe budget during a transient
   network dip.**

## Root Cause Analysis (upstream source investigation, 2026-11-09)

The kubeopencode controller renders the `opencode-server` Deployment from
the `Agent` CRD (`kubeopencode.io/v1alpha1`). The startup probe is
**hardcoded** in the controller source — it is not derived from any Agent
spec field:

- Rendering: [`internal/controller/server_builder.go` lines 593–605](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/server_builder.go#L593-L605)
  (v0.1.9, commit `a54986b` — the tag the cluster runs; identical on
  current upstream `main` as of 2026-11-09):

  ```go
  StartupProbe: &corev1.Probe{
      ProbeHandler: corev1.ProbeHandler{
          HTTPGet: &corev1.HTTPGetAction{
              Path:   ServerHealthPath,   // "/session/status"
              Port:   intstr.FromInt32(port),
              Scheme: corev1.URISchemeHTTP,
          },
      },
      InitialDelaySeconds: DefaultStartupPeriodSeconds,  // 2
      PeriodSeconds:       DefaultStartupPeriodSeconds,  // 2
      TimeoutSeconds:      DefaultProbeTimeoutSeconds,   // 5
      FailureThreshold:    DefaultStartupFailureThreshold, // 30
  },
  ```

- Constants (same file, with the upstream author's own budget comment):

  ```go
  // DefaultStartupFailureThreshold is the failure threshold for the startup probe.
  // 2 + 2*30 = 62s max startup time.
  DefaultStartupFailureThreshold = 30
  // DefaultStartupPeriodSeconds is the period for the startup probe.
  DefaultStartupPeriodSeconds = 2
  ```

**The budget math, and why the incident kills landed at ~100–115s:**

| Probe state | Per-attempt cost | Wall-clock for 30 failures |
| --- | --- | --- |
| `connection refused` (server not bound) | ~instant, spaced `periodSeconds=2` | **~62s** (the author's intended budget) |
| `context deadline exceeded` (bound, endpoint hangs) | each attempt consumes the full `timeoutSeconds=5` | **up to ~150s** |

The kubelet counts *failures*, not wall-clock: when the endpoint hangs,
each failed probe stretches the effective period from 2s toward the 5s
timeout. The incident saw ~65s of fast refusals followed by ~50s of
hanging probes — a mix that exhausts `failureThreshold=30` at
**~100–115s wall clock**, exactly as observed. So the *effective* budget
lies between 62s (all-refused) and ~150s (all-hanging) — and the
requirement below (worst-case cold boot) is far beyond both.

**What the budget must cover** (work that happens between container start
and the first successful `/session/status`): the `/tools/opencode` symlink
setup, `opencode serve` startup, config load, and — the incident's killer
— **opencode plugin/npm resolution**, which hits the network. On a
degraded network that work can take minutes. The 5m33s image pull is
*not* charged to this budget (the probe starts at container start), but
it is what made the pods cold (the node had no cached current digest) and
it is the same degraded-network window in which the in-container init
work ran slowly.

### Is the probe budget expressible in the Agent spec?

**No — investigated and ruled out** on v0.1.9 and on current upstream
`main` (2026-11-09), across every plausible extension point:

| Checked location | Result |
| --- | --- |
| `AgentSpec` ([`api/v1alpha1/agent_types.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/api/v1alpha1/agent_types.go)) | no probe fields (grep for `Probe`/`probe`: zero hits) |
| `AgentPodSpec` (`spec.podSpec`) | exposes labels, annotations, scheduling, runtimeClassName, resources, securityContext, podSecurityContext, lifecycle, extraVolumes/Mounts, extraEnv, systemContainers — **no probes** |
| `SystemContainerOverrides` (`podSpec.systemContainers`) | env/volumeMounts for `openCodeInit`/`contextInit`/`gitInit`/`gitSync`/`pluginInit` only — the `opencode-server` container is not a target, and probes are not an override type |
| `AgentTemplate` spec (templateRef source) | zero probe mentions |
| Cluster `KubeOpenCodeConfig` (system CRD) | `systemImage`/`systemImagePullPolicy` (internal init containers only), proxy, clusterDomain, observability — **no probe knobs, no server-image override** |

And the deployment-level escape hatch is closed: hand-patching the
rendered Deployment's probe is reverted by the controller's reconcile,
which overwrites `existing.Spec` wholesale (see BITB-284; the hand-patch
itself *triggers* the reconcile that reverts it, typically within
seconds).

**Verdict: path (c) of the investigation plan** — the probe budget is
not spec-expressible, so this story (a) documents the constraint here
and in `deployment/kubeopencode/README.md`, (b) drafts a paste-ready
upstream issue for the kubeopencode repo requesting spec-expressible
probe overrides (same pattern as BITB-271's upstream opencode issue), and
(c) records the interim mitigation (rollback anchors, BITB-283/284)
below.

## Requirement

The `opencode-server` startup probe must tolerate worst-case cold boots:
a **~300s budget** (observed kills at ~100–115s; boot work includes
opencode plugin/npm resolution on possibly-slow networks). Concretely,
upstream should make `failureThreshold`/`periodSeconds`/
`timeoutSeconds`/`initialDelaySeconds` for the startup (and ideally
liveness/readiness) probe settable from the Agent spec — e.g.
`spec.podSpec.probes` or a `spec.startupProbe` block — with defaults no
tighter than today's.

## Interim mitigation (what we can do today, no upstream change)

1. **Do not panic-roll the image.** The 2026-11-09 outage self-healed once
   the network dip cleared: a later boot fit the (unchanged) probe budget
   and the service recovered with no human intervention. The image was
   never broken (digest verified equal to upstream `:latest`).
2. **Known-good digest rollback anchors** (BITB-283, README): if a cold
   boot outage is ever caused by image *content*, the one-command rollback
   is recorded in `deployment/kubeopencode/README.md` →
   *Known-good image digests (rollback anchors)* — with the BITB-284
   caveat that a controller reconcile may revert a deployment-level
   patch, and the durable (Agent-spec) alternative.
3. **Keep agent pods warm where possible**: the probe budget only bites
   on cold boots. `spec.persistence` (BITB-128) already preserves
   workspace/sessions across the pod replacements the config-sync
   runbook requires; the remaining cold-boot cost is image pull (node
   cache) + in-container init.
4. During an active probe-kill loop, options are: wait out the
   degraded-network window (proven to work, 2026-11-09), or suspend +
   resume the Agent (`spec.suspend`) to reset restart backoff — an
   operator judgment call, documented here for the next on-call.

## Requirements (deliverables in this story)

1. Document the constraint and the budget math (this story +
   `deployment/kubeopencode/README.md` → *What the controller owns* →
   *Startup-probe budget*).
2. Draft the paste-ready upstream issue (below), covering: the incident
   narrative with probe-failure evidence, the hardcoded probe location,
   the budget math (62s intended vs ~150s hang-stretched vs 300s
   requirement), the ask (spec-expressible probe overrides, in the
   spirit of the podSpec extension work from upstream issue #282), and
   the fact that deployment-level probe patches are reverted by the
   reconcile so no workaround exists today.
3. Record the interim mitigation (above) and the rollback anchors
   (BITB-283 lane).
4. Owner steps: file the upstream issue; track the outcome; when upstream
   ships probe fields, wire the ~300s budget into `agent.yaml`,
   `agent-wf3.yaml` (and the desktop manifest once BITB-283's owner step
   exports it) and apply.

## Acceptance Criteria

- [x] Investigation findings documented: probe rendering location, v0.1.9
      constants, budget math vs observed kill times, expressibility check
      across AgentSpec/podSpec/systemContainers/AgentTemplate/
      KubeOpenCodeConfig (all negative, on v0.1.9 and main)
- [x] Constraint documented in `deployment/kubeopencode/README.md`
      (with the probe-failure → kill-loop failure mode spelled out)
- [x] Paste-ready upstream issue drafted in this story (below), following
      the BITB-271 pattern
- [x] Interim mitigation recorded (self-heal evidence + rollback anchors
      cross-ref BITB-283/284)
- [ ] (owner) upstream issue filed against
      [kubeopencode/kubeopencode](https://github.com/kubeopencode/kubeopencode)
      (no existing issue covers it — verified 2026-11-09, the closest is
      the closed podSpec-extension request #282, which shipped without
      probes); URL recorded here and in the backlog entry
- [ ] (owner) upstream outcome tracked; when probe fields ship, set a
      ~300s startup budget in `agent.yaml` + `agent-wf3.yaml` (+ the
      desktop manifest, BITB-283) and apply — the live `kubectl apply`
      is an owner step
- [ ] (owner) after the probe budget lands, re-run the 2026-11-09
      scenario once (config-sync + pod delete during a controlled slow
      network, or at minimum verify the rendered probe shows the new
      budget: `kubectl -n kubeopencode-system get deploy default-wf2-server
      -o jsonpath='{.spec.template.spec.containers[0].startupProbe}'`)

## Upstream issue draft (paste-ready — verify against the kubeopencode

issue template before filing)

> **Title:** Agent server startup probe budget (~62s) is too tight for
> cold boots on slow networks — please make probe settings
> spec-expressible
>
> **Version:** kubeopencode v0.1.9 (controller image `kubeopencode:v0.1.9`);
> verified identical on current `main` as of 2026-11-09.
>
> **What happens:**
> The controller hardcodes the `opencode-server` startup probe in
> `internal/controller/server_builder.go`:
>
> ```yaml
> startupProbe:
>   httpGet: {path: /session/status, port: 4096}
>   initialDelaySeconds: 2
>   periodSeconds: 2
>   timeoutSeconds: 5
>   failureThreshold: 30   # source comment: "2 + 2*30 = 62s max startup time"
> ```
>
> That budget only holds when probes fail *fast*. When the port is bound
> but `/session/status` is not answering yet, each probe consumes the
> full 5s timeout, so 30 failures stretch toward ~150s wall clock — and
> the kubelet kills the container mid-boot. On 2026-11-09 we had a
> ~46-minute outage from exactly this: a transient network dip (~2.2 MB/s
> to GHCR) made cold pods pull the 748MB devbox image slowly and made
> opencode's in-container init (plugin/npm resolution) slow; the startup
> probe recorded ~65s of `connection refused` then ~50s of
> `context deadline exceeded` and killed the container at ~100–115s,
> producing a kill/restart loop (5 restarts observed). It self-healed
> when the network recovered — the image was verified fine (digest ==
> upstream `:latest`).
>
> Slow cold boots are a legitimate operating condition: first pull of the
> (large) devbox image plus plugin/npm resolution on a constrained
> network routinely exceed 62s. We would like the boot window to tolerate
> ~300s worst case.
>
> **Expected:**
>
> 1. Probe settings (`failureThreshold`, `periodSeconds`,
>    `timeoutSeconds`, `initialDelaySeconds`) settable from the Agent
>    spec — e.g. `spec.podSpec.probes` or a `spec.startupProbe` block.
>    The podSpec extension work from #282 added resources,
>    securityContext, lifecycle, annotations, extraEnv… but no probes.
> 2. Alternatively/additionally, a more forgiving default
>    `failureThreshold` for the startup probe (e.g. 2s × 150 ≈ 300s).
> 3. For completeness: the same expressibility for liveness/readiness.
>
> **No workaround exists today:** patching the rendered Deployment's
> probe is not an option — `reconcileDeployment` overwrites
> `existing.Spec` on every reconcile, so the patch is reverted (and the
> patch itself triggers the reverting reconcile via the owner watch).
>
> Happy to contribute the CRD/controller change if there is appetite.

## Out of Scope

- Fixing the probe in the upstream controller from this repo (draft +
  owner-filed issue only, BITB-271 pattern)
- The fallback-chain, plugin-loader, and config-gate work (BITB-279/
  280 — different incidents, already covered)
- Pre-pulling / node image caching strategies (would reduce cold-boot
  frequency but not fix the budget; noted as a future option only if
  upstream stalls)
- The desktop agent's unpinned `agentImage` (BITB-283's lane)

## References

- Incident timeline + digest verification: this story's *Bug Report*;
  GHCR API check 2026-11-09 (digest
  `sha256:1be2d086185e06572622d2ab87aa6eb93e6031c7c18953c0551869a39a617669`
  == upstream `:latest` == the running-healthy image)
- Probe rendering + constants (v0.1.9, `a54986b`):
  [`server_builder.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/server_builder.go#L593-L605)
- No-probe-fields Agent spec:
  [`agent_types.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/api/v1alpha1/agent_types.go)
- Reconcile overwrite (why deployment patches can't work):
  BITB-284 + [`agent_controller.go` `reconcileDeployment`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/agent_controller.go#L269-L275)
- BITB-172 / `k8s/kubeopencode/custom-opencode-image.md` (agent binary
  installed by `opencode-init` from `agentImage`; the server container is
  the generic devbox image)
- BITB-271 (the upstream-issue pattern this story follows)
- Rollback anchors: BITB-283 + README *Known-good image digests*
