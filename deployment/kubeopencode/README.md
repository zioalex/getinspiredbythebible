# KubeOpenCode Deployment Config — OBSOLETE (BITB-285)

**This folder is obsolete.** Per the 2026-11-09 owner ruling,
[`k8s/kubeopencode/`](../../k8s/kubeopencode/README.md) is **THE canonical
home for all KubeOpenCode manifests and docs**. Everything that used to live
here has migrated there; this stub remains so old references land somewhere
truthful. Do not add content to this folder — `deployment/` is Terraform
for Azure only (see `AGENTS.md` → *Repository Layout*).

- `agent.yaml` → **removed** — its content was field-for-field identical to
  the canonical [`k8s/kubeopencode/agent-default-wf2.yaml`](../../k8s/kubeopencode/agent-default-wf2.yaml)
  (verified before removal, zero drift; live == repo confirmed by owner
  `kubectl diff`, 2026-11-09). Applying the k8s manifest converges the same
  live object.
- `agents.md` → moved to [`k8s/kubeopencode/agents.md`](../../k8s/kubeopencode/agents.md)
  (the 12-agent model table).

## Where the old sections went (anchor redirects)

| Old section (anchor) | New location |
| --- | --- |
| Prerequisites / Create the secret | [`k8s/kubeopencode/README.md` → *Secrets to create*](../../k8s/kubeopencode/README.md#secrets-to-create-not-stored-in-git) |
| Create the ConfigMap / sync flow (`#create-the-configmap`) | [`k8s/.../README.md` → *OpenCode config* + *Config sync runbook — merge before sync*](../../k8s/kubeopencode/README.md#opencode-config-agent-definitions--configmap) |
| After the pod restart: verify the plugin (`#after-the-pod-restart-verify-the-plugin-actually-loaded`) | [`k8s/.../README.md` → *After the pod restart: verify the plugin actually loaded*](../../k8s/kubeopencode/README.md#after-the-pod-restart-verify-the-plugin-actually-loaded) |
| Pre-merge checklist (`#pre-merge-checklist-for-opencode-config-changes-bitb-280`) | [`k8s/.../README.md` → *Pre-merge checklist for opencode config changes*](../../k8s/kubeopencode/README.md#pre-merge-checklist-for-opencode-config-changes-bitb-280) |
| Apply (`#apply`) | [`k8s/.../README.md` → *Apply order*](../../k8s/kubeopencode/README.md#apply-order) |
| Persist GitHub Copilot access (`#persist-github-copilot-access`) | [`k8s/.../README.md` → *Persist GitHub Copilot access*](../../k8s/kubeopencode/README.md#persist-github-copilot-access) |
| Fallback resilience (`#fallback-resilience`) | [`k8s/.../README.md` → *Fallback resilience*](../../k8s/kubeopencode/README.md#fallback-resilience) |
| Persistence (`#persistence-bitb-128`) | [`k8s/.../README.md` → *Persistence*](../../k8s/kubeopencode/README.md#persistence-bitb-128) |
| Files / Notes | folded into the [`k8s/.../README.md`](../../k8s/kubeopencode/README.md) *Files* table and section prose |

The controller-ownership / startup-probe / rollback-anchor sections were
already moved to the k8s README by PR #1272 (BITB-282/283/284); this stub
completes the sunset (BITB-285).
