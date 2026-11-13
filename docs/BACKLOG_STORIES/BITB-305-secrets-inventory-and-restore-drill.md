---
id: BITB-305
status: todo
priority: P1
size: M
rank: 70
created: 2026-11-11
---

# BITB-305: Secrets-Expiry Inventory and Check, Database Restore Drill, Retirement Dates on Record

**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows R12, R17, D7, D8 and §7.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), any wave.
**Commit:** `ci: secrets-expiry check and inventory; restore-drill record (BITB-305)`

## Problem

The project has one maintainer and several things that stop working on a date nobody
has written down:

- `RELEASE_PLEASE_TOKEN` is a fine-grained PAT with a maximum lifetime of one year;
  `AUTO_UPDATE_PR_TOKEN` falls back to it. `docs/RELEASE_PROCESS.md:382-400` lists "PAT
  expired" as a known failure but records no expiry date and no owner. When it lapses,
  release PRs, the Play upload that the tag triggers, and PR auto-update all stop.
- The Azure service principal, the Play service-account key, the Cloudflare Turnstile
  secret, the probe secrets and the LLM/embedding keys have no inventory either.
- The commercial-cloud retirement date of the Azure embedding model is not on record. A
  forced change means re-embedding 403,856 verses.
- Backups are 7 days, single region (`deployment/main.tf:425-426`), and there is no
  record that a restore has ever been performed. Making the database private is already
  BITB-005 and is **not** part of this story.
- `deployment/terraform.tfvars:136-137` enables a budget alert; whether the resource
  exists in Azure has not been confirmed.

Most of this needs the owner's access. The story is split so a builder can do its part
without any secret.

## Decisions already made

1. **The inventory is a YAML file, not prose:** `docs/secrets-inventory.yaml`, one entry
   per credential — `name`, `kind`, `used_by` (workflow or service), `expires`
   (`YYYY-MM-DD` or `never`), `rotation_doc` (path#anchor), `owner`. **Names and dates
   only; never a value, never a token prefix.**
2. **One weekly workflow checks it:** fails when any `expires` is within 21 days or
   past, and when an entry has `expires: unknown`.
3. **GitHub tokens are also checked live.** GitHub returns the header
   `github-authentication-token-expiration` on authenticated API calls made with an
   expiring PAT; the workflow calls `GET /user` with each PAT secret, compares the header
   with the inventory and fails on a mismatch or a date inside 21 days. The token value
   is never printed.
4. **The restore drill is a recorded, timed exercise**, not automation: point-in-time
   restore to a temporary server, a row-count comparison, deletion of the temporary
   server.
5. **No Terraform changes to backups in this story.** Read the Azure documentation for
   whether geo-redundant backup can be enabled on an existing Flexible Server before
   proposing anything; record the answer here and file a follow-up if it can.

## Requirements — builder (no secrets needed)

1. `docs/secrets-inventory.yaml` listing every secret referenced by
   `.github/workflows/*.yml` (`grep -ho "secrets\.[A-Z0-9_]*" .github/workflows/*.yml | sort -u`)
   and every secret Terraform injects (`deployment/main.tf`, `deployment/variables.tf`
   sensitive variables). Set `expires: unknown` for all — the owner fills them in.
2. `scripts/check_secrets_inventory.py` (stdlib + PyYAML if already a dependency;
   otherwise parse the simple structure by hand): validates the schema; exit 1 on
   expired/expiring/unknown; `--allow-unknown` flag for the first weeks; a
   `--completeness` mode that fails when a `secrets.NAME` used in a workflow is missing
   from the inventory.
3. Unit tests for the script (dates around the 21-day boundary, unknown, malformed,
   missing entry, completeness).
4. `.github/workflows/secrets-expiry-check.yml`: weekly cron (not minute 0 or 30) +
   `workflow_dispatch`; runs the script, then the live header check for
   `RELEASE_PLEASE_TOKEN` and `AUTO_UPDATE_PR_TOKEN` (skip a secret that is unset; mask
   everything). Add the completeness mode to the PR workflow so a new secret cannot be
   introduced without an inventory entry.
5. `docs/HOW-TO-BACKUP-RESTORE-DATABASE.md`: add a "Restore drill" section with the
   exact steps and a "Drill log" table (date, restore point, minutes to restore, row
   counts matched, performed by). Read the existing document first and reuse its
   commands.
6. `docs/RELEASE_PROCESS.md`: link the inventory from the PAT section.
7. A "Dates to watch" table in `docs/secrets-inventory.yaml`'s header comment or a short
   `docs/DATES_TO_WATCH.md`: embedding-model retirement, Google Play target-API
   deadline, Node 22 end of life (2027-04-30), Python 3.12 end of life (2028-10-31),
   PostgreSQL 16 end of life (2028-11-09) — the three end-of-life dates are from
   endoflife.date on 2026-11-11; leave the first two as `unknown` for the owner.

## Owner steps (unticked until done by the owner)

- [ ] Fill in `expires` and `owner` for every inventory entry; remove `--allow-unknown`
      from the workflow
- [ ] Add a second person with admin rights on the GitHub repository, the Azure
      subscription and the Play Console, or record here that the risk is accepted
- [ ] Run the restore drill once and fill in the first row of the drill log
- [ ] Run `terraform state list | grep -i budget` and record whether the budget alert
      exists
- [ ] Look up the retirement date of the deployed embedding model on the Azure OpenAI
      model-retirements page and record it in "Dates to watch"
- [ ] Record the Google Play target-API deadline for 2027

## Tests (minimum)

Requirement 3, plus a test that the committed inventory passes `--completeness` against
the committed workflows.

## Acceptance criteria

- [ ] Every secret used by a workflow or injected by Terraform has an inventory entry
- [ ] The weekly check exists and fails 21 days before any recorded expiry
- [ ] No secret value, prefix or hash appears in the repository or in workflow logs
- [ ] The restore-drill procedure and log table exist
- [ ] Owner steps above are listed and left for the owner

## Out of scope

- Private networking for the database (BITB-005).
- Automatic secret rotation.
- Geo-redundant backup (decision 5).

## Related

BITB-005, BITB-150, BITB-165, `docs/RELEASE_PROCESS.md`.
