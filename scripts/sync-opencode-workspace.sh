#!/bin/bash
# sync-opencode-workspace.sh — keep the KubeOpenCode pod's shared checkout in
# lockstep with the synced opencode config (BITB-269 delivery fix, T-1254PLG).
#
# WHY THIS EXISTS
#   The generated opencode.json loads the task-reliability plugin via an
#   absolute `file:///workspace/repo/.opencode/plugin/task-reliability.ts`
#   entry — a path into the pod's shared git checkout on the workspace PVC.
#   Nothing updated that checkout after the initial clone, so on 2026-11-08
#   the config was synced from PR #1254 while the checkout sat 6 days stale:
#   the plugin entry resolved to a file whose export shape the runtime
#   rejected (`ERROR failed to load plugin … error="Plugin export is not a
#   function"`, runtime log 18:52:00Z) and the plugin silently never loaded.
#   `make sync-opencode-configmap` now runs this script first, so config and
#   the plugin code it references can never drift apart again.
#
# WHAT IT DOES (Option B delivery — fast-forward, never rewrite)
#   1. Finds the agent pod in the namespace (override with OPENCODE_AGENT_POD).
#   2. `git fetch origin` + `git merge --ff-only <REF>` in /workspace/repo.
#      - ff-only: a diverged or detached checkout fails LOUDLY; we never
#        reset, force, or touch history.
#      - Attached worktrees (${WORKSPACE_DIR}/worktrees/*) are unaffected:
#        they have their own HEADs; fetch only adds objects. Verified
#        empirically (T-1254PLG): worktrees + uncommitted files survived.
#   3. Runs the plugin unit tests IN THE POD (node 22+, type-stripping):
#      the suite asserts the opencode 1.18.31 loader contract (plugin module
#      must export exactly one default function) — the pre-live check that
#      was missing on 2026-11-08, when a "verified" plugin had never actually
#      been load-tested against the real loader.
#
# RUNBOOK (full flow in k8s/kubeopencode/README.md)
#   1. Merge the PR that changes .opencode/** or opencode.json.
#   2. make sync-opencode-configmap   (runs this script + the ConfigMap sync)
#   3. kubectl -n kubeopencode-system delete pod <agent-pod>
#   4. Verify: no "failed to load plugin" in the runtime log; after the next
#      subagent dispatch, /workspace/.opencode/task-registry.jsonl exists.
#
# Requirements: kubectl with get/list pods + create pods/exec in the
# namespace; git and node 22+ inside the agent pod (shipped by the devbox
# executor image). Env overrides:
#   KUBEOPENCODE_NAMESPACE   (default kubeopencode-system)
#   OPENCODE_AGENT_POD       (default: first pod found in the namespace)
#   OPENCODE_WORKSPACE_REPO  (default /workspace/repo)
#   OPENCODE_WORKSPACE_REF   (default origin/main; must be an origin/* ref)

set -euo pipefail

NAMESPACE="${KUBEOPENCODE_NAMESPACE:-kubeopencode-system}"
REPO_DIR="${OPENCODE_WORKSPACE_REPO:-/workspace/repo}"
REF="${OPENCODE_WORKSPACE_REF:-origin/main}"

if [ "${REF#origin/}" = "$REF" ]; then
  echo "ERROR: OPENCODE_WORKSPACE_REF must be an origin/* ref (got '$REF')." >&2
  exit 1
fi

if [ -z "${OPENCODE_AGENT_POD:-}" ]; then
  OPENCODE_AGENT_POD="$(
    kubectl -n "$NAMESPACE" get pod -o name 2>/dev/null | grep -m1 '^pod/' | sed 's|^pod/||'
  )" || true
fi
if [ -z "${OPENCODE_AGENT_POD:-}" ]; then
  echo "ERROR: no agent pod found in namespace $NAMESPACE." >&2
  echo "       Start the Agent, or set OPENCODE_AGENT_POD explicitly." >&2
  exit 1
fi

echo "Workspace sync: pod ${OPENCODE_AGENT_POD} (${NAMESPACE}) — ${REPO_DIR} -> ${REF}"

# One exec keeps fetch + merge + pre-flight test atomic from the caller's view.
# Quoting: the payload below runs INSIDE the pod — its $VAR references are
# expanded there, never locally — so shellcheck's SC2016 single-quote warning
# is suppressed deliberately; env passes the parameters in.
# shellcheck disable=SC2016
kubectl -n "$NAMESPACE" exec "${OPENCODE_AGENT_POD}" -- \
  env REPO_DIR="$REPO_DIR" REF="$REF" bash -eu -c '
    cd "$REPO_DIR"
    branch="$(git symbolic-ref --short HEAD)" || {
      echo "ERROR: $REPO_DIR is on a detached HEAD — refusing to update." >&2
      exit 1
    }
    if [ "$branch" != "main" ]; then
      echo "ERROR: $REPO_DIR is on branch [$branch], not main — refusing to update." >&2
      exit 1
    fi
    git fetch origin
    git merge --ff-only "$REF"
    echo "  checkout now at: $(git rev-parse --short HEAD) ($REF)"
    echo "  pre-flight: task-reliability plugin tests (loader contract)"
    node --experimental-strip-types --test .opencode/plugin/task-reliability.test.ts
  '

echo "✓ Pod workspace checkout is current and the plugin passed its pre-flight tests."
