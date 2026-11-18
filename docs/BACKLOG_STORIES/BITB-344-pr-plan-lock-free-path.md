---
id: BITB-344
status: todo
priority: P3
size: S
created: 2026-11-18
---

# BITB-344: Give PR `tf-plan` a Lock-Free Path So It Never Waits on Main's Apply

**Follow-up of:** BITB-330 (deferred there as out of scope).

## Problem

BITB-330 added `-lock-timeout=10m` to `terraform plan`/`apply`/`destroy`, so a run that meets a
concurrent run holding the state lease now waits instead of failing instantly. That removes the red
check, but it does not remove the contention — it converts it into waiting:

- A PR's `tf-plan` can now sit idle for up to 10 minutes holding a GitHub-hosted runner, purely
  because `main`'s deploy is applying.
- If the apply takes longer than 10 minutes the PR plan still fails, with the same
  `Error acquiring the state lock` message BITB-330 set out to remove — just 10 minutes later.
- The root cause named in BITB-330's problem statement is untouched: the `azure-deploy.yml`
  concurrency group is `deploy-${{ github.ref }}`, so every PR's plan, every other PR's plan and
  `main`'s deploy all contend for the single `tfstate/bible-app.tfstate` lease. `auto-update-prs.yml`
  makes the collision routine by updating opted-in PR branches at the same moment `main`'s deploy
  starts.

A PR plan is a read-only, advisory artifact: it is posted as a PR comment and, on the
`pull_request` event, is never applied (the plan artifact is only uploaded when
`github.event_name != 'pull_request'`). It does not need the write lease at all.

## Fix sketch

- Pass `-lock=false` to `terraform plan` **only** on the `pull_request` event, keeping the lease (and
  `-lock-timeout`) for push/dispatch runs that may apply. Terraform reads state without taking the
  blob lease, so a PR plan becomes immune to contention.
- Guard the asymmetry in `api/tests/test_deploy_workflow_state_lock.py` (BITB-330): assert that
  `-lock=false` is reachable only on the PR path, and that no `apply` or `destroy` invocation ever
  carries it. A `-lock=false` apply can corrupt state, so this is the assertion that matters.
- Document the trade-off: a `-lock=false` plan can in principle read state mid-apply and show a
  slightly stale diff. That is acceptable for an advisory PR comment and is why it must not extend
  to apply.

## Acceptance criteria

- [ ] A PR `tf-plan` started while `main`'s apply holds the lease succeeds without waiting
- [ ] `-lock=false` is confined to the `pull_request` plan path; a test fails if it ever reaches
      `terraform apply` or `terraform destroy`
- [ ] A deliberate violation is proven to fail that test, not just asserted to
- [ ] The stale-diff trade-off is written down next to the flag

## Out of scope

- Splitting state per environment, or moving to Terraform workspaces. That is the general fix for
  contention but is a much larger change than this story.
- Changing the `concurrency` group semantics for the deploy job itself.
