---
id: BITB-330
status: todo
priority: P2
size: XS
rank: 45
created: 2026-11-16
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
- [ ] Guard test fails if a new `terraform plan|apply` lacks `-lock-timeout`

## Out of scope

- Splitting PR plans onto a separate (read-only / `-lock=false`) path.
