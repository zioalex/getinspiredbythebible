# BITB-158: KubeOpenCode Dev Image — Bake CLI/Toolchain into Agent Image

**Status:** 🚧 In Progress — PR pending (Dockerfile + CI build validation implemented;
registry push and `executorImage` cutover on the live cluster are a manual follow-up,
out of scope for this PR)
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

> **v2 correction (2026-09-25):** the table below was written before a first
> (v1) build was independently verified and found to have built FROM the
> wrong upstream image (`kubeopencode-agent-opencode`, the `agentImage`
> default — an Alpine image with no shell, and not even the container where
> tasks run) and told users to set the wrong CRD field (`agentImage:`
> instead of `executorImage:`). It also assumed the base shipped nothing,
> when `kubeopencode-agent-devbox` (the real `executorImage` default)
> already ships `git`/`make`/`curl`/`jq`/`gh`/`kubectl`/`yq`/system Node
> 22.x (no NVM)/`python3`+`pip`. The table is kept here for historical
> context of what the story originally asked for; see
> `k8s/kubeopencode/dev-image/README.md` for what the shipped v2 image
> actually adds on top of that base (just `ripgrep` + `pytest`/`pre-commit`/
> `PyYAML` + a pre-warmed hook cache) and why Python is 3.11 (bookworm's
> system `python3`), not 3.12.

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

- [x] Agent Dockerfile (or base-image extension) installs the table above with
      repo-pinned versions (`.pre-commit-config.yaml` revs, Node `22.22.0`,
      Python `3.12`) — shipped as: base image (`kubeopencode-agent-devbox`,
      the `executorImage`) already provides Node 22.x and Python 3.11 system-
      wide; this derivative adds `ripgrep` + pinned `pytest`/`pre-commit`/
      `PyYAML`. Python is 3.11, not 3.12 — see `dev-image/README.md` for why
      that's a deliberate, documented deviation.
- [x] Hook envs pre-warmed at build time (`pre-commit install-hooks` or
      equivalent); first real `make pre-commit` in a fresh pod is a cache hit
      — **v3 fix:** a v2 verify pass built the real Dockerfile against a
      stand-in base and reproduced this as false: the seed was `chmod -R g+w`
      only, which left `pre-commit`'s own `db.db` (600) and hook-repo dirs
      (700) unreadable by the runtime `USER 1000:0` (group 0) — every real
      hook run failed with `unable to open database file`, uncaught because
      the smoke test only checked `pre-commit --version`. Fixed to
      `chmod -R g+rwX`; confirmed by the verifier that a UID 1000:0 container
      then reuses the cache with no re-install. Separately, the seed's own
      build-time `RUN` steps (pip, and pre-commit's node-language hooks like
      prettier/markdownlint) left root-owned files under `/tmp` (inherited
      `HOME=/tmp` from the base), breaking `npm`/`npx` for the runtime user —
      fixed with a `chmod -R 777 /tmp` restoring the base's own
      arbitrary-UID convention.
- [x] `PRE_COMMIT_HOME` placed under `/workspace` (or otherwise on the PVC) so
      the mandatory post-sync `kubectl delete pod` does not wipe hook caches —
      shipped as `PRE_COMMIT_HOME=/opt/pre-commit-seed`, a fixed path baked
      directly into the image layer (not the PVC) once the copy-based design
      was found to break pre-commit's own absolute-path `db.db`; see
      `dev-image/README.md` "Pre-warmed pre-commit cache".
- [x] Smoke test in Dockerfile/CI: `gh --version`, `kubectl version --client`,
      `python3 -c "import yaml, pytest"`, `node --version`,
      `pre-commit --version`, `make verify-opencode-config` — the exact
      commands that failed or were worked around in PR #1079 — **v3
      addition:** also runs `pre-commit run check-yaml --all-files`, since
      `--version` alone never opens the cache and didn't catch the
      permission bug above; CI's `docker run` also gained
      `--user "$(id -u):0"` after the same verify pass found the bind-mounted
      runner checkout (owned by the runner's UID, not the image's baked
      `1000:0`) made `make verify-opencode-config` fail with
      `Permission denied` writing `opencode.json`.
- [x] `python3 -m pytest scripts/test_generate_opencode_config.py -q` green in
      a fresh pod with no warm-up
- [x] ESLint hook works with baked Node — moot in practice: the base ships
      Node 22.x as a plain system package (no NVM), and the hook's
      `$NVM_DIR/nvm.sh` guard is a no-op that falls through to system `node`/
      `npx` already on `PATH`; no image or hook change needed
- [ ] Follow-ups filed or fixed: stale `README.md` cross-provider table
      (`muse-spark`/`gemma-3-27b` → super/gpt-oss, matching `agents.md`) — see
      `docs/BACKLOG_STORIES/BITB-163-sync-kubeopencode-fallback-table-post-1079.md`
      (blocked on PR #1079 merging); NVM-assumption note — resolved above,
      no longer applicable on the `executorImage` base this image derives from

## Notes / Leads

- Precedent: `agent.yaml` already documents `/tmp` non-persistence and the
  `${WORKSPACE_DIR}/worktrees` pattern (BITB-128) — hook caches need the same
  treatment.
- Keep the image lean: lint/test toolchain only, not the full API venv that
  caused the resolver failure.
- Coordinate with BITB-152 (sandbox hardening): default-deny egress must still
  allow the registries needed at *build* time; runtime pod needs no new egress
  if everything is pre-warmed.
