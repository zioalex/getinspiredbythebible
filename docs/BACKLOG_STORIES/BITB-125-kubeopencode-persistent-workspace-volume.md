# BITB-125: Persistent KubeOpenCode Workspace Volume

**Priority:** P2 (Medium)
**Status:** 🚧 In Progress
**Size:** S (reduced from M — the CRD provides this natively; see *Gate: resolved*)
**Created:** 2026-09-12
**Affects:** `deployment/kubeopencode/` only — no application code

---

## Background

`deployment/kubeopencode/agent.yaml` declares `spec.workspaceDir: /workspace` but
configures no persistence. The agent pod's workspace is therefore an `EmptyDir`:
every pod replacement destroys everything under it.

This is not an edge case — the project's own documented workflow *requires*
routine pod deletion. `deployment/kubeopencode/README.md` states:

> Updating a ConfigMap does not restart anything that already mounted it, so the
> running agent keeps serving the previous config until its pod is replaced:
> `kubectl -n kubeopencode-system delete pod <agent-pod>`

So every time an agent definition changes (`make sync-opencode-configmap` →
delete pod), the workspace is wiped. Node eviction, OOM kill, and cluster
upgrades do the same without warning.

The CRD's own documentation confirms the diagnosis verbatim:

> Without this, workspace uses EmptyDir and is re-initialized on every restart
> (git repos re-cloned by init containers).

**What is lost on every restart:**

| Lost | Consequence |
|---|---|
| The cloned repo + any uncommitted work | Silent loss of in-progress agent work; no error, the next session just starts empty |
| OpenCode session data (SQLite) | Conversation history gone — the agent loses all prior context |
| Git worktrees (`AGENTS.md` mandates `/tmp/<short-name>`) | Branches with unpushed commits vanish |
| Re-clone of a 1,291-commit repo | Slow cold start on every single session |

---

## User Story

**As a** developer running the agent graph on KubeOpenCode,
**I want** the workspace and session database backed by persistent volumes,
**so that** a pod restart — routine or unexpected — does not destroy in-progress
work, conversation history, or force a full re-clone.

---

## Gate: resolved (2026-09-12)

The story originally gated on whether the CRD exposes storage at all, since
`AgentSpec` is known to have no top-level `model`/`provider` fields. **Resolved
by querying the live CRD:**

```console
$ kubectl explain agent.spec.persistence --recursive
FIELD: persistence <Object>
    Persistence configures persistent storage for the Agent.
    When set, session data (and optionally workspace files) survive pod restarts.
FIELDS:
  sessions   <Object>
    size              <string>
    storageClassName  <string>
  workspace  <Object>
    size              <string>
    storageClassName  <string>
```

**Outcome (a): a native `spec.persistence` field exists.** This materially
simplifies the story and **supersedes the original design**:

- ❌ **No `pvc.yaml` is needed.** The operator creates and owns the PVCs.
- ❌ **No manual `volumeMounts`, `fsGroup`, or ownership wrangling.** The
  operator handles mounting and permissions — the most common failure mode for a
  hand-rolled PVC is simply not reachable here.
- ✅ **`storageClassName` empty ⇒ cluster default**, which is exactly the
  portability behaviour the original design wanted.
- ✅ **`sessions` persistence is a bonus** not identified in the original
  analysis: it persists the OpenCode SQLite session DB, so conversation history
  survives restarts too.

Defaults per the CRD: `sessions` 1Gi, `workspace` 10Gi.

---

## Design

Add a `persistence` block to the existing Agent in `agent.yaml`:

```yaml
spec:
  persistence:
    workspace:
      size: 20Gi
    sessions:
      size: 2Gi
```

Decisions:

1. **`workspace: 20Gi`** (over the 10Gi default). The workspace holds a
   1,291-commit clone plus `node_modules`, pip wheels, and Gradle caches across
   three toolchains (Python, Node, Android/JVM). 10Gi is tight for a Gradle cache
   alone; 20Gi is cheap insurance against a full-disk stall.
2. **`sessions: 2Gi`** (over the 1Gi default), for conversation history headroom.
3. **`storageClassName` omitted** so the cluster default applies, keeping the
   manifest portable across clusters.
4. **`/tmp` worktrees move onto the persisted volume.** `AGENTS.md` previously
   mandated `git worktree add /tmp/<short-name>`, but `persistence.workspace`
   covers `spec.workspaceDir` only — **`/tmp` is not persisted** — so unpushed
   commits in a worktree would still be lost on every restart. Resolved (not
   merely documented): `AGENTS.md` now derives the worktree root from
   `${WORKSPACE_DIR:-/tmp}/worktrees`, so agents get the PVC-backed path while a
   developer machine keeps `/tmp`. Because the repo is checked out *at*
   `$WORKSPACE_DIR`, `worktrees/` is added to `.gitignore` — otherwise worktrees
   appear as untracked files and are destroyed by `git clean -fdx`.
5. **Persistence is not free of risk.** A persistent workspace accumulates stale
   branches, and anything written to disk now survives. Document a reset path
   (delete the PVC and let the operator re-provision) and keep the
   no-secrets-on-disk expectation explicit.
6. **Access mode is operator-owned.** The CRD does not expose `accessModes`, so
   do not assert RWO/RWX in the manifest. If the agent is ever scaled past one
   replica, verify the operator's chosen access mode supports it.

---

## Functional Requirements

- [x] CRD storage support confirmed and recorded (see *Gate: resolved*)
- [x] `agent.yaml` gains `spec.persistence` with `workspace: 20Gi` and
      `sessions: 2Gi`, no hardcoded `storageClassName`
- [x] `/tmp` worktree behaviour resolved: `AGENTS.md` uses
      `${WORKSPACE_DIR:-/tmp}/worktrees`, and `worktrees/` is gitignored
- [ ] `README.md` updated: persistence documented (what survives, what does not),
      the `/tmp` caveat, how to pin a `storageClassName`, and a reset procedure
- [ ] No secret material written to the persisted volumes; `detect-secrets` green

## Non-Functional Requirements

- [ ] `make pre-commit` passes (check-yaml, yamllint, prettier, markdownlint)
- [ ] `agent.yaml` validates: `kubectl apply --dry-run=server -f`
- [x] `spec.persistence` covered by the manifest tests added in **BITB-126**

---

## Verification

Requires an operator with write RBAC — the in-cluster agent ServiceAccount is
restricted to schema reads (`kubectl explain`), so steps 1-5 cannot be run by the
agent itself.

1. `kubectl apply -f deployment/kubeopencode/agent.yaml` → agent reaches ready.
2. `kubectl -n kubeopencode-system get pvc` → workspace and sessions PVCs `Bound`
   at the requested sizes.
3. **Persistence proof:**

   ```bash
   kubectl -n kubeopencode-system exec <agent-pod> -- \
     sh -c 'echo bitb-125 > /workspace/persistence-probe.txt'
   kubectl -n kubeopencode-system delete pod <agent-pod>
   # wait for the replacement pod
   kubectl -n kubeopencode-system exec <new-agent-pod> -- \
     cat /workspace/persistence-probe.txt   # must print: bitb-125
   ```

4. **No re-clone proof:** the replacement pod does not re-clone the repo; the
   git-init init container is a no-op against the existing checkout.
5. **Session proof:** conversation history from before the restart is still
   available after it.
6. **Reset proof:** the documented reset procedure restores a clean workspace.

---

## Out of Scope

- Multi-replica / access-mode changes (operator-owned; documented, not implemented)
- Backup or snapshot policy for the workspace PVC
- Any change to application runtime storage (Azure Container Apps, PostgreSQL)

---

## Related

- `deployment/kubeopencode/agent.yaml` — `spec.workspaceDir: /workspace`, no persistence
- `deployment/kubeopencode/README.md` — the `delete pod` step that makes loss routine
- `AGENTS.md` → *Git Worktree Pattern* — the `/tmp/` mandate this must reconcile
- BITB-123 — created `deployment/kubeopencode/`
- BITB-126 — CI coverage for these manifests
