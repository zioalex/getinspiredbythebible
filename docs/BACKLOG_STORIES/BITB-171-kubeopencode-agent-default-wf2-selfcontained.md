# BITB-171: k8s agent-default-wf2.yaml Is a Stripped Sketch — Applying It Degrades the Live Agent

**Status:** ✅ Done
**Priority:** P1
**Size:** S
**Created:** 2026-09-30
**Completed:** 2026-09-30
**PR:** #1125

## User Story

**As** an operator rolling out the `default-wf2` Agent from `k8s/kubeopencode/`, **I want** that manifest to be self-contained — the same `configRef`, `persistence`, and credentials as `deployment/kubeopencode/agent.yaml` — **so that** applying it (standalone or over the live object) converges instead of silently stripping fields the older manifest set.

## Why This Exists

`k8s/kubeopencode/agent-default-wf2.yaml` (added in PR #1089 for mobile access) was a **patch sketch**, not a full manifest: inline `spec.config` (bare `model`/`small_model`), **no `persistence`**, and only two of four credentials. Its header said "keep your existing spec fields" and pointed at `mobile-access.md`'s "reconcile with your live spec first" — but the README apply order (`kubectl apply -f agent-default-wf2.yaml`) carried no such caveat.

The two manifests declare the **same Agent object** (`default-wf2` in `kubeopencode-system`). Client-side `kubectl apply` three-way-merges: fields present in the last-applied config but absent in the new manifest are **removed**. So following the k8s README alone would strip from the live object:

- `persistence` → workspace reverts to **EmptyDir** → the README-mandated `kubectl delete pod` after every config sync destroys the clone and uncommitted work (the exact failure BITB-128 fixed)
- `configRef` → the 12-agent roster + fallbacks replaced by a bare inline model config
- the `github-copilot` and `openrouter` credentials → silent degradation to free fallback models (T3's failure mode)

Nothing guarded this: `scripts/test_kubeopencode_manifests.py` (T5, BITB-129) validated `spec.persistence` **only for `deployment/kubeopencode/agent.yaml`** — the k8s variant was invisible to CI. Found while deploying the `wf3` agent (BITB-170 follow-up: "where did the persistence go?").

## The Fix

1. **`k8s/kubeopencode/agent-default-wf2.yaml` made self-contained** — identical to `deployment/kubeopencode/agent.yaml` (`profile`, `workspaceDir`, `serviceAccountName`, `configRef` → `opencode-config` ConfigMap, `persistence` workspace 20Gi + sessions 2Gi, credentials `api-key`/`github-copilot`/`openrouter-api-key`) **plus** the `server-password` credential (`OPENCODE_SERVER_PASSWORD`, mobile Basic auth). Header rewritten: prerequisites, the BITB-171 history, and a pointer to the parity test.
2. **Parity tests (T6) in `scripts/test_kubeopencode_manifests.py`** — new fixtures for the k8s manifest and its README; tests assert:
   - same object identity (metadata name/namespace; `profile`/`workspaceDir`/`serviceAccountName` identical)
   - persistence block matches deployment's volumes and sizes
   - `configRef` matches what `make sync-opencode-configmap` creates; config/configRef mutual exclusivity; configRef present (not inline)
   - credentials are a **superset** of deployment's (same `secretRef`/`env`) and keep `server-password` → `OPENCODE_SERVER_PASSWORD`
   - every secret name and env var the manifest wires is documented in `k8s/kubeopencode/README.md` (T3 extended to the k8s variant)
3. **Doc consistency**:
   - `k8s/kubeopencode/README.md` — Files row rewritten (self-contained, parity-tested); Secrets section gains `openrouter-api-key` and `github-copilot-auth` creation commands (with the gho-vs-PAT caveat and links to `deployment/kubeopencode/README.md`); the "OpenCode config" section's mutual-exclusivity paragraph no longer describes the manifest as an inline-config sketch; apply-order step 3 notes the ConfigMap prerequisite.
   - `k8s/kubeopencode/mobile-access.md` — the Phase-1 note and files table now describe the manifest as self-contained (converging) instead of "reconcile with your live spec first".

## Acceptance Criteria

- [x] `agent-default-wf2.yaml` carries `spec.configRef` → `opencode-config`/`opencode.json`, `spec.persistence` (workspace 20Gi, sessions 2Gi), and credentials `api-key`, `server-password`, `github-copilot`, `openrouter-api-key`
- [x] Applying it over a live object applied from `deployment/kubeopencode/agent.yaml` converges (no field removals) — all shared fields identical, only `server-password` added
- [x] T6 parity tests added and passing; they fail on any future drift between the two manifests
- [x] Every secret/env wired in the k8s manifest is documented in `k8s/kubeopencode/README.md` (asserted by test)
- [x] No doc anywhere still describes `agent-default-wf2.yaml` as an inline-config sketch or "add the credential to your existing spec"
- [x] `markdownlint` clean on all touched markdown; `pytest scripts/test_kubeopencode_manifests.py` green locally and in CI

## Out of Scope

- Consolidating the two manifests into one (root cause is "two manifests, one object"; the parity test contains the risk, a future story can merge them)
- `agent-desktop.yaml` (has `sessions`-only persistence by design — example agent, not a default-wf2 twin)
- Any change to `deployment/kubeopencode/` or the ConfigMap/generator pipeline

## Verification

```bash
cd <repo-root>
python -m pytest scripts/test_kubeopencode_manifests.py -v
npx markdownlint-cli k8s/kubeopencode/README.md k8s/kubeopencode/mobile-access.md docs/BACKLOG.md
```
