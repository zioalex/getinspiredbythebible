# BITB-158: KubeOpenCode Dev Image — Bake CLI/Toolchain into Agent Image

**Status:** 🚧 In Progress — PR pending (Dockerfile + CI build validation implemented;
registry push and `agentImage` cutover on the live cluster are a manual follow-up, out
of scope for this PR)
**Priority:** P1
**Size:** M (Dockerfile + build/push pipeline + docs; no app code)
**Created:** 2026-09-15
**Renumbered:** 2026-09-21 from BITB-155 — ID collision with the OpenRouter model refresh story (#1081), which claimed BITB-155 first. A first renumber to BITB-157 collided with the wire-donate-URL story in #1084 (claimed Sept 17); final ID is BITB-158.
**Related:** BITB-123 (agent graph), BITB-152 (sandbox hardening), BITB-154 (multi-provider resilience), PR #1079 (fallback review that exposed the gaps)

---

## Problem

The PR #1079 session (Ultra → Super-Free + GPT-OSS-120B fallback swap) exposed
that the KubeOpenCode agent pod is missing the standard dev toolchain, forcing
slow cold-installs and fragile workarounds on every fresh pod:

1. **`gh` assumed but not guaranteed.** The session used `gh pr view/diff/checks`,
   `gh run view --log-failed`, `gh pr edit/comment`, and the `gh auth token`
   Copilot flow documented in `deployment/kubeopencode/README.md`.
2. **`kubectl` missing in-pod.** Every `make sync-opencode-configmap` cycle ends
   with `kubectl get/delete pod`, `get/describe agent`, `get configmap`
   (`deployment/kubeopencode/README.md`); the agent cannot self-verify without it.
3. **Python test deps missing.** `python3 -m pytest
   scripts/test_generate_opencode_config.py` failed with
   `No module named pytest` (only `python3 -m json.tool` worked).
4. **`make pre-commit` broken in-pod.** Venv creation pulled unsatisfiable deps
   (`lingua-language-detector==2.2.0`) and then
   `.venv/bin/pre-commit: No such file or directory`. Hook caches live outside
   `/workspace`, so pod restarts (mandatory after every config sync) wipe them.
5. **No JSON/YAML query tools.** JSON checks were hand-rolled
   (`python3 -c "import json..."`) and searches fell back to `grep -rn`.
6. **Node/NVM assumption.** The ESLint hook sources `$NVM_DIR/nvm.sh`
   (`.pre-commit-config.yaml`, `default_language_version: node: 22.22.0`);
   a baked system Node without the NVM shim breaks the hook.

## Why it matters

- Every fresh pod repeats the same cold-download tax (13 hook repos) and the
  same failure modes, slowing exactly the config-sync loop BITB-123/154 made
  central (`gen → verify → sync → delete pod`).
- `opencode Config & Manifests` CI caught a stale test constant the pod could
  not catch locally (no `pytest`), pushing defect discovery to CI instead of
  the worktree.
- Version drift between pod-resolved deps and CI-pinned revs is a proven
  failure mode (the `lingua-language-detector` resolver error in this session).

## What to bake

| Layer | Packages (pin to repo) |
|---|---|
| VCS + build | `git` (recent, worktree support), `make`, `bash`, `curl` |
| Cluster + forge | `kubectl` (match server version), `gh` |
| Query | `jq`, `yq`, `ripgrep` |
| Python | `python3.12`, `pip`, `PyYAML`, `pytest`, `pre-commit` binary |
| Python lint envs (pre-warmed) | `black 26.1.0` (line-length 100, `api/`), `ruff v0.2.0`, `mypy v1.8.0` (+`types-requests`, `types-PyYAML`), `bandit 1.7.6` |
| Generic hooks (pre-warmed) | `hadolint v2.12.0`, `yamllint v1.33.0`, `shellcheck-py v0.9.0.6`, `markdownlint v0.39.0`, `detect-secrets v1.4.0`, `prettier v4.0.0-alpha.8` |
| Node | `node 22.22.0` + `npm`/`npx`, plus NVM shim (`NVM_DIR`) or a patched ESLint hook entry with system-node fallback |

Deliberately **excluded**: JDK 17/Gradle/Android SDK (CI-side, heavy),
Docker engine, Ollama, Terraform, full `api/` backend venv.

## Acceptance Criteria

- [ ] Agent Dockerfile (or base-image extension) installs the table above with
      repo-pinned versions (`.pre-commit-config.yaml` revs, Node `22.22.0`,
      Python `3.12`)
- [ ] Hook envs pre-warmed at build time (`pre-commit install-hooks` or
      equivalent); first real `make pre-commit` in a fresh pod is a cache hit
- [ ] `PRE_COMMIT_HOME` placed under `/workspace` (or otherwise on the PVC) so
      the mandatory post-sync `kubectl delete pod` does not wipe hook caches
- [ ] Smoke test in Dockerfile/CI: `gh --version`, `kubectl version --client`,
      `python3 -c "import yaml, pytest"`, `node --version`,
      `pre-commit --version`, `make verify-opencode-config` — the exact
      commands that failed or were worked around in PR #1079
- [ ] `python3 -m pytest scripts/test_generate_opencode_config.py -q` green in
      a fresh pod with no warm-up
- [ ] ESLint hook works with baked Node (NVM shim or documented fallback)
- [ ] Follow-ups filed or fixed: stale `README.md` cross-provider table
      (`muse-spark`/`gemma-3-27b` → super/gpt-oss, matching `agents.md`),
      NVM-assumption note

## Notes / Leads

- Precedent: `agent.yaml` already documents `/tmp` non-persistence and the
  `${WORKSPACE_DIR}/worktrees` pattern (BITB-128) — hook caches need the same
  treatment.
- Keep the image lean: lint/test toolchain only, not the full API venv that
  caused the resolver failure.
- Coordinate with BITB-152 (sandbox hardening): default-deny egress must still
  allow the registries needed at *build* time; runtime pod needs no new egress
  if everything is pre-warmed.
