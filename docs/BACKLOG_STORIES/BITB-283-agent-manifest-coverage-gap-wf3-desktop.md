# BITB-283: desktop Agent Manifest Unverified and Unpinned; wf3 Live-Spec Verification; KubeOpenCode Manifest Home Ruled `k8s/` (Owner Correction)

**Status:** 🔄 In progress — PR #1272 (desktop verification + upstream-adjacent steps are unticked owner steps)
**Priority:** P2
**Size:** S
**Created:** 2026-11-09
**Incident:** 2026-11-09 ~09:10–09:56 UTC (the outage that exposed the gap)
**Sibling stories:** BITB-282 (probe budget), BITB-284 (controller ownership), BITB-285 (folder sunset — filed from this story's correction)

## Correction (owner ruling, 2026-11-09 — supersedes this story's original framing)

The original pass framed `deployment/kubeopencode/` as "the canonical
deployment folder", added `deployment/kubeopencode/agent-wf3.yaml` there,
and put the new README sections in `deployment/kubeopencode/README.md`.
**The owner ruled the opposite: `k8s/kubeopencode/` is THE canonical home
for all KubeOpenCode manifests and docs; `deployment/kubeopencode/` is
obsolete.** Corrections applied in the same PR:

- `deployment/kubeopencode/agent-wf3.yaml` **removed** — the canonical
  tree already had `k8s/kubeopencode/agent-default-wf3.yaml`, verified
  field-for-field faithful to the live spec (below), so the deployment
  copy added nothing but a BITB-171 drift trap.
- The parity tests retargeted to the **k8s twins** (whole-spec
  `agent-default-wf2.yaml` ↔ `agent-default-wf3.yaml` parity — see
  `scripts/test_kubeopencode_manifests.py` T8).
- The controller-ownership, probe-budget, and rollback-anchor README
  sections moved to **`k8s/kubeopencode/README.md`**.
- The folder sunset + steering-facts root cause is filed as **BITB-285**.

What survives of the original story: the desktop gap (unverified sketch,
unpinned binary), the rollback anchors, and the live-spec verification of
the wf3 manifest — all now documented against the canonical tree.

## Problem Statement (checked against the repo + owner ruling, 2026-11-09)

The cluster runs **three** `Agent` instances. The canonical manifest home
is `k8s/kubeopencode/` (owner ruling), whose state is:

| Agent | Deployment | `k8s/kubeopencode/` (canonical) | Verified vs live? | `agentImage` |
| --- | --- | --- | --- | --- |
| `default-wf2` | `default-wf2-server` | `agent-default-wf2.yaml` | yes — twin-checked 2026-11-09 against the deployment-folder copy: **full parsed-spec equality, no drift**; test-enforced (BITB-171/172) | pinned `…:v0.1.9-oc1.18.31` |
| `default-wf3` | `default-wf3-server` | `agent-default-wf3.yaml` | **yes after this PR** — verified field-for-field against the 2026-11-09 live export during the original transcription pass (the since-removed deployment copy was identical to it; the k8s manifest IS that same faithful text) | pinned `…:v0.1.9-oc1.18.31` |
| `desktop` | `desktop-server` | `agent-desktop.yaml` — an **example sketch** (the k8s README's word), unverified | **no** — only fragments of the live object are known (name, serviceAccountName, derived deployment/service names) | **UNPINNED — no `agentImage` set**, so `opencode-init` runs `kubeopencode-agent-opencode:latest` |

The real gaps this story closes:

1. **desktop** — its only repo presence is an unverified sketch whose
   fidelity to the live object is unknown, and its init container runs an
   **unpinned `:latest`** binary (contract risk, below).
2. **No rollback anchor was on record** for the devbox executor image —
   added to the canonical README in this PR.
3. **wf3's live fidelity was undocumented** — the manifest existed and was
   faithful (validated on the home cluster 2026-09-30, BITB-172), but the
   2026-11-09 outage recovery had to re-derive it from the live cluster;
   this PR records the verification (and hardens it with a whole-spec
   wf2↔wf3 parity test).

The *original* framing — "the canonical deployment folder lacks a wf3
manifest" — was an artifact of the steering docs (AGENTS.md's Repository
Layout has no `k8s/` entry; the deployment-folder README carried no
deprecation pointer): the canonical tree was invisible, so work accreted to
the obsolete one. Root-cause prevention is BITB-285's lane.

## default-wf3: k8s manifest verified; deployment copy added-then-removed

The original pass transcribed the **verified live spec**
(`kubectl -n kubeopencode-system get agent default-wf3 -o yaml`, exported
2026-11-09) into `deployment/kubeopencode/agent-wf3.yaml` and, while
transcribing, cross-checked it against the existing
`k8s/kubeopencode/agent-default-wf3.yaml`: **field-for-field identical** —
both faithful to the same live object. Under the owner ruling the
deployment copy was redundant (a second manifest for one object is the
BITB-171 drift class) and has been **removed from this PR**.

The verification's durable value is redirected into the test suite
(`scripts/test_kubeopencode_manifests.py`, T8):

- **Whole-spec parity, k8s twins**: `agent-default-wf2.yaml` ↔
  `agent-default-wf3.yaml` specs must be *fully equal* — upgrading the
  T7 field-subset check, which stays green on one-sided additions (a
  field gained by only one twin would ship silently). wf3's documented
  contract (its own header) is "the wf2 shape under a new name" with
  nothing spec-level differing.
- Image-pin/pull-secret coverage of the k8s wf3 manifest (T7) already
  existed and stays.

**Applying anything remains an owner step** (no cluster access in this
session); with the deployment copy removed there is nothing new to apply
for wf3 — the canonical manifest already converges with live. The wf2
twin-check (2026-11-09) found **no drift** between the deployment and k8s
copies, so BITB-285's eventual `git rm` of the deployment copy loses
nothing.

## desktop: an example sketch is not a verified manifest (owner steps)

`k8s/kubeopencode/agent-desktop.yaml` exists but the k8s README itself
calls it an **"Example `desktop` Agent"** — a design sketch (strict-tier
egress annotations, sessions-only persistence, 30m standby, **no
configRef/config, no credentials, no `agentImage`**), with no evidence it
matches the live object. The 2026-11-09 review of the live cluster knows
only fragments (name `desktop`, `serviceAccountName: kubeopencode-agent`,
derived `desktop-server` deployment / `desktop` service) — nothing
confirms the sketch's persistence/standby/annotations are what live
actually runs.

**Applying the sketch as-is would be destructive** — a `kubectl apply` of
a manifest missing fields that exist live removes them (client-side apply
diffs against last-applied; this is precisely how BITB-171 stripped
persistence from live wf2). So no manifest is added or edited for desktop
in this PR.

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
4. Commit the verified+pinned manifest (update the k8s sketch; the k8s
   README's Files-table entry for it already flags the unverified status
   and points here).
5. Verify convergence: `kubectl -n kubeopencode-system diff -f
   k8s/kubeopencode/agent-desktop.yaml` (expect no diff except the
   deliberate `agentImage` pin), apply, and confirm `desktop-server`
   stays/rolls healthy and the `opencode-init` log reports the pinned
   version (`kubectl -n kubeopencode-system logs <desktop-pod> -c
   opencode-init | grep -i version`).
6. (Optional) extend `scripts/test_kubeopencode_manifests.py` to guard
   the verified desktop manifest (e.g. image-pin coverage once pinned) —
   deferred until the export lands because a test against an unverified
   sketch would enforce fiction.

## Rollback anchors (canonical README, added in this PR)

`k8s/kubeopencode/README.md` gains a **"Known-good image digests
(rollback anchors)"** note recording
`kubeopencode-agent-devbox@sha256:1be2d086…` — verified working through the
2026-11-09 outage **and** verified equal to the current upstream
`:latest` tag (GHCR API check, 2026-11-09) — with the one-command rollback
pattern (`kubectl set image deployment/<d> opencode-server=…@sha256:<digest>`)
**and** the incident caveat that a controller reconcile may revert a
deployment-level patch (cross-ref BITB-284), plus the durable
Agent-spec-level alternative (`spec.executorImage` pin), which *does*
survive reconciles. (Originally added to the obsolete deployment README;
moved to the canonical README in the correction round.)

## Requirements

1. Record the wf3 manifest's live fidelity and harden it with whole-spec
   k8s twin parity tests (done in this PR).
2. Document the `desktop` gap accurately: an unverified example sketch;
   do **not** apply it blindly (destructive-apply risk); diff-then-pin
   owner steps above (done in this story + the k8s README Files entry).
3. Flag `desktop`'s unpinned `agentImage:latest` binary-contract risk and
   recommend pinning at export time (done).
4. Add the rollback-anchors note to the canonical README with the
   reconcile-reversion caveat (done in this PR; BITB-284 documents the
   mechanism).
5. File the folder-sunset story with the steering-facts root cause
   (done — BITB-285).

## Acceptance Criteria

- [x] wf3 manifest verified field-for-field against the 2026-11-09 live
      export and recorded here; whole-spec wf2↔wf3 parity test added
      (one-sided-addition gap closed); manifest suite green
- [x] `deployment/kubeopencode/agent-wf3.yaml` removed per the owner
      ruling (the canonical k8s tree already had the faithful manifest;
      adding a second copy was the BITB-171 drift shape)
- [x] `desktop` gap documented accurately (example sketch, unverified,
      destructive-apply risk) with diff-then-pin owner steps, plus the
      k8s README Files-entry flag
- [x] `desktop` unpinned `agentImage:latest` binary-contract risk flagged
      with a pin recommendation
- [x] Rollback-anchors note added to `k8s/kubeopencode/README.md`
      (known-good devbox digest, one-command rollback pattern,
      reconcile-reversion caveat cross-ref BITB-284, durable Agent-spec
      `executorImage` form)
- [x] Folder-sunset story filed with the steering-facts root cause
      (BITB-285)
- [ ] (owner) export the live `desktop` spec, diff it against
      `k8s/kubeopencode/agent-desktop.yaml`, reconcile the sketch, pin
      `agentImage` (recommended: `…:v0.1.9-oc1.18.31`), commit, diff-verify,
      apply — per the steps above
- [ ] (owner) confirm the `desktop` opencode binary version after the pin
      matches the pinned tag's `oc<x.y.z>` suffix (opencode-init log)
- [ ] (owner, optional) extend the manifest tests to the verified desktop
      manifest once the export lands

## Out of Scope

- Changing any live agent (no cluster access in this session; all
  cluster actions are the unticked owner steps above)
- The startup-probe budget (BITB-282) and the controller-ownership
  documentation (BITB-284) — siblings in the same PR
- The obsolete-folder sunset itself (BITB-285: runbook migration,
  AGENTS.md layout fix, stub, reference repointing, gate retargeting)
- Restructuring the two manifest trees beyond what the ruling required
  (the deployment copies stay until BITB-285 removes them properly)

## References

- Verified live spec source: `kubectl -n kubeopencode-system get agent
  default-wf3 -o yaml` export, 2026-11-09 (compared field-for-field
  against `k8s/kubeopencode/agent-default-wf3.yaml` — identical)
- wf2 twin-check (2026-11-09): `k8s/kubeopencode/agent-default-wf2.yaml`
  == `deployment/kubeopencode/agent.yaml` full parsed-spec equality — no
  drift; the k8s copy is canonical per the owner ruling
- Digest verification (GHCR API, 2026-11-09):
  `sha256:1be2d086185e06572622d2ab87aa6eb93e6031c7c18953c0551869a39a617669`
  == running-healthy == upstream `:latest` (image content never broken)
- Owner ruling 2026-11-09: `k8s/kubeopencode/` canonical,
  `deployment/kubeopencode/` obsolete (durable record: BITB-285)
- BITB-171 (two manifests, one object → drift strips live fields; the
  parity-test pattern), BITB-172 (commit hand-wired live state so repo
  applies converge)
- BITB-128 (persistence rationale), BITB-269/280 (the opencode
  loader/config contract that an unpinned binary can break)
- BITB-284 (why a deployment-level `set image` rollback can be reverted
  by a reconcile), BITB-285 (the folder sunset + steering-facts root cause)
