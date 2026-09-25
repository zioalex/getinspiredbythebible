# syntax=docker/dockerfile:1
#
# KubeOpenCode dev-toolchain agent image (BITB-158)
#
# Derivative of the upstream kubeopencode-agent-opencode image (the one
# `custom-opencode-image.md` documents building/publishing) that layers on
# the CLI/toolchain this repo's config-sync loop (`gen -> verify -> sync ->
# delete pod`) and `make pre-commit` need in-pod. See
# docs/BACKLOG_STORIES/BITB-158-kubeopencode-dev-image.md for the friction
# log (PR #1079) this image fixes, and ./README.md for build/publish/cutover
# instructions.
#
# This image does NOT change the opencode binary itself or the base image's
# ENTRYPOINT/CMD -- it only adds layers. Bumping the opencode version is still
# done exactly as custom-opencode-image.md describes (rebuild upstream with a
# newer OPENCODE_VERSION, then point BASE_IMAGE_TAG below at your new tag).
#
# IMPORTANT -- build context must be the REPO ROOT, not this directory. The
# pre-commit-seed step below COPYs the repo's own .pre-commit-config.yaml and
# .secrets.baseline so the pre-warmed hook cache matches exactly what
# `make pre-commit` runs in this repo. Build with:
#   docker build --build-arg BASE_IMAGE_TAG=... \
#     -f k8s/kubeopencode/dev-image/Dockerfile \
#     -t <your-registry>/kubeopencode-agent-dev:<tag> .
# (see ./README.md for the full walkthrough)

# custom-opencode-image.md's walkthrough uses "v0.1.9-oc1.18.31" as an
# illustrative example of a tag YOU choose when you push your OWN derivative
# build -- it was never published upstream and does not exist on
# ghcr.io/kubeopencode/kubeopencode-agent-opencode (confirmed against the
# registry's real tag list: only bare vX.Y.Z tags exist there, e.g. v0.1.9).
# Default here to that real upstream tag instead, so `docker build` with no
# override actually resolves. Override to match whatever `agentImage` /
# opencode version you're actually running -- see custom-opencode-image.md
# step 1.
ARG BASE_IMAGE_TAG=ghcr.io/kubeopencode/kubeopencode-agent-opencode:v0.1.9

# DL3006 (hadolint): the tag IS pinned, via BASE_IMAGE_TAG's default above --
# hadolint just can't resolve an ARG-based FROM to check it statically.
# hadolint ignore=DL3006
FROM ${BASE_IMAGE_TAG}

# The upstream kubeopencode-agent-opencode image is Debian-based (apt-get is
# available). If a future upstream base switches package managers, swap the
# install block below accordingly -- don't assume Debian silently.

# Fail RUN pipelines (e.g. `curl ... | bash` below) on the first failing
# stage, not just the last one's exit code (hadolint DL4006).
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Match the cluster's server minor version -- `kubectl version` on a live pod
# shows the mismatch if this drifts.
ARG KUBECTL_VERSION=v1.31.4
# A current stable `gh` release at plan time; bump as needed.
ARG GH_VERSION=2.63.2
# mikefarah/yq (Go binary) -- current stable release at plan time.
ARG YQ_VERSION=v4.44.3
# NOT a guess: the exact pin in .pre-commit-config.yaml's
# default_language_version.node, which the local `eslint` pre-commit hook
# sources via `$NVM_DIR/nvm.sh`.
ARG NODE_VERSION=22.22.0

ENV DEBIAN_FRONTEND=noninteractive

# --no-install-recommends + cleaned apt lists per hadolint DL3008/DL3009 --
# this repo's pre-commit hadolint hook already ignores DL3008/DL3018, so pins
# for apt packages themselves are not required here.
# hadolint ignore=DL3008,DL3018
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        make \
        bash \
        curl \
        ca-certificates \
        ripgrep \
        jq \
        unzip \
        python3.12 \
    && rm -rf /var/lib/apt/lists/*

# apt's python3-pip package targets the OS-default python3, which is not
# guaranteed to be python3.12 (e.g. plain Debian bookworm defaults to 3.11) --
# bootstrap pip directly for the 3.12 interpreter instead of depending on that
# alignment.
RUN curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
    && python3.12 /tmp/get-pip.py \
    && rm -f /tmp/get-pip.py \
    && python3.12 -m pip --version

# --- kubectl: official dl.k8s.io binary download ---------------------------
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL -o /usr/local/bin/kubectl \
        "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && kubectl version --client

# --- gh CLI: pinned release tarball -----------------------------------------
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL -o /tmp/gh.tar.gz \
        "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" \
    && tar -xzf /tmp/gh.tar.gz -C /tmp \
    && install -m 0755 "/tmp/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh \
    && rm -rf /tmp/gh.tar.gz "/tmp/gh_${GH_VERSION}_linux_${ARCH}" \
    && gh --version

# --- yq: mikefarah/yq Go binary ---------------------------------------------
# No existing pin to match (this repo's prettier-yaml/yamllint pre-commit
# hooks don't install a yq binary today) -- pick a current stable release.
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL -o /usr/local/bin/yq \
        "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_${ARCH}" \
    && chmod +x /usr/local/bin/yq \
    && yq --version

# --- Python toolchain --------------------------------------------------------
# python3.12/pip installed above. Pull in the packages the config-sync loop
# and pre-commit need: PyYAML (generator), pytest (test suites), pre-commit
# (the binary -- hook envs are pre-warmed separately below). PyYAML/pytest
# versions match api/requirements.txt and api/requirements-dev.txt; pre-commit
# has no existing repo pin (make install-hooks installs it unpinned too) --
# pinned here for build determinism/hadolint DL3013, bump as needed.
RUN python3.12 -m pip install --no-cache-dir --break-system-packages \
        "PyYAML>=6.0.3" \
        "pytest==9.1.1" \
        "pre-commit==4.0.1" \
    && python3.12 -c "import yaml, pytest" \
    && pre-commit --version

# --- Node via NVM ------------------------------------------------------------
# Baking NVM (not a bare system Node) means the ESLint pre-commit hook, which
# explicitly sources $NVM_DIR/nvm.sh, works unmodified with zero changes to
# .pre-commit-config.yaml.
ENV NVM_DIR=/opt/nvm
# SC1091: nvm.sh doesn't exist yet at lint time (installed by the line above
# it, in the same RUN) -- shellcheck can't follow it statically.
# hadolint ignore=SC1091
RUN mkdir -p "$NVM_DIR" \
    && curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" \
    && nvm install "$NODE_VERSION" \
    && nvm alias default "$NODE_VERSION" \
    && ln -sf "$NVM_DIR/versions/node/v$NODE_VERSION/bin/node" /usr/local/bin/node \
    && ln -sf "$NVM_DIR/versions/node/v$NODE_VERSION/bin/npm" /usr/local/bin/npm \
    && ln -sf "$NVM_DIR/versions/node/v$NODE_VERSION/bin/npx" /usr/local/bin/npx \
    && node --version

# Make both interactive shells and pre-commit's hook subshells (which run
# `bash -c '... . "$NVM_DIR/nvm.sh" ...'`, see the local `eslint` hook entry
# in .pre-commit-config.yaml) pick up NVM.
# SC2016: the single quotes are intentional -- $NVM_DIR must expand later,
# when /etc/profile.d/nvm.sh is sourced at shell start, not now at build time.
# hadolint ignore=SC2016
RUN mkdir -p /etc/profile.d \
    && printf 'export NVM_DIR=%s\n[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"\n' "$NVM_DIR" \
        > /etc/profile.d/nvm.sh

# --- Pre-warm pre-commit hook envs at build time ----------------------------
# PRE_COMMIT_HOME under /workspace (spec.workspaceDir): the one path the
# Agent CRD's spec.persistence.workspace PVC actually persists across the
# mandatory `kubectl delete pod` after every `make sync-opencode-configmap`
# (deployment/kubeopencode/README.md). /tmp is explicitly NOT persisted (same
# doc). This is what makes `make pre-commit` survive pod restarts.
ENV PRE_COMMIT_HOME=/workspace/.cache/pre-commit

# /workspace is an empty PVC mount at container start on a fresh pod/PVC (the
# mount shadows anything baked into the image at that path), so the warmed
# hook envs are instead baked at a fixed image-layer path, /opt/pre-commit-seed,
# and copied into PRE_COMMIT_HOME on first use by the guarded step added to the
# repo's `make pre-commit` target (see ../../../Makefile).
# These paths are repo-root-relative -- see the build-context note at the top
# of this file.
COPY .pre-commit-config.yaml /tmp/pre-commit-seed-src/.pre-commit-config.yaml
COPY .secrets.baseline /tmp/pre-commit-seed-src/.secrets.baseline
# DL3003: deliberately `cd` rather than WORKDIR -- this is a scratch dir used
# only within this single RUN, and changing the image's global WORKDIR here
# would leak into the base image's own entrypoint (untouched by this file).
# hadolint ignore=DL3003
RUN git config --global --add safe.directory '*' \
    && cd /tmp/pre-commit-seed-src \
    && git init -q \
    && git add -A \
    && git -c user.email=seed@example.com -c user.name=seed commit -q -m seed \
    && PRE_COMMIT_HOME=/opt/pre-commit-seed pre-commit install-hooks \
    && rm -rf /tmp/pre-commit-seed-src

# Deliberately excluded (per the story): JDK/Gradle/Android SDK, Docker
# engine, Ollama, Terraform, the full api/ backend venv.

# No ENTRYPOINT/CMD here -- the base image's existing entrypoint runs the
# opencode server. Overriding it would break the pod; this image only adds
# layers on top.
