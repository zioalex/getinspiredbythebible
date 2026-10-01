#!/usr/bin/env bash
# BITB-158: KubeOpenCode dev-image smoke test.
#
# Runs the exact commands that failed or were worked around in-pod during the
# PR #1079 session (see docs/BACKLOG_STORIES/BITB-158-kubeopencode-dev-image.md),
# to prove the dev-toolchain image actually fixes them.
#
# Usage: smoke-test.sh [REPO_DIR]
#   REPO_DIR - path to a checked-out copy of this repo (default: .). The last
#              check, `make verify-opencode-config`, needs the actual repo
#              (reads .opencode/agents/*.md and scripts/generate-opencode-config.py).
#              In CI the checkout is already present; in a running pod it's
#              /workspace (see agent.yaml's workspaceDir) -- both work the
#              same way via this argument.
#
# Exits non-zero on the first failing command.

set -euo pipefail

REPO_DIR="${1:-.}"

run() {
    echo "+ $*"
    "$@"
}

echo "=== KubeOpenCode dev-image smoke test ==="

run gh --version
run kubectl version --client
run python3 -c "import yaml, pytest"
run node --version
run pre-commit --version

echo "+ cd $REPO_DIR"
cd "$REPO_DIR"
run make verify-opencode-config

# `pre-commit --version` above never opens the hook cache -- it can pass even
# when PRE_COMMIT_HOME is unreadable by the running user (this is exactly how
# a broken baked cache slipped through the first build of this image: every
# real hook run failed with "unable to open database file", but the smoke
# test only checked --version). Actually run a fast, dependency-free hook
# against real repo files so a cache-permission or path regression fails
# here instead of silently in a pod. check-yaml needs no network and no
# Docker (unlike the hadolint-docker hook -- see README's "Known limitation"
# section), and this repo has plenty of YAML files to match against.
run pre-commit run check-yaml --all-files

echo "=== All smoke-test checks passed ==="
