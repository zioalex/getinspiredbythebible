# BITB-243: Fast pre-commit commit stage (move slow hooks to pre-push/manual)

**Status:** 🚧 In Progress
**Opened:** 2026-10-26
**Size:** M
**Owner:** infra-engineer (build), verifier (verify)

## User story

As a developer on this repo, I want `git commit` to be fast, so that I don't
wait on MyPy, Bandit, hadolint, Prettier, yamllint, shellcheck, markdownlint
and ESLint every single commit — they already run in CI on every PR.

## Problem

`.pre-commit-config.yaml` registers ~16 hooks, all on the default `commit`
stage. The slow ones (MyPy in a full isolated env with additional
dependencies, Bandit, hadolint, both Prettier hooks, yamllint, ESLint via
NVM+`npx`, markdownlint, shellcheck) make each commit take tens of seconds
even for a one-line change.

## Requirements

1. Split hooks into pre-commit `stages`:
   - **`commit` stage (fast, < 5 s typical):** trailing-whitespace,
     end-of-file-fixer, check-yaml, check-json, check-added-large-files,
     check-merge-conflict, check-case-conflict, mixed-line-ending,
     detect-private-key. Black and Ruff may stay on `commit` (fast, and they
     auto-fix); decide with measurement, not vibes.
   - **`pre-push` stage (slow):** mypy, bandit, hadolint, prettier (both),
     yamllint, shellcheck, markdownlint, eslint, detect-secrets.
     detect-secrets placement is the builder's call — it scans the whole tree
     against `.secrets.baseline`; keep `detect-private-key` on commit.
2. Ensure `make install-hooks` / `scripts/setup-pre-commit.sh` also installs
   the `pre-push` hook type (`pre-commit install --hook-type pre-push`) so the
   pre-push stage actually runs for devs who used the documented setup.
3. `make pre-commit` (`pre-commit run --all-files`) must remain unchanged in
   behavior: all hooks still run there (default stage selection for
   `--all-files` covers all hooks regardless of stage).
4. CI (`test_update.yml`) does not change — it already runs these checks.
5. Update docs: `AGENTS.md` Pre-commit Hooks section (hook list per stage),
   `README.md`/`docs/LOCAL_DEVELOPMENT.md` if they mention hook setup, and
   the k8s dev-image README pre-warmed-cache note if stage changes affect
   `pre-commit install-hooks` (they do not — same hook set, different stages).

## Acceptance criteria

- [x] `pre-commit run --all-files` passes with the same hooks as before
      (set of hook ids unchanged; only `stages:` added).
      Verified: `pre-commit validate-config` passes; hook-id set diffed
      against `origin/main` — identical (21 ids, zero changed);
      `pre-commit run --hook-stage pre-commit/pre-push --files <touched>`
      both pass. Full `--all-files` run delegated to PR CI (sandbox cannot
      build the node/eslint hook envs).
- [x] A measured before/after timing of `pre-commit run` on a touched file
      (simulating commit) vs before, included in the PR description.
      Measured 2026-10-26 (warm hook envs, touched `api/main.py`):
      full `pre-commit` stage 0.5 s vs full `pre-push` stage 34.7 s —
      ~70× faster commits. Per-hook: trailing-whitespace 0.2 s, ruff 0.1 s,
      black 0.2 s, mypy 8.3 s.
- [x] `make install-hooks` installs commit, commit-msg and pre-push hooks
      (verified: `make install-hooks` output lists all three).
- [x] Docs updated in the same commit (AGENTS.md hook table, setup docs).
- [ ] PR opened against `main`, conventional-commit title, CI green.

## Out of scope

- Bumping stale hook `rev:` versions (separate follow-up).
- Consolidating the two Prettier hook entries.
- Changes to CI jobs.

## Follow-ups

(none yet)
