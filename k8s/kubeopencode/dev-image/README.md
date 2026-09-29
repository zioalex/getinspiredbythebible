# KubeOpenCode dev-toolchain image (BITB-158)

Derivative agent image that bakes the CLI/toolchain this repo's config-sync
loop and `make pre-commit` need but the upstream base doesn't ship, so
`pytest`/`pre-commit`/`ripgrep` don't have to be cold-installed (or fail to
install) on every fresh pod.

> **This PR ships the Dockerfile + CI build validation only.** Pushing the
> built image to a registry and flipping `spec.executorImage:` on the live
> `Agent` is a manual follow-up -- this repo's CI has no registry push
> credentials configured (same limitation `custom-opencode-image.md`
> documents for the opencode-version bump workflow). See "Publish and point
> the Agent at it" below, which reuses that exact mechanism rather than
> inventing a new one.

## Which base image, and which CRD field

The `kubeopencode.io/v1alpha1` `Agent` spec has three separate image fields
(`api/v1alpha1/agent_types.go` in the upstream `kubeopencode/kubeopencode`
repo):

| Field | What it is | Default |
|---|---|---|
| `agentImage` | Init container image that copies the `opencode` binary to `/tools/opencode`. Never runs a shell, never executes a task. | `kubeopencode-agent-opencode` |
| **`executorImage`** | **The main worker container -- the development environment where tasks actually run.** This is the field this image is for. | `kubeopencode-agent-devbox` |
| `attachImage` | Minimal image for `--attach` pods. Not relevant here. | -- |

This image is a derivative of `kubeopencode-agent-devbox` (the
`executorImage` default), **not** `kubeopencode-agent-opencode`. The
`opencode` image's final build stage is plain `alpine:3.24.1` with no shell
and no package manager -- there is nothing to layer a dev toolchain onto,
and it isn't the container where commands run anyway. Setting `agentImage:`
to a derivative of it (as an earlier draft of this image did) would build
successfully but never actually be used to run `make pre-commit`/`gh`/
`kubectl`; the toolchain has to live on `executorImage` instead. See
"Publish and point the Agent at it" below for the exact field to set.

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

Two of those findings turned out to be independent of the image entirely and
are fixed directly:

- **`lingua-language-detector` unsatisfiable** -- `make pre-commit` depended
  on `install-deps`, which pulls the *application's* full dependency graph
  (`api/requirements-dev.txt` -> `api/requirements.txt`, including
  `lingua-language-detector`). `pre-commit run --all-files` never needed
  that: every hook except the local `eslint` one manages its own isolated
  venv via `pre-commit install-hooks`, and `eslint` shells to `npx` directly.
  The `Makefile`'s `pre-commit` target now depends on `install-hooks`
  instead.
- **ESLint hook's NVM assumption** -- turned out to be moot on this base:
  `kubeopencode-agent-devbox` installs Node 22.x as a plain system package
  (NodeSource `setup_22.x`), not via NVM. The `eslint` hook's
  `[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"` guard is a no-op when
  `$NVM_DIR/nvm.sh` doesn't exist, and the hook falls through to whatever
  `node`/`npx` is already on `PATH` -- the base's system Node. No image
  change, no `.pre-commit-config.yaml` change needed.

## What's already in the base vs. what this image adds

`kubeopencode-agent-devbox` (Debian `bookworm-slim`) already ships:

| Already in the base | Notes |
|---|---|
| `git`, `make`, `curl`, `jq` | |
| `gh` | via apt repo |
| `kubectl` | `dl.k8s.io` stable |
| `yq` | mikefarah/yq, `latest` |
| Node 22.x | NodeSource `setup_22.x`, a **system** install -- no NVM |
| `python3`, `python3-pip`, `python3-venv`, `pipx` | system Python (bookworm's default: 3.11) |

This derivative **only adds**:

| Added here | Why |
|---|---|
| `ripgrep` | not in the base |
| `pytest==9.1.1`, `pre-commit==4.0.1`, `PyYAML>=6.0.3` | base has `pip` but not these packages |
| Pre-warmed `pre-commit` hook envs at `/opt/pre-commit-seed` | see "Pre-warmed pre-commit cache" below |

Nothing the base already provides is reinstalled.

Deliberately **excluded** (per the story): JDK 17/Gradle/Android SDK, Docker
engine, Ollama, Terraform, the full `api/` backend venv.

## Python version: 3.11, not 3.12

The story's acceptance criteria literally say "Python 3.12". This image
ships **3.11** instead, deliberately: the base OS is Debian bookworm, whose
system `python3` is 3.11, and `apt-get install python3.12` is not available
on bookworm without adding extra repositories or compiling from source --
out of proportion for what this image needs. Nothing in the smoke test or
`make verify-opencode-config` requires a specific minor version -- the
`Makefile`'s `PYTHON_VERSION := python3` and the smoke test's
`python3 -c "import yaml, pytest"` just need *some* `python3` with those
packages importable, and 3.11 satisfies that. (This is about this
lint/test-tooling image only; the `api/` backend's own 3.12 requirement is
about the application runtime and is unaffected.)

Because bookworm's system Python is externally managed (PEP 668), the
Python packages above are installed with `pip install --break-system-packages`
rather than into a venv -- a plain `pip install` against the system
interpreter fails with an `externally-managed-environment` error otherwise.

## Pre-warmed pre-commit cache

The hook environments (`black`, `ruff`, `mypy`, `bandit`, `yamllint`,
`shellcheck`, `markdownlint`, `detect-secrets`, `prettier` x2 -- every hook in
`.pre-commit-config.yaml` **except** `hadolint-docker`, which has no
installable environment at all; see "Known limitation" below) are installed
at build time (`pre-commit install-hooks`) against a scratch copy of this
repo's `.pre-commit-config.yaml` and `.secrets.baseline`, and the resulting
cache is baked at the image-layer path `/opt/pre-commit-seed`.

`PRE_COMMIT_HOME` is set to that path directly via `ENV` in the Dockerfile --
**there is no runtime copy step**. An earlier draft of this image baked the
seed and then had the `Makefile` `cp -r` it into a PVC-backed
`PRE_COMMIT_HOME` on first use; that broke by construction, because
pre-commit 4.0.1 stores **absolute paths** in each hook repo's `db.db`. After
a copy, those rows still point at the original build-time paths, which only
"work" by coincidence (the source directory still exists post-copy), and
silently break on the next image rebuild (the seed's `mkdtemp` directory
names change) while a naive `[ ! -d "$PRE_COMMIT_HOME" ]` guard sees the
stale copy and never re-seeds. Pointing `PRE_COMMIT_HOME` straight at the
image-layer path sidesteps all of that: every pod running this image tag
already has `/opt/pre-commit-seed` present via the image layer, with nothing
to copy and no path-mismatch risk, and the first real `make pre-commit` in a
fresh pod is a cache hit for free.

This also fixes the underlying problem the story names: the base image sets
`XDG_CACHE_HOME=/tmp/.cache`, and pre-commit's default cache path follows
`$XDG_CACHE_HOME/pre-commit` when that's set -- landing in `/tmp`, which
`deployment/kubeopencode/README.md` already establishes is **not** persisted
across the mandatory `kubectl delete pod` after every
`make sync-opencode-configmap`. Overriding `PRE_COMMIT_HOME` explicitly
sidesteps that regardless of where `/tmp` lives.

The seed directory is `chmod -R g+rwX` at build time, matching the base
image's own `USER 1000:0` (arbitrary-UID-friendly, GID 0) convention. An
earlier version of this image used `g+w` only, which added write but left
`pre-commit install-hooks`'s own restrictive `db.db` (600) and hook-repo
directories (700) unreadable to group 0 -- every real hook run under the
runtime `USER 1000:0` failed with `unable to open database file`, something
a smoke test that only checks `pre-commit --version` never caught (see
`smoke-test.sh`, which now also runs a real hook). `g+rwX` grants read
everywhere, write everywhere, and execute only where something already has
an execute bit (directories, and hook-venv scripts that need `+x` to run).

On a normal laptop or CI runner (no `/opt/pre-commit-seed`), `pre-commit`
falls back to its own default cache location and behaves exactly as it did
before this image existed.

**What's still not fully offline:** `make pre-commit` depends on
`install-hooks` (see `Makefile`), which runs `pip install -q pre-commit`
into `.venv` -- an unpinned install from PyPI, separate from this image's own
`pre-commit==4.0.1` on the system `python3`. That means a pod still needs
PyPI reachability the first time `make pre-commit` runs (pip's own resolver
check), even though the *hook environments* it then drives are fully
pre-warmed and need no network. In practice the two `pre-commit` versions
are cache-compatible (`4.0.1`'s seed was confirmed reusable by a `.venv`
running `4.6.2`), so this doesn't cost a re-fetch of the 13 hook repos --
only pip's own small resolve/install of the `pre-commit` package itself.

### Known limitation: hadolint can't actually run via `make pre-commit` in-pod

`hadolint-docker` (this repo's actual hadolint hook type) is a `language:
docker_image` pre-commit hook -- unlike the venv-based hooks above, it has no
isolated environment for `pre-commit install-hooks` to create or pre-warm at
all; it runs by invoking `docker run hadolint/hadolint ...` directly every
time, needing a working Docker *daemon* at invocation. The story's own
"deliberately excluded" list excludes the Docker engine from this image, so
this is a real, unresolvable-within-scope tension: there is nothing this
image can pre-warm for this specific hook, and invoking it inside a pod
built from this image will fail without Docker regardless. CI's own hadolint step
(`.github/workflows/kubeopencode-dev-image.yml`, via `hadolint-action`, and
`test_update.yml`'s equivalent for the rest of the repo) runs outside
`make pre-commit` entirely, against a pinned hadolint binary/action, and is
unaffected by this.

## Build

Build context must be the **repo root** (not this directory) -- the
pre-commit-seed layer `COPY`s this repo's own `.pre-commit-config.yaml` and
`.secrets.baseline` so the warmed cache matches exactly what `make pre-commit`
runs here:

```bash
docker build \
  --build-arg BASE_IMAGE_TAG=ghcr.io/kubeopencode/kubeopencode-agent-devbox:v0.1.9 \
  -f k8s/kubeopencode/dev-image/Dockerfile \
  -t <your-registry>/kubeopencode-agent-dev:<tag> \
  .
```

`BASE_IMAGE_TAG` defaults to `v0.1.9`, confirmed against the registry's real
tag list (only bare `vX.Y.Z` tags exist there). Override `BASE_IMAGE_TAG` to
match whatever `executorImage` / kubeopencode version you're actually
running.

## Publish and point the Agent at it

Same mechanism `custom-opencode-image.md` already documents for the plain
opencode-version bump -- this is a different image plugged into a
**different** field. Follow that doc's
["Make the image pullable"](../custom-opencode-image.md#3-make-the-image-pullable-by-the-cluster)
section unchanged (public package vs. `imagePullSecret`), then set:

```yaml
spec:
  executorImage: <your-registry>/kubeopencode-agent-dev:<tag>
```

on the `Agent` -- **not** `spec.agentImage`, which is a different field for a
different purpose (it only supplies the `opencode` binary via an init
container; see "Which base image, and which CRD field" above).

## Run the smoke test manually

Against a running container (or from inside a pod built from this image,
with the repo checked out):

```bash
docker run --rm -v "$(pwd):/workspace" -w /workspace \
  --entrypoint /workspace/k8s/kubeopencode/dev-image/smoke-test.sh \
  <your-registry>/kubeopencode-agent-dev:<tag> \
  /workspace
```

(The base image has no `ENTRYPOINT` -- only `CMD ["/bin/zsh"]`, untouched by
this Dockerfile. `--entrypoint` here just points the container at the smoke
test instead of a shell. If your host UID differs from the image's baked
`USER 1000:0`, add `--user "$(id -u):0"` too, same as CI does -- see
`.github/workflows/kubeopencode-dev-image.yml`.)

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
- Setting `spec.executorImage` on `deployment/kubeopencode/agent.yaml` /
  `k8s/kubeopencode/agent-default-wf2.yaml`
- In-pod verification against a real `Agent` rollout

See `k8s/kubeopencode/README.md` and `deployment/kubeopencode/README.md` for
where this fits into the rest of the KubeOpenCode config.
