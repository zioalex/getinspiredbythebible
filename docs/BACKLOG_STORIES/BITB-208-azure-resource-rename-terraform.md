# BITB-208: Rename Azure Resources to `voxquieta-*` Through Terraform

**Status:** 🎯 Todo
**Priority:** P3
**Size:** M
**Created:** 2026-10-22
**Follow-up of:** BITB-205 (PR #1188), which reverted the broken workflow-only rename from #1183

## Problem

PR #1183 renamed the Azure resource names in `azure-deploy.yml` and `prod-deploy-drift.yml` to
`voxquieta-*` without renaming the resources. Terraform still creates them from
`project_name = "bible-app"` / `resource_suffix = "mb0172"` (`deployment/terraform.tfvars`), so every
deploy failed until PR #1188 restored the real names. `api/tests/test_workflow_azure_resource_names.py`
now requires workflows to match Terraform.

The `bible-app-*` names are still used across workflows (`golden-set-live.yml`, `prod-monitor.yml`,
`weekly-report.yml`, `db-firewall-cleanup.yml`, `search-eval-full.yml`), scripts (`scripts/monitor/*`,
`scripts/db-backup-restore.sh`, `scripts/update-env-backend-url.sh`), `Makefile`, `.env.production.example`
and `deployment/` docs. Renaming Azure resource groups, the ACR and Container Apps means recreating
them.

## Acceptance criteria

- [ ] Decision on whether the rename is worth it (cost: downtime, new ACR, DNS / custom-domain rebinding, DB move)
- [ ] If yes: a migration plan (Terraform `moved` / import or blue-green), then `project_name` changed and
      every hardcoded name above updated in one PR, with the guard test still green
