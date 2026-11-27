---
id: BITB-373
status: in-review
priority: P2
kind: chore
size: XS
created: 2026-11-27
depends_on: [BITB-372]
---

# BITB-373: ACR Purge Workflow Dies on `az acr show-usage --registry`

## User story

As the owner paying the Azure invoice, I want the weekly ACR purge job (BITB-372) to actually
run, so that image storage stays inside the Basic registry's 10 GB included tier instead of
accumulating a ~$4.7/month overage that nothing deletes.

## Evidence

The first scheduled run of `.github/workflows/acr-purge.yml` (workflow run 46056530171)
failed at the third step, "Registry usage before":

- `az acr show-usage` accepts `--name/-n` (like every registry-* read command); it has no
  `--registry` parameter (that flag belongs to the run-scheduling commands such as
  `az acr run`, which this workflow uses correctly).
- The step exited non-zero before the lock/purge/unlock steps, so the weekly purge never
  executed — the cost cut that motivated BITB-372 was dead on arrival.

## Fix

`acr-purge.yml`, two lines, both `az acr show-usage` invocations:

- "Registry usage before": `--registry "$ACR_NAME"` → `--name "$ACR_NAME"`
- "Registry usage after": same fix on the `|| true` line

No other `az acr` command is touched: `az acr run` keeps `--registry` (correct for that
command) and the `az acr repository show/update/show-tags` steps already use `--name`.

## Acceptance criteria

- [x] `yamllint .github/workflows/acr-purge.yml` passes
- [x] Both `az acr show-usage` lines use `--name "$ACR_NAME"`; every other `az` invocation unchanged
- [ ] A scheduled or manual (dry-run) workflow run gets past "Registry usage before"

## Out of scope

- Purge retention policy (`--ago 14d --keep 10 --untagged`) — BITB-372
- The Telegram notify step and its failure handling
