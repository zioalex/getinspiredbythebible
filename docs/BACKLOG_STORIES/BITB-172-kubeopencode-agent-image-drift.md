# BITB-172: Repo-vs-Live Drift — agentImage Wiring Uncommitted, Mobile Credential Pre-Wired

**Status:** ✅ Done
**Priority:** P1
**Size:** S
**Created:** 2026-09-30
**Completed:** 2026-09-30
**PR:** pending

## User Story

**As** the operator of the home k3s cluster, **I want** the committed Agent manifests to match what the live `default-wf2` object actually runs — custom `agentImage` + pull secret included, mobile Basic auth opt-in — **so that** repo applies converge with live and a fresh agent (wf3) starts without hitting missing-secret or default-image surprises.

## Why This Exists

Surfaced while testing the new `default-wf3` agent (follow-up to BITB-170/171):

- **wf3 pod crashlooped** with `CreateContainerConfigError: secret "opencode-server-auth" not found`. Root cause: the BITB-171 self-contained manifest pre-wired the `server-password` credential (mobile Basic auth), but the flow was documented (PR #1089) and **never rolled out** — no cluster had the secret. Live `default-wf2` (applied from `deployment/kubeopencode/agent.yaml`) never referenced it, which is why wf2 worked while wf3 failed on the identical-looking manifest.
- **wf3 ran the default opencode image**, not the custom build. Root cause: `agentImage` (`ghcr.io/zioalex/kubeopencode-agent-opencode:v0.1.9-oc1.18.31`) and `imagePullSecrets: ghcr-pull` were wired **only on the live object** (kubectl patch per `custom-opencode-image.md`) and existed nowhere in git. The wf3 manifest applied from the repo pinned nothing → operator rendered the default `ghcr.io/kubeopencode/...-opencode:latest` init container.
- The k8s README's "safe to apply standalone" (shipped in BITB-171) was overstated: it is only true once every referenced secret exists.

## The Fix

1. **`k8s/kubeopencode/agent-default-wf2.yaml`** — added `agentImage` (pinned `v0.1.9-oc1.18.31`, never `:latest`) + `imagePullSecrets: ghcr-pull`; **removed** the `server-password` credential (mobile auth is opt-in). Header rewritten: prerequisites, the BITB-172 history, mobile opt-in pointer.
2. **`k8s/kubeopencode/agent-default-wf3.yaml`** (new) — the validated wf3 agent: identical shape to wf2 (configRef, persistence, 3 credentials, image wiring) under its own name; the operator provisions its own PVCs. Validated on the home cluster 2026-09-30 (pod Ready, init container running the custom build).
3. **`deployment/kubeopencode/agent.yaml`** — same `agentImage` + `imagePullSecrets` added, converging the second repo manifest with the live object.
4. **T7 tests** (`scripts/test_kubeopencode_manifests.py`):
   - `test_agent_image_pinned_with_pull_secret` (parametrized over all 3 Agent manifests): `agentImage` present, pinned to the live build, never `:latest`, `ghcr-pull` wired.
   - `test_wf3_agent_matches_wf2_shape`: wf3 = wf2 shape (config/persistence/credentials/image) — keeps wf3 a faithful image test, not a second drift source.
   - `test_k8s_agent_credentials_match_deployment` (replaces BITB-171's superset test): **exact** credential match + asserts `server-password` is NOT pre-wired.
   - `test_k8s_credential_secrets_and_envs_documented` parametrized over wf2 + wf3.
5. **Doc consistency**: k8s README (wf2 Files row corrected — "converging with the live object" + explicit standalone prerequisites; new wf3 row; `opencode-server-auth` marked OPTIONAL/mobile-only; `ghcr-pull` marked REQUIRED; optional wf3 line in the apply order; missing-secret failure mode named); `mobile-access.md` (Phase 1 is now an opt-in `kubectl edit` patch with the merge-patch list-replacement caveat; files table updated); `deployment/kubeopencode/README.md` Files bullet updated.

## Acceptance Criteria

- [x] `agentImage` + `imagePullSecrets` committed in both `default-wf2` manifests and the new wf3 manifest — repo = live
- [x] No manifest pre-wires `server-password`; `mobile-access.md` documents the opt-in patch; a cluster without `opencode-server-auth` can apply every manifest cleanly
- [x] `agent-default-wf3.yaml` committed, matching the cluster-validated shape
- [x] T7 tests green: image pinning (3 manifests), wf3 parity, credentials exact-match, doc coverage parametrized over both k8s manifests
- [x] README no longer overstates "safe to apply standalone"; secrets section marks optional vs required
- [x] `pytest scripts/test_kubeopencode_manifests.py` + `markdownlint` + `yamllint` + `prettier` (pinned) green

## Out of Scope

- Rolling out the mobile-access flow itself (creating `opencode-server-auth`, enabling Basic auth) — remains the operator's opt-in
- `agent-desktop.yaml` (example agent, no image wiring by design)
- Automating repo-vs-live drift detection against a live cluster (the T7 tests pin the committed side; live-side verification stays manual)

## Verification

```bash
cd <repo-root>
python -m pytest scripts/test_kubeopencode_manifests.py -v
npx markdownlint-cli k8s/kubeopencode/README.md k8s/kubeopencode/mobile-access.md deployment/kubeopencode/README.md docs/BACKLOG.md
```
