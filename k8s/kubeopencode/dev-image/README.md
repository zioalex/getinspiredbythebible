# KubeOpenCode dev-toolchain image (BITB-158)

Derivative agent image that bakes the CLI/toolchain this repo's agent pods
need but the upstream `kubeopencode-agent-opencode` image doesn't ship, so
`gh`/`kubectl`/`pytest`/`pre-commit`/`node` don't have to be cold-installed
(or fail to install) on every fresh pod.

> **This PR ships the Dockerfile + CI build validation only.** Pushing the
> built image to a registry and flipping `agentImage:` on the live `Agent` is
> a manual follow-up -- this repo's CI has no registry push credentials
> configured (same limitation `custom-opencode-image.md` documents for the
> opencode-version bump workflow). See "Publish and point the Agent at it"
> below, which reuses that exact mechanism rather than inventing a new one.

## Why

The PR #1079 session hit, in order: `gh` assumed but not installed,
`kubectl` missing in-pod (every `make sync-opencode-configmap` cycle ends
with `kubectl get/delete pod`), `python3 -m pytest ...` failing with
`No module named pytest`, `make pre-commit` failing to build a venv
(`lingua-language-detector==2.2.0` unsatisfiable) and then not finding a
`pre-commit` binary, hand-rolled JSON/YAML checks in place of `jq`/`yq`, and
the ESLint hook's `$NVM_DIR/nvm.sh` assumption breaking against a bare system
Node. See `docs/BACKLOG_STORIES/BITB-158-kubeopencode-dev-image.md` for the
full friction log and acceptance criteria.

## What's baked in

| Layer | Packages (pinned to this repo where a pin exists) |
|---|---|
| VCS + build | `git`, `make`, `bash`, `curl` |
| Cluster + forge | `kubectl` (`KUBECTL_VERSION` build arg), `gh` (`GH_VERSION` build arg) |
| Query | `jq`, `yq` (`YQ_VERSION` build arg), `ripgrep` |
| Python | `python3.12`, `pip`, `PyYAML`, `pytest`, `pre-commit` binary |
| Python lint envs (pre-warmed) | `black 26.1.0`, `ruff v0.2.0`, `mypy v1.8.0`, `bandit 1.7.6` |
| Generic hooks (pre-warmed) | `hadolint v2.12.0`, `yamllint v1.33.0`, `shellcheck-py v0.9.0.6`, `markdownlint v0.39.0`, `detect-secrets v1.4.0`, `prettier v4.0.0-alpha.8` |
| Node | `node 22.22.0` (`NODE_VERSION` build arg) via NVM at `$NVM_DIR=/opt/nvm`, so the local `eslint` pre-commit hook (which sources `$NVM_DIR/nvm.sh`) works unmodified |

Pinned versions match `.pre-commit-config.yaml`'s hook revs and
`default_language_version.node` exactly -- see that file for the source of
truth if a version here ever looks stale.

Deliberately **excluded** (per the story): JDK 17/Gradle/Android SDK, Docker
engine, Ollama, Terraform, the full `api/` backend venv.

## Pre-warmed pre-commit cache

The hook environments (`black`, `ruff`, `mypy`, `bandit`, `hadolint`,
`yamllint`, `shellcheck`, `markdownlint`, `detect-secrets`, `prettier`) are
installed at build time (`pre-commit install-hooks`) against a scratch copy
of this repo's `.pre-commit-config.yaml` and `.secrets.baseline`, and the
resulting cache is baked at the image-layer path `/opt/pre-commit-seed`.

That path is deliberately **not** `/workspace/...`: `/workspace` is an empty
PVC mount at container start on a fresh pod (`spec.persistence.workspace`,
see `deployment/kubeopencode/README.md` → "Persistence"), so the mount would
shadow anything baked into the image at that path.

The repo's `Makefile` `pre-commit` target has a small guarded step that
copies `/opt/pre-commit-seed` into `$PRE_COMMIT_HOME`
(`/workspace/.cache/pre-commit`, set via `ENV` in the Dockerfile) the first
time it's empty. `/workspace` is the one path the `Agent` CRD's
`spec.persistence.workspace` PVC actually persists across the
`kubectl delete pod` cycle that `deployment/kubeopencode/README.md` requires
after every `make sync-opencode-configmap` -- so the warmed cache survives
pod restarts, and the *first* real `make pre-commit` in a fresh pod is a
cache hit instead of a 13-repo cold download. On a normal laptop or CI
runner (no `/opt/pre-commit-seed`), that step is a no-op and `make pre-commit`
behaves exactly as it did before this change.

## Build

Build context must be the **repo root** (not this directory) -- the
pre-commit-seed layer `COPY`s this repo's own `.pre-commit-config.yaml` and
`.secrets.baseline` so the warmed cache matches exactly what `make pre-commit`
runs here:

```bash
docker build \
  --build-arg BASE_IMAGE_TAG=ghcr.io/kubeopencode/kubeopencode-agent-opencode:v0.1.9 \
  -f k8s/kubeopencode/dev-image/Dockerfile \
  -t <your-registry>/kubeopencode-agent-dev:<tag> \
  .
```

`BASE_IMAGE_TAG` defaults to `v0.1.9`, the newest tag actually published on
`ghcr.io/kubeopencode/kubeopencode-agent-opencode` as of this writing (checked
against the registry's tag list directly -- only bare `vX.Y.Z` tags exist
there; `custom-opencode-image.md`'s `v0.1.9-oc1.18.31` is an example of a tag
*you* choose for *your own* pushed build, not an upstream artifact). Override
`BASE_IMAGE_TAG` to match whatever `agentImage` / opencode version you're
actually running.

## Publish and point the Agent at it

Same mechanism `custom-opencode-image.md` already documents for the plain
opencode-version bump -- this is just a different image to plug into the
same field. See that doc's:

- ["Make the image pullable"](../custom-opencode-image.md#3-make-the-image-pullable-by-the-cluster)
  (public package vs. `imagePullSecret`)
- ["Point the Agent at your image"](../custom-opencode-image.md#4-point-the-agent-at-your-image)
  (`spec.agentImage: <your-registry>/...`)

## Run the smoke test manually

Against a running container (or from inside a pod built from this image,
with the repo checked out):

```bash
docker run --rm -v "$(pwd):/workspace" -w /workspace \
  --entrypoint /workspace/k8s/kubeopencode/dev-image/smoke-test.sh \
  <your-registry>/kubeopencode-agent-dev:<tag> \
  /workspace
```

(`--entrypoint` overrides the base image's opencode-server entrypoint, which
this Dockerfile deliberately leaves untouched, so the container runs the
smoke test instead.)

Or directly in a pod (repo already at `/workspace` per `agent.yaml`'s
`workspaceDir`):

```bash
k8s/kubeopencode/dev-image/smoke-test.sh /workspace
```

It runs, in order and stopping on the first failure: `gh --version`,
`kubectl version --client`, `python3 -c "import yaml, pytest"`,
`node --version`, `pre-commit --version`, `make verify-opencode-config` --
the exact commands that failed or were worked around in PR #1079.

## Scope of this change

This PR validates the image builds and the smoke test passes in CI (no
registry push, no cluster access -- CI has neither). Not exercised here, and
left as a manual follow-up on the live cluster:

- Pushing the built image to a registry
- Flipping `spec.agentImage` on `deployment/kubeopencode/agent.yaml` /
  `k8s/kubeopencode/agent-default-wf2.yaml`
- In-pod verification against a real `Agent` rollout

See `k8s/kubeopencode/README.md` and `deployment/kubeopencode/README.md` for
where this fits into the rest of the KubeOpenCode config.
