# BITB-170: kubeopencode README — Document All 14 Files + Egress/Netpol Apply Order + RBAC + Hardening Cross-Link + OpenCode Config Sync

**Status:** ✅ Done
**Priority:** P2
**Size:** S
**Created:** 2026-09-30
**Completed:** 2026-09-30
**PR:** #1124

## User Story

**As** an operator deploying a new KubeOpenCode agent, **I want** the `k8s/kubeopencode/README.md` to document all manifests in the directory, show the correct apply order (including RBAC before Agents), cross-link the hardening runbook, and document the `make` targets that generate and sync the opencode config, **so that** I can roll out a strict-tier agent without guessing which files are required, in what order, or where the agent definitions come from.

## Why This Exists

Discovered while deploying a new agent (`wf3`):

- The operator could not find the egress/NetworkPolicy apply order — the README
  documented only 6 of 14 files in `k8s/kubeopencode/`, and the egress instructions
  existed only in `docs/SECURITY-KUBEOPENCODE.md` (§ "Zero-downtime rollout",
  lines 60–79) with no reference from the README.
- The operator could not find where/how to run the make targets that create the
  opencode config — `gen-opencode-config` / `verify-opencode-config` /
  `sync-opencode-configmap` were documented only in the older
  `deployment/kubeopencode/README.md`, never in `k8s/kubeopencode/README.md`
  (the directory they were actually reading).
- The RBAC manifests (`role-agent.yaml`, `rolebinding-agent.yaml`) are required by every Agent manifest (they all set `serviceAccountName: kubeopencode-agent`) but appeared in no apply order in the README.
- The `opencode-api-key` secret (file-mounted, hardening path) was missing from the Secrets section.
- No "Sandbox hardening" section existed in the README with the ordered netpol applies + the critical `default-deny-all` LAST warning.

## The Fix

Extended `k8s/kubeopencode/README.md` with:

1. **Intro paragraph** — now mentions strict-tier sandbox hardening and links to `docs/SECURITY-KUBEOPENCODE.md`.
2. **Files table** — 8 new rows for the previously undocumented files, with accurate one-line descriptions verified against file contents.
3. **Secrets section** — added `opencode-api-key` imperative creation (matching `docs/SECURITY-KUBEOPENCODE.md` lines 66–71) with a note that `default-wf2` uses the `ai-credentials` env route instead, so this secret is only for hardened agents.
4. **Apply order** — inserted RBAC step before Agent apply: `kubectl apply -f role-agent.yaml -f rolebinding-agent.yaml`.
5. **New "Sandbox hardening (strict-tier egress)" section** — 2–3 sentence summary, ordered apply commands copied from the security doc (three allow-policies, verify comment, then `default-deny-all` LAST), bold warning about `default-deny-all` order, verification commands (`make verify-kubeopencode-netpol` / `make test-kubeopencode-netpol`), rollback one-liner, and link to the security doc for full rationale/label taxonomy/LAN opt-in/troubleshooting.
6. **New "OpenCode config (agent definitions → ConfigMap)" section** (between Apply order and Sandbox hardening) — source of truth (`.opencode/agents/*.md`, 12 agents) and generated artifact (`opencode.json`, committed); the three make targets with one-line comments and the repo-root invocation note; ConfigMap-before-`configRef`-Agent warning; pod-restart-after-sync (`get pods` then `delete pod <agent-pod>`); `configRef`-vs-inline-`config` mutual exclusivity (full 12-agent roster + fallbacks needs `configRef`; copying `agent-default-wf2.yaml`'s inline block yields only bare model settings); cross-link to `deployment/kubeopencode/README.md` as the full runbook.

## Acceptance Criteria

- [x] All 14 files in `k8s/kubeopencode/` appear in the Files table with accurate descriptions.
- [x] Apply order includes RBAC (`role-agent.yaml` + `rolebinding-agent.yaml`) before any Agent manifest.
- [x] Secrets section includes `opencode-api-key` with the imperative pattern from the security doc and the clarifying note about `default-wf2` using `ai-credentials` env.
- [x] New "Sandbox hardening (strict-tier egress)" section exists after Apply order with:
  - [x] What strict tier enforces (public 443/53 + cluster DNS + K8s API only; LAN/metadata/loopback denied; agents cannot reach each other).
  - [x] Ordered apply commands: three allow-policies → verify → `default-deny-all` LAST.
  - [x] Bold warning that `default-deny-all` selects every pod and enforces on apply; applying it first kills gateway DNS/egress.
  - [x] Verification: `make verify-kubeopencode-netpol` (live) and `make test-kubeopencode-netpol` (static/CI).
  - [x] Rollback one-liner: `kubectl -n kubeopencode-system delete netpol default-deny-all`.
  - [x] Cross-link to `docs/SECURITY-KUBEOPENCODE.md` for full rationale, label taxonomy, LAN opt-in, troubleshooting.
- [x] New "OpenCode config (agent definitions → ConfigMap)" section exists between Apply order and Sandbox hardening with:
  - [x] Source of truth (`.opencode/agents/*.md`, 12 agents) and generated artifact (`opencode.json`, committed).
  - [x] All three make targets documented with one-line comments and the repo-root invocation note (`make gen-opencode-config` / `make verify-opencode-config` / `make sync-opencode-configmap`).
  - [x] ConfigMap-before-Agent warning: a `spec.configRef` Agent (like `deployment/kubeopencode/agent.yaml`) will not start unless the ConfigMap already exists.
  - [x] Pod-restart-after-sync: updating the ConfigMap does not restart mounted consumers; running agents keep the previous config until their pod is replaced.
  - [x] `configRef`-vs-inline-`config` mutual exclusivity; full roster + fallbacks needs `configRef`, copying `agent-default-wf2.yaml`'s inline block yields only bare model settings.
  - [x] Cross-link to `deployment/kubeopencode/README.md` as the full runbook (proper link syntax, no bare URL).
- [x] `docs/BACKLOG.md` updated with BITB-170 summary entry and `Last Updated` date.
- [x] `markdownlint` passes on all three changed files (no MD034 bare URLs, consistent table columns, no trailing whitespace, single trailing newline).

## Out of Scope

- No YAML manifest changes — this is docs-only.
- No changes to `docs/SECURITY-KUBEOPENCODE.md` (canonical hardening runbook remains the source of truth).
- No changes to `mobile-access.md` or `custom-opencode-image.md`.

## Verification

```bash
cd /workspace/worktrees/docs-kubeopencode-readme
npx markdownlint-cli k8s/kubeopencode/README.md docs/BACKLOG.md docs/BACKLOG_STORIES/BITB-170-kubeopencode-readme-egress-docs.md
pre-commit run --files k8s/kubeopencode/README.md docs/BACKLOG.md docs/BACKLOG_STORIES/BITB-170-kubeopencode-readme-egress-docs.md
```
