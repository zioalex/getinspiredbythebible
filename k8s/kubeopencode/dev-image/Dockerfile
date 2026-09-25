# syntax=docker/dockerfile:1
#
# KubeOpenCode dev-toolchain agent image (BITB-158)
#
# Derivative of the upstream kubeopencode-agent-devbox image -- the image the
# Agent CRD's spec.executorImage field points at, i.e. the actual worker
# container where `make pre-commit`/`gh`/`kubectl`/task commands run (NOT
# spec.agentImage, which only carries the opencode binary via an init
# container -- see api/v1alpha1/agent_types.go in the upstream
# kubeopencode/kubeopencode repo). See
# docs/BACKLOG_STORIES/BITB-158-kubeopencode-dev-image.md for the friction
# log (PR #1079) this image fixes, and ./README.md for the base-vs-derivative
# split, build/publish/cutover instructions, and known limitations.
#
# The devbox base already ships git/make/curl/jq/gh/kubectl/yq/Node 22.x
# (system install, no NVM)/python3+pip -- this Dockerfile only ADDS what's
# missing: ripgrep, and the Python packages pytest/pre-commit/PyYAML, plus a
# pre-warmed pre-commit hook cache. It does NOT reinstall anything the base
# already provides, and does NOT change the base's own ENTRYPOINT/CMD.
#
# IMPORTANT -- build context must be the REPO ROOT, not this directory. The
# pre-commit-seed step below COPYs the repo's own .pre-commit-config.yaml and
# .secrets.baseline so the pre-warmed hook cache matches exactly what
# `make pre-commit` runs in this repo. Build with:
#   docker build --build-arg BASE_IMAGE_TAG=... \
#     -f k8s/kubeopencode/dev-image/Dockerfile \
#     -t <your-registry>/kubeopencode-agent-dev:<tag> .
# (see ./README.md for the full walkthrough)

# ghcr.io/kubeopencode/kubeopencode-agent-devbox is the upstream image behind
# spec.executorImage -- confirmed to exist via a direct GHCR tag-list query
# (only bare vX.Y.Z tags are published there, e.g. v0.1.9). Override to match
# whatever executorImage / kubeopencode version you're actually running.
ARG BASE_IMAGE_TAG=ghcr.io/kubeopencode/kubeopencode-agent-devbox:v0.1.9

# DL3006 (hadolint): the tag IS pinned, via BASE_IMAGE_TAG's default above --
# hadolint just can't resolve an ARG-based FROM to check it statically.
# hadolint ignore=DL3006
FROM ${BASE_IMAGE_TAG}

# The base image's own Dockerfile sets SHELL ["/bin/bash", "-c"], but SHELL
# does not carry across a FROM boundary into a derivative Dockerfile -- redo
# it here (with pipefail, hadolint DL4006) since a later RUN uses `pip`
# output piped through a check.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Base ends as USER 1000:0; switch back to root (numeric, hadolint DL3066 --
# prefers a UID:GID a host system can always resolve over the "root" name)
# to install packages, then restore 1000:0 at the very end to match the base
# image's own final state exactly.
USER 0:0

# Everything the base is missing for this repo's lint/test loop: ripgrep.
# jq/yq/gh/kubectl/git/make/curl/node/python3 are already in the base image
# -- do not reinstall them here.
# --no-install-recommends + cleaned apt lists per hadolint DL3008/DL3009 --
# this repo's pre-commit hadolint hook already ignores DL3008/DL3018, so pins
# for apt packages themselves are not required here.
# hadolint ignore=DL3008,DL3018
RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Python packages the config-sync loop and pre-commit need on top of the
# base's own python3/pip: PyYAML (generator), pytest (test suites),
# pre-commit (the binary -- hook envs are pre-warmed separately below).
# Debian 12 (bookworm, the base OS) marks the system Python
# externally-managed per PEP 668 -- --break-system-packages is required, not
# optional, for a plain `pip install` against it to succeed. This installs
# against the base's system python3, which on bookworm is 3.11, not 3.12:
# see ./README.md "Python version" for why that's a deliberate, documented
# deviation from the story's literal "python3.12" line (nothing in this
# image's smoke test or `make verify-opencode-config` needs a specific minor
# version). PyYAML/pytest versions match api/requirements.txt and
# api/requirements-dev.txt; pre-commit has no existing repo pin (make
# install-hooks installs it unpinned too) -- pinned here for build
# determinism/hadolint DL3013, bump as needed.
RUN pip install --no-cache-dir --break-system-packages \
        "PyYAML>=6.0.3" \
        "pytest==9.1.1" \
        "pre-commit==4.0.1" \
    && python3 -c "import yaml, pytest" \
    && pre-commit --version

# --- Pre-warm pre-commit hook envs at build time ----------------------------
# Baked at a plain image-layer path, /opt/pre-commit-seed, and set as
# PRE_COMMIT_HOME directly (ENV below) -- no runtime copy step. pre-commit
# 4.0.1 stores absolute paths in each hook repo's db.db; a copy-then-seed
# design (v1's approach) leaves those rows pointing at the original build-time
# paths and silently breaks on the next image rebuild. Setting PRE_COMMIT_HOME
# to this fixed path means every pod running this image tag already has the
# warmed cache present via the image layer itself -- nothing to copy, nothing
# to go stale. This also sidesteps the base's own XDG_CACHE_HOME=/tmp/.cache
# (pre-commit's default cache path would otherwise land in /tmp, which this
# repo's docs already establish is NOT persisted across the mandatory
# `kubectl delete pod` after every `make sync-opencode-configmap`).
#
# These paths are repo-root-relative -- see the build-context note at the top
# of this file. The scratch git repo (WORKDIR below) is created and used
# entirely as root within this single RUN/stage, so there's no UID mismatch
# for git to flag -- no `git config --global --add safe.directory` needed.
WORKDIR /opt/pre-commit-seed-src
COPY .pre-commit-config.yaml .secrets.baseline ./
RUN git init -q \
    && git -c user.email=seed@build -c user.name=seed add -A \
    && git -c user.email=seed@build -c user.name=seed commit -q -m seed \
    && PRE_COMMIT_HOME=/opt/pre-commit-seed pre-commit install-hooks \
    && chmod -R g+w /opt/pre-commit-seed
WORKDIR /workspace
RUN rm -rf /opt/pre-commit-seed-src

ENV PRE_COMMIT_HOME=/opt/pre-commit-seed

# Deliberately excluded (per the story): JDK/Gradle/Android SDK, Docker
# engine, Ollama, Terraform, the full api/ backend venv.

# Restore the base image's own final state exactly (confirmed from the real
# upstream Dockerfile: USER 1000:0, then WORKDIR ${WORKSPACE_DIR}, then
# CMD ["/bin/zsh"]). No ENTRYPOINT/CMD override here -- the base's existing
# entrypoint/cmd is inherited unchanged; this image only adds layers.
USER 1000:0
