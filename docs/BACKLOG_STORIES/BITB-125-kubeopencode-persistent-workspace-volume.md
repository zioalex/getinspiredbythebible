# BITB-125: Persistent KubeOpenCode Workspace Volume

**Priority:** P2 (Medium)
**Status:** 🎯 Todo
**Size:** M (1-2 days)
**Created:** 2026-09-12
**Affects:** `deployment/kubeopencode/` only — no application code

---

## Background

`deployment/kubeopencode/agent.yaml` declares `spec.workspaceDir: /workspace` but
attaches **no volume**. The agent pod's filesystem is therefore ephemeral: every
pod replacement destroys everything under `/workspace` and `/tmp`.

This is not an edge case — the project's own documented workflow *requires*
routine pod deletion. `deployment/kubeopencode/README.md` states:

> Updating a ConfigMap does not restart anything that already mounted it, so the
> running agent keeps serving the previous config until its pod is replaced:
> `kubectl -n kubeopencode-system delete pod <agent-pod>`

So every time an agent definition changes (`make sync-opencode-configmap` →
delete pod), the workspace is wiped. Node eviction, OOM kill, and cluster
upgrades do the same without warning.

**What is lost on every restart:**

| Lost | Consequence |
|---|---|
| The cloned repo + any uncommitted work | Silent loss of in-progress agent work; no error, the next session just starts empty |
| Git worktrees (`AGENTS.md` mandates `/tmp/<short-name>`) | Branches with unpushed commits vanish |
| `node_modules`, pip wheels, Gradle caches | Every session re-runs `npm ci` / `pip install` / Gradle sync from scratch |
| Re-clone of a 1,291-commit repo | Slow cold start on every single session |

The caching loss also has a second-order cost: repeated dependency downloads and
re-clones burn network and can hit registry rate limits.

---

## User Story

**As a** developer running the agent graph on KubeOpenCode,
**I want** `/workspace` and the toolchain caches backed by PersistentVolumeClaims,
**so that** a pod restart — routine or unexpected — does not destroy in-progress
work or force a full re-clone and dependency reinstall.

---

## ⚠️ Gate: verify the CRD surface first

`AgentSpec` is known to have **no** top-level `model`/`provider` fields (see the
README notes), so it cannot be assumed to expose volumes either. **Before any
implementation**, confirm how KubeOpenCode v0.1.8+ exposes storage:

```bash
kubectl explain agent.spec --recursive | grep -iE 'volume|storage|pvc|persist'
kubectl get crd agents.kubeopencode.io -o yaml | grep -iE 'volume|storage'
```

Outcomes:

- **(a) A native volume/volumeMounts field exists** → implement as designed below.
- **(b) A pod-template passthrough exists** → mount the PVCs through it.
- **(c) Neither exists** → do **not** fake it. Record the finding, open an
  upstream issue, and reduce this story to the documented interim mitigation
  (below). Re-open when the CRD supports it.

**Interim mitigation if (c):** document in the README that the workspace is
ephemeral, and that agents must push work to a remote branch before any
`kubectl delete pod` — never rely on pod-local state surviving.

---

## Design

Two claims, deliberately split so that cache bloat cannot fill the volume that
holds actual work:

| PVC | Mount | Size | Holds |
|---|---|---|---|
| `opencode-workspace` | `/workspace` | 20Gi | Cloned repo, branches, in-progress edits |
| `opencode-cache` | `~/.npm`, `~/.cache/pip`, `~/.gradle`, `~/.cache/opencode` | 10Gi | Toolchain caches — disposable, safe to delete |

Design decisions:

1. **`ReadWriteOnce`, single agent replica.** RWO is the portable default. If the
   graph is ever scaled past one replica the workspace PVC must move to an RWX
   class (e.g. `azurefile-csi`); this constraint is documented, not silently
   assumed.
2. **No hardcoded `storageClassName`.** Omit it so the cluster default applies,
   keeping the manifest portable. Document how to pin it.
3. **`/tmp` worktrees.** `AGENTS.md` mandates `git worktree add /tmp/<short-name>`.
   `/tmp` is *not* on the PVC, so worktrees would still be destroyed — which is
   exactly where unpushed commits live. Resolve explicitly: either mount a
   workspace subpath at `/tmp/opencode` and update the `AGENTS.md` guidance to
   use it, or state plainly that worktrees are ephemeral. Do not leave this
   ambiguous.
4. **Filesystem ownership.** A freshly provisioned PVC mounts root-owned. If the
   agent container runs as non-root it will fail to write — the single most
   common failure mode for this change. Set `fsGroup` (or the CRD's equivalent)
   and verify the agent can actually write before closing the story.
5. **Persistence is not free of risk.** A persistent `/workspace` accumulates
   stale branches, and anything an agent writes to disk now survives. Ship a
   documented reset path and an explicit "no credentials written to the PVC"
   check.

---

## Functional Requirements

- [ ] CRD storage support confirmed and recorded in the story before implementing
- [ ] `deployment/kubeopencode/pvc.yaml` defines `opencode-workspace` (20Gi, RWO)
      and `opencode-cache` (10Gi, RWO) in `kubeopencode-system`, with no
      hardcoded `storageClassName`
- [ ] `agent.yaml` mounts `opencode-workspace` at `spec.workspaceDir`
      (`/workspace`) and `opencode-cache` at the toolchain cache paths
- [ ] Filesystem ownership configured so the agent user can write to both mounts
- [ ] `/tmp` worktree behaviour explicitly resolved (persisted via subpath, or
      documented as ephemeral) and `AGENTS.md` updated if the guidance changes
- [ ] `README.md` updated: PVC prerequisite listed **before** the Agent apply
      step (same ordering rule the ConfigMap already follows), plus the RWO /
      single-replica constraint, how to pin a `storageClassName`, and a reset
      procedure for a corrupted or bloated workspace
- [ ] No secret material is written to either PVC; `detect-secrets` stays green

## Non-Functional Requirements

- [ ] `make pre-commit` passes (check-yaml, yamllint, prettier, markdownlint)
- [ ] Manifests validate against the cluster: `kubectl apply --dry-run=server`
- [ ] Volume manifests covered by the automated checks added in **BITB-126**

---

## Verification

1. `kubectl apply -f deployment/kubeopencode/pvc.yaml` → both PVCs reach `Bound`.
2. `kubectl apply -f deployment/kubeopencode/agent.yaml` → agent reaches ready.
3. **Persistence proof:**

   ```bash
   kubectl -n kubeopencode-system exec <agent-pod> -- \
     sh -c 'echo bitb-125 > /workspace/persistence-probe.txt'
   kubectl -n kubeopencode-system delete pod <agent-pod>
   # wait for the replacement pod
   kubectl -n kubeopencode-system exec <new-agent-pod> -- \
     cat /workspace/persistence-probe.txt   # must print: bitb-125
   ```

4. **Write-permission proof:** the agent (not `kubectl exec` as root) creates a
   file under `/workspace` and under a cache path.
5. **Cache proof:** time `npm ci` in a fresh pod; the second run after a pod
   replacement is materially faster and does not re-download the full tree.
6. **Reset proof:** the documented reset procedure restores a clean workspace.

---

## Out of Scope

- Multi-replica / RWX storage (documented as a constraint, not implemented)
- Backup or snapshot policy for the workspace PVC
- Any change to application runtime storage (Azure Container Apps, PostgreSQL)

---

## Related

- `deployment/kubeopencode/agent.yaml` — `spec.workspaceDir: /workspace`, no volume
- `deployment/kubeopencode/README.md` — the `delete pod` step that makes loss routine
- `AGENTS.md` → *Git Worktree Pattern* — the `/tmp/` mandate this must reconcile
- BITB-123 — created `deployment/kubeopencode/`
- BITB-126 — CI coverage for these manifests
