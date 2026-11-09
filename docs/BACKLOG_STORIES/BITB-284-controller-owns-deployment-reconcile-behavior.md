# BITB-284: Controller Owns the Deployment — Reconcile Re-Renders Templates and Reverts Hand-Patches; Behavior Undocumented

**Status:** 🔄 In progress — PR #1272 (README section + this investigation shipped)
**Priority:** P2
**Size:** S
**Created:** 2026-11-09
**Incident:** 2026-11-09 ~09:10–09:56 UTC (where the behavior was observed)
**Sibling stories:** BITB-282 (probe budget — the gap this behavior makes
unfixable), BITB-283 (rollback anchors that must respect it)

## Problem Statement

The `kubeopencode-controller` renders each Agent's Deployment from the
Agent spec and **overwrites the entire Deployment spec on every
reconcile**. Anything hand-patched onto the Deployment (image pins,
probe tweaks, resource changes) is reverted — often within seconds,
because the patch itself *triggers* the reverting reconcile. During the
2026-11-09 outage an operator's `kubectl set image` on the deployment
was wiped exactly this way, and the BITB-172 history shows the
hand-wired custom agent image survived only until the first re-render
(that is why `agent.yaml` was committed — so repo applies *converge*
with live).

None of this was written down anywhere an operator would look before
reaching for `kubectl patch/set image` during an incident. This story
fixes the documentation gap and records the source-verified mechanism
so the next on-call doesn't burn outage minutes on patches that
cannot stick.

## Observed (2026-11-09, live cluster)

Stated as **facts observed during the incident**, kept separate from
the source investigation below:

- The `kubeopencode-controller` (image `kubeopencode:v0.1.9`) restarted
  40→41 during the outage, and Agent template re-renders accompanied
  both controller restarts and Agent spec changes.
- A deployment-level `kubectl set image` patch **was reverted by a
  reconcile** during the incident.
- The BITB-172 hand-wired agent image (wired directly on the cluster
  before the manifest existed) survived only until the first re-render.

## Investigated (upstream source, v0.1.9 = commit `a54986b`; re-checked on current `main` 2026-11-09 — identical)

### The overwrite

[`agent_controller.go` → `reconcileDeployment`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/agent_controller.go#L269-L275)
renders the desired Deployment from the Agent spec (+ template merge +
system config + contexts + configRef content read at that moment) and
then:

```go
// Update the Deployment if needed
// For now, we do a simple update of the spec
existing.Spec = desired.Spec
existing.Labels = desired.Labels
if err := r.Update(ctx, &existing); err != nil { ... }
```

**Unconditional, whole-spec overwrite** — no diff, no three-way merge, no
field preservation (the source comment confirms it is deliberate current
behavior). The Service is reconciled the same way (ClusterIP preserved
because it is immutable). So a reconcile replaces *every* Deployment
spec field with the rendered desired state.

Cheap when converged: an Update that writes an identical spec is a
server-side no-op (no new ReplicaSet, no pod rollout) — reconciles are
safe to run constantly; only *actual* template changes roll pods.

### The reconcile trigger set

From [`SetupWithManager`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/agent_controller.go#L810-L824)
and the manager setup:

| Trigger | Effect |
| --- | --- |
| `For(&Agent{})` — any Agent object change | re-render that agent |
| `Owns(&Deployment{})` — any event on the owned Deployment | re-render; includes the Deployment controller's own *status* writes (pod churn), and **the hand-patch itself** — a `kubectl set image` fires the watch that reverts it, typically within seconds |
| `Owns(&Service{})`, `Owns(&ConfigMap{})` (controller-created context ConfigMap), `Owns(&PVC{})`, `Owns(&Secret{})` (share token) | re-render on any of their events |
| `Watches(&AgentTemplate{})` | re-renders every agent referencing the template |
| `Watches(&Task{})` | re-render on task lifecycle events (quota/standby bookkeeping) |
| Controller (re)start | informers re-list → **every Agent reconciled** — matches the 2026-11-09 observation that controller restarts re-rendered templates |
| Periodic resync | no `SyncPeriod` override in the manager options ([`cmd/kubeopencode/controller.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/cmd/kubeopencode/controller.go#L98)) → controller-runtime default **~10h** re-list of everything |
| Git contexts with sync (`RequeueAfter`), standby timers | not used by our agents today (no git contexts, no standby) |

One important non-trigger: the **`configRef` ConfigMap is not watched**.
`opencode-config` is read at reconcile time
([`config_resolver.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/config_resolver.go#L110-L131))
and baked into the pod template (serve-command config or context-init).
That is why the README's sync flow requires the pod replacement: the
`kubectl delete pod` churns the Deployment's status, the `Owns(Deployment)`
watch fires, the reconcile re-renders with the *fresh* ConfigMap content,
and the changed template rolls the pods. A ConfigMap-only change with a
quiet cluster never converges on its own until the ~10h resync.

### What this means operationally

- **Never hand-patch the Deployment for anything that must survive** —
  express it in the Agent spec (the rendered spec *is* the Agent spec)
  or expect reversion. Spec-expressible today: `agentImage`,
  `executorImage`, `attachImage`, `imagePullSecrets`, `port`,
  `extraPorts`, credentials, contexts, plugins, skills, `configRef`,
  persistence, `serviceAccountName`, `suspend`, and `podSpec.*`
  (resources, securityContext, lifecycle, annotations, labels,
  scheduling, runtimeClassName, extraEnv, extraVolumes/Mounts,
  systemContainers env/volumeMount overrides).
- **What IS safe to patch across reconciles: effectively nothing in the
  Deployment's `.spec`** (and object-level `.metadata.labels` are
  overwritten too). The only durable control surface is the Agent
  object. `spec.suspend` is the one deployment-shaping field the
  controller deliberately honors (scales to 0).
- **The one legitimate use of a deployment-level hand-patch** is an
  *emergency* change while the controller is down (crash-looping) — as
  in the 2026-11-09 outage, when the controller was in restart backoff.
  Expect it to be reverted when the controller recovers; follow up with
  the Agent-spec change (see BITB-283's rollback-anchor note for the
  durable `spec.executorImage` form).
- **Probes are owned too** and are not spec-expressible anywhere — that
  is BITB-282's upstream gap; deployment-level probe patches are as
  doomed as any other.

### Controller config options relevant to images/probes

The cluster-scoped `KubeOpenCodeConfig` (system CRD) exposes
`systemImage` + `systemImagePullPolicy` (internal kubeopencode
containers only — git-init, context-init, plugin-init, git-sync
sidecars), proxy, clusterDomain, and observability. There is **no
probe knob and no server-image override** at the system level; the
server container's image comes solely from the Agent's
`spec.executorImage` (default
`ghcr.io/kubeopencode/kubeopencode-agent-devbox:latest`).

## Requirements

1. Document all of the above in `deployment/kubeopencode/README.md` in a
   **"What the controller owns"** section, explicitly separating
   observed facts from source-investigated findings (done in this PR).
2. State the operational rule (hand-patches revert; express it in the
   Agent spec; the controller-down emergency exception) and the
   ConfigMap-not-watched nuance (why the sync runbook deletes pods)
   (done in this PR).
3. Record the reconcile trigger set with source links (done in this
   story + README).
4. Record the system-config options relevant to images (no probe
   options) (done in this story + README).
5. Cross-link from BITB-283's rollback-anchor note (the
   reconcile-reversion caveat) and from BITB-282's probe gap (why a
   deployment-level probe patch cannot work) (done in this PR).

## Acceptance Criteria

- [x] README "What the controller owns" section added, observed vs
      investigated facts separated, with upstream source links (v0.1.9
      commit `a54986b`)
- [x] Reconcile trigger set documented (Agent/owned-objects watches,
      AgentTemplate/Task watches, controller restart, ~10h default
      resync; configRef ConfigMap NOT watched)
- [x] Operational guidance documented: nothing in the Deployment `.spec`
      survives reconciles; Agent spec is the only durable surface;
      emergency hand-patches only while the controller is down
- [x] Controller config options relevant to images/probes documented
      (systemImage = internal init containers only; no probe knobs)
- [x] Cross-references wired: BITB-282 (probe gap), BITB-283 (rollback
      anchors caveat)
- [ ] (owner, optional) observe the revert live once as a drill:
      `kubectl -n kubeopencode-system set image deploy/default-wf2-server
      opencode-server=<any-tag>` → confirm the field reverts to the
      Agent-spec-rendered value within seconds, and that no pod rollout
      results (identical final template)
- [ ] (owner, optional) file an upstream docs PR against
      kubeopencode/kubeopencode suggesting a "controller-owned fields /
      don't hand-patch deployments" operator note (the behavior is
      upstream-undocumented too)

## Out of Scope

- Changing the controller's behavior (upstream; would also be a
  breaking semantic change for every user — this story only documents)
- The probe-budget ask (BITB-282's lane — same reconcile-overwrite
  mechanism makes it unworkaroundable, but it is a distinct upstream
  request)
- Helm-chart-level values (we deploy the Agent CRs, not the controller
  chart; controller config knobs documented only as they affect images)

## References

- Overwrite: `reconcileDeployment` in
  [`internal/controller/agent_controller.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/agent_controller.go#L269-L275)
  ("For now, we do a simple update of the spec")
- Watch set: `SetupWithManager`,
  [same file, lines 810–824](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/agent_controller.go#L810-L824)
- Manager options (no `SyncPeriod` → ~10h controller-runtime default):
  [`cmd/kubeopencode/controller.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/cmd/kubeopencode/controller.go#L98)
- configRef read-at-reconcile (not watched):
  [`config_resolver.go`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/config_resolver.go#L110-L131)
- System config surface: `KubeOpenCodeConfig` /
  [`pod_builder.go` `systemConfig`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/pod_builder.go#L120-L136)
- Incident observations: 2026-11-09 outage (controller 40→41 restarts;
  `set image` reverted; BITB-172 hand-wired image lost to first
  re-render)
- BITB-172 (`agent.yaml` committed so repo applies converge with live),
  BITB-282 (probe budget — the gap that cannot be patched around),
  BITB-283 (rollback anchors that must account for this behavior)
