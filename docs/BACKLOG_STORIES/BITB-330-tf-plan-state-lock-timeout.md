---
id: BITB-330
status: in-review
priority: P2
size: XS
rank: 45
created: 2026-11-16
prs: [1318]
follow_ups: [BITB-344]
---

# BITB-330: PR `tf-plan` Fails Instantly When Another Run Holds the Terraform State Lock

**Prompted by:** PR #1291 — `tf-plan` went red twice on 2026-11-16 (16:59 and 19:35 UTC) with
`Error acquiring the state lock` while main's deploy (apply) or another PR's plan held
`tfstate/bible-app.tfstate`. A single re-run after the other run finished went green.

## Problem

- `terraform plan` in `.github/workflows/azure-deploy.yml` ("Terraform Plan" step) and
  `terraform apply -auto-approve tfplan` run without `-lock-timeout`, so Terraform fails the
  moment the Azure blob lease is held instead of waiting.
- The workflow's `concurrency` group is `deploy-${{ github.ref }}`, so a PR's plan, other PRs'
  plans and main's deploy all run concurrently against the same state blob.
- Every merge to main also triggers `auto-update-prs.yml`, which updates opted-in PR branches
  at the same moment main's deploy starts — so the collision is routine, not rare. Each one
  costs a red check, a notification and a manual re-run.

## Requirements

- Add `-lock-timeout=10m` (or similar, below the job timeout) to the plan and apply commands.
- Keep the existing exit-code handling (`PIPESTATUS[0]`, `-detailed-exitcode`) intact.
- Optional: a workflow-level guard test (like `api/tests/test_runtime_alignment.py`) asserting
  every `terraform plan|apply` invocation in `.github/workflows` carries `-lock-timeout`.

## Acceptance criteria

- [ ] A PR plan started while main's apply is running waits and then succeeds
- [x] Guard test fails if a new `terraform plan|apply` lacks `-lock-timeout`

## Implementation plan (Plan stage, 2026-11-18)

### Verified against `main` @ c9e7f9a (2026-11-18)

`grep -rn lock-timeout` over the whole repo returns nothing, so the story is unstarted. The
state-mutating invocations are all in `.github/workflows/azure-deploy.yml`:

| Job | Step | Line | Command |
|-----|------|------|---------|
| `tf-plan` | Terraform Plan | ~750 | `terraform plan -var-file=... -out=tfplan -detailed-exitcode 2>&1 \| tee plan_output.txt` |
| `deploy` | Terraform Apply | ~1146 | `terraform apply -auto-approve tfplan` |
| `destroy` | Terraform Destroy | ~1681 | `terraform destroy -var-file=... -auto-approve` |

`tf-validate` runs `terraform init -backend=false` (line 568) — no backend, no state, no lock:
**exempt**. The three `terraform init` calls that do configure the backend are left alone; `init`
only takes a state lock when migrating state, which this workflow never does. `prod-deploy-drift.yml`
runs no terraform (its only match is prose inside a `#` comment).

None of `tf-plan`, `deploy` or `destroy` sets `timeout-minutes`, so each gets the GitHub default of
360 minutes — a 10-minute lock wait is safely below the job timeout.

### Changes

1. **`.github/workflows/azure-deploy.yml`** — add `-lock-timeout=10m` to the three commands above.
   The plan step's exit-code contract must survive untouched: `-detailed-exitcode`, the
   `2>&1 | tee plan_output.txt` pipe, `PLAN_EXIT_CODE=${PIPESTATUS[0]}` and the
   "exit 1 only on code 1" logic. For apply, flags precede the `tfplan` positional argument.
2. **`api/tests/test_deploy_workflow_state_lock.py`** (new) — guard test in the existing
   `test_deploy_workflow_*.py` family, so it runs in the `Backend API Tests` job. It scans every
   `.github/workflows/*.yml`, reconstructs each logical `terraform plan|apply|destroy` command
   (joining `\`-continued lines) and asserts each carries `-lock-timeout=`. It must skip `#`
   comment lines — `prod-deploy-drift.yml:65` contains the words "terraform apply" in prose and a
   naive grep would flag it. `terraform init -backend=false` stays exempt.
3. **Docs** — if `deployment/README.md` has a natural deploy/troubleshooting home, add one line
   saying plan/apply wait up to 10m for the state lease rather than failing immediately.

### Verification

- `cd api && python -m pytest tests/test_deploy_workflow_state_lock.py -q` plus the full backend
  suite; Ruff/Black/MyPy via pre-commit.
- Negative control: temporarily drop one `-lock-timeout` and confirm the guard test fails.
- `actionlint`/`yamllint` via pre-commit for the workflow edit.
- **Cannot be proven in CI:** acceptance criterion 1 (a PR plan waiting out a live apply) needs a
  real lock collision. The flag's semantics are Terraform's; the guard test plus a green `tf-plan`
  run are the achievable gates, and the next natural collision confirms it in production.

## Out of scope

- Splitting PR plans onto a separate (read-only / `-lock=false`) path.

## Follow-ups

- BITB-344 — give PR `tf-plan` a lock-free path so it never waits on main's apply (the deferred
  "splitting PR plans onto a separate read-only path" item above)
