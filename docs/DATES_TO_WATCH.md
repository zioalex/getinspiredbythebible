# Dates to watch

Deadlines that stop something working (or leave it unsupported) on a date nobody otherwise
tracks (BITB-305). Credential expiry dates live in
[`secrets-inventory.yaml`](secrets-inventory.yaml) and are checked weekly by
`.github/workflows/secrets-expiry-check.yml`.

| Item | Date | Source | Notes |
| ---- | ---- | ------ | ----- |
| Azure embedding model retirement | `unknown` | Azure OpenAI model-retirements page | Owner: look up the deployed model. A forced change means re-embedding all verses. |
| Google Play target-API deadline | `unknown` | Play Console / Android developer docs | Owner: record the 2027 deadline. |
| Node.js 22 end of life | 2027-04-30 | endoflife.date, checked 2026-11-11 | Frontend CI matrix is 22.x + 26.x. |
| Python 3.12 end of life | 2028-10-31 | endoflife.date, checked 2026-11-11 | Backend runtime. |
| PostgreSQL 16 end of life | 2028-11-09 | endoflife.date, checked 2026-11-11 | Azure Flexible Server major version. |

## Secret rotation

There is no per-secret rotation runbook yet. The release PAT is covered in
[`RELEASE_PROCESS.md`](RELEASE_PROCESS.md#pat-requirement--release_please_token). For every
other credential, the owner records the rotation steps here as they are worked out, and points the
entry's `rotation_doc` in the inventory at the new section.
