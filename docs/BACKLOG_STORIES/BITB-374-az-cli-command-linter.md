---
id: BITB-374
status: in-progress
priority: P2
kind: chore
size: M
created: 2026-11-28
follow_ups: [BITB-375, BITB-376]
---

# BITB-374: Lint every az CLI command against the real Azure CLI

## Problem

On 2026-11-27 the new `.github/workflows/acr-purge.yml` (BITB-372) failed in production on
`az acr show-usage --registry "$ACR_NAME" -o table`: the command only accepts `--name/-n`
(and `--resource-group/-g`). The workflow's unit tests (substring checks on the YAML) and two
static reviews all passed, because nothing ever asked the CLI whether the flag exists. The repo
runs about 120 `az` invocations (83 distinct command shapes) across ~33 files: workflows, shell
scripts, the Makefile and Python subprocess calls. Each is one typo away from the same failure,
and most of them only run against production.

Owner decision (2026-11-28): add a CI linter that checks every `az` invocation against the real CLI.

## Requirements

- `scripts/check_az_commands.py` (stdlib only) extracts every `az ...` call from
  `.github/workflows/*.yml` `run:` scripts, `.github/actions/**/action.yml`, `scripts/**/*.sh`,
  `deployment/**/*.sh`, the `Makefile` (recipe lines, `$$`, `@`/`-` prefixes) and `["az", ...]`
  list/tuple literals in `scripts/**/*.py` and `api/**/*.py` (AST), with file and line.
- Shell handling: `\` continuations, `$( )` and backtick substitutions (nested too), pipes,
  `||`, `&&`, `;`, comments, quoting, `--flag=value`, variable expansions, heredoc bodies
  skipped. `az` counts only in command position, never in prose, `echo` strings or comments.
- Validation asks the CLI (`az <path> --help`, dynamic extension install off, telemetry off, per-run
  cache, timeout): unknown command, incomplete command (a group), unknown long flag, unknown short flag.
  Global flags are always accepted. `--cmd` values of `az acr run` are never linted (ACR's own DSL).
- Allowlist `scripts/az-lint-allowlist.txt` (`path:pattern  # reason`): a reason is mandatory and an
  entry that no longer matches a finding fails the run as stale.
- Extensions are pinned in `scripts/az-extensions.txt`; a command that needs one is a finding that names it.
- Exit 0 clean, 1 findings, 2 environment error (no `az`). `--list` prints every extracted invocation;
  `--json` prints findings.
- Parsing and validation are pure with an injectable help provider, so the tests need no azure-cli.
- CI: `.github/workflows/az-lint.yml` (pinned `azure-cli`, no login, no secrets); `make az-lint`;
  a pre-push hook that skips cleanly when `az` is not installed.

## Acceptance criteria

- [x] `az acr show-usage --registry "$ACR_NAME" -o table` fails, `... --name "$ACR_NAME" ...` passes
      (regression tests against the canned `show-usage` help).
- [x] Extraction fixtures: continuations, nested `$(az ...)`, pipes and `|| true`, `--a=b`, quoted
      `#` and `|`, heredoc, prose `az`, Makefile `@az` with `$$VAR`, YAML `run: |`, Python argv list.
- [x] Validation fixtures: unknown flag, short flag, global flags, group vs command, extension
      missing, allowlist match / missing reason / stale entry.
- [x] A run over the whole repo with azure-cli 2.93.0 reports the acr-purge `--registry` finding
      (allowlisted as "fixed in #1353" so CI is green) and nothing else that is unexplained.
- [x] The allowlist entry for acr-purge fails the run as stale once #1353 merges.
- [x] `make az-lint`, `az-lint.yml`, pre-push hook, `docs/CONTRIBUTING.md`, AGENTS.md updated.
- [ ] Owner step: after #1353 merges, delete the `acr-purge.yml` entry from
      `scripts/az-lint-allowlist.txt` (the linter fails the run until you do).
- [ ] Owner step: confirm the first CI run of `az-lint.yml` installs `log-analytics==0.2.2` (the
      extension download host was unreachable from the build sandbox, so that pin and the two
      `az monitor log-analytics query` calls were verified only through the skip path).

## Out of scope

- Validating flag *values* (`--output` choices, resource names), or `--cmd` task strings.
- `az` calls inside Dockerfiles, docs, `echo`ed hints and Terraform `local-exec`.
- Wrappers such as `xargs az ...`, `bash -c "az ..."` or `retry az ...` (not in command position).
- Extension-aware help for Python strings (`shell=True`): only argv list literals are read.

## Findings from the first run (azure-cli 2.93.0)

| Where | Finding | Disposition |
| ----- | ------- | ----------- |
| `.github/workflows/acr-purge.yml:83,175` | `--registry` is not a flag of `az acr show-usage` | The BITB-372 incident. Fixed in #1353; allowlisted here until it merges |
| `.github/workflows/prod-monitor.yml:402`, `scripts/az-logs.sh:67` | `az monitor log-analytics query` is not in the core CLI (extension `log-analytics`) | Pinned in `scripts/az-extensions.txt`; making the callers install it is BITB-375 |
| `make test-makefile` | 3 failures on `main` that predate this story | BITB-376 |

## Follow-ups

- BITB-375: make `prod-monitor.yml` and `az-logs.sh` install the `log-analytics` extension themselves.
- BITB-376: `make test-makefile` fails on `main` (stale audit report, `make az-logs` doc references).
