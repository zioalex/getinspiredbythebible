# BITB-112: Every Database URL in This Repo Assumes the Password Is URL-Safe

**Status:** 🚧 In Progress — all nine sites (eight in `azure-deploy.yml`, one in `main.tf`) now
percent-encode the password, `administrator_password` is left literal on purpose (commented at both
sites), and a guard test (`api/tests/test_azure_deploy_workflow_credentials.py`) fails on a future
raw-password DSN. The one AC this PR cannot close is the live rehearsal — see *Verification* below.
**Priority:** P1 — the same defect already took `eval-prod` down once, and one of the remaining
sites is the running production app's own connection string
**Size:** S–M (mechanical fix at ~10 sites + a charset guard + tests; the care is in not breaking a
working deploy while changing how its credential is encoded)
**Created:** 2026-08-28
**Prompted by:** BITB-101's first non-skipped `eval-prod` run
([33212723774](https://github.com/zioalex/getinspiredbythebible/actions/runs/33212723774)), which
died at import in 1.5s because `search_eval_ro`'s password was interpolated into a DSN raw. Fixed
for that one job in PR #1020; this story is the rest of the sites.

## User Story

**As** the operator of a production service, **I want** every database URL this repo builds to
survive whatever characters are in the password, **so that** rotating a credential — the thing you
do *during* a security incident — does not take the API down or block the deploy that is meant to
fix it.

## Problem

A Postgres DSN is a URL. `postgresql://user:password@host:5432/db` only means what it looks like if <!-- pragma: allowlist secret -->
the password contains no character that is structural in a URL. Any of `:/?#[]@%&` silently changes
what the URL names — it does not error, it points somewhere else:

| password | host the URL actually names |
| --- | --- |
| `plainAlnum123` | `db.example.com` ✅ |
| `p@ss/w0rd#x` | `ss` ❌ |
| `a%b:c?d[e]f&g` | `search_eval_ro`, with the rest becoming the query string ❌ |
| `Str0ng!Pass+With/Slash=` | `search_eval_ro` ❌ |

This is not hypothetical here. It is exactly what happened to `eval-prod` on 2026-08-28: the job
exited 1 after 1.5 seconds — too fast for any network round-trip — because
`api/scripture/database.py` calls `create_async_engine()` at module scope, so the malformed URL was
parsed at *import*, before a single query. PR #1020 percent-encodes that one DSN. Every other site
still interpolates raw:

| site | what it feeds | blast radius if the password is not URL-safe |
| --- | --- | --- |
| `deployment/main.tf:93` | the **running app's** `DATABASE_URL` container env var | the API cannot reach its database — a production outage, not a CI failure |
| `.github/workflows/azure-deploy.yml` (×7) | Alembic migrations, seeding, `verse_topics` population, drift checks | the deploy fails, including the deploy you would be running to *fix* the credential |
| `.github/workflows/search-eval-full.yml` | `eval-prod` | fixed in PR #1020 |

`deployment/main.tf:390` hands the same value to
`azurerm_postgresql_flexible_server.administrator_password`, which takes it **literally**. So the
server is configured with the raw password while the app is handed a percent-decoded misreading of
it: the two disagree precisely when the password is interesting. `deployment/variables.tf:69-76`
validates only `length >= 8` — nothing constrains the character set today.

Why it has not bitten yet: the current admin password happens to be URL-safe. That is a property of
one generated value, not of the system, and nothing anywhere records that the property is
load-bearing. The next rotation is the trigger — and rotations are most likely during incident
response, which is the worst possible moment to discover that the deploy path is broken.

## Proposed Approach

1. **Encode at every boundary that builds a URL.** In workflow shell, the same treatment PR #1020
   applied: `urllib.parse.quote(..., safe="")` on the password before interpolation, plus
   `::add-mask::` on the encoded form (GitHub masks the secret's literal value, not its encoded
   variant — they are different strings). In Terraform, `urlencode(var.db_admin_password)` at
   `main.tf:93` only; **not** at `main.tf:390`, where the server wants the literal value. That
   asymmetry is the whole point and deserves a comment at both sites.

2. **Add a charset guard as belt-and-braces**, not as the fix: a `validation` block on
   `db_admin_password` that rejects the structural characters outright, or (better, since it
   constrains nothing a generator must obey) a comment plus the encoding above. Decide which —
   encoding alone is sufficient and strictly more general; a validation rule additionally stops a
   human from pasting something that will confuse a `psql` invocation elsewhere.

3. **Consider removing the URL assembly entirely where possible.** `PGPASSWORD` + discrete
   `PGHOST`/`PGUSER`/`PGDATABASE` env vars have no encoding problem at all. This is the real fix for
   the `psql`-based steps; the SQLAlchemy ones need a URL, so they need encoding.

4. **Guard it with a test in the style of `api/tests/test_search_eval_workflow_credentials.py`**,
   which already asserts this property for `search-eval-full.yml`: parse the workflow files and
   assert no `DATABASE_URL=` line interpolates a bare password variable. A `terraform validate` /
   plan-level assertion for `main.tf:93` if one is cheap; otherwise a grep-shaped test.

## Acceptance Criteria

- [x] No `DATABASE_URL` anywhere in `.github/workflows/` interpolates an unencoded password — all
      eight sites in `azure-deploy.yml` (legacy migrations, Alembic migrations, two Translation
      Status checks, Load Bible Data, Populate Verse Topics, Verse Topic Coverage Check, Generate
      Embeddings) now compute `DB_PASS_ENC` via `urllib.parse.quote(..., safe="")`, `::add-mask::`
      it, and interpolate `DB_PASS_ENC` instead of `DB_PASS`
- [x] `deployment/main.tf:93` (now inside the `DATABASE_URL` env-var block) percent-encodes the
      password via `urlencode(var.db_admin_password)`; `administrator_password` provably still
      passes the literal value, with a comment at both sites explaining why they differ
- [x] A test fails if a future edit reintroduces a raw-password DSN in any workflow —
      `api/tests/test_azure_deploy_workflow_credentials.py`, parsing every `run:` step in
      `azure-deploy.yml` plus a text check on `main.tf`'s two sites
- [x] Decision recorded (see *Decision* below): no charset `validation` block; no `psql` steps to
      move — none of these sites shell out to `psql` in the first place
- [ ] Rehearsed, not assumed: a deploy (or at minimum the migration job) runs green against a
      password containing `@`, `/`, and `#` — **left open**, see *Verification*

## Decision

**No charset `validation` block on `db_admin_password`.** Per the story's own reasoning: encoding
is strictly more general than a character-set restriction, and every site that builds a URL from
the password now encodes it. A validation block would only add a constraint a generator must obey
for zero additional safety.

**No `psql` steps to move to `PGPASSWORD`.** All nine DSN sites this story touches feed a Python
process (`asyncpg`/SQLAlchemy via `scripts/*.py`, `alembic`, or Terraform's own `DATABASE_URL` env
var) — none of them shell out to `psql` directly, so there is no URL-vs-`PGPASSWORD` choice to make
at these sites. The one script in the repo that *does* call `psql` directly,
`scripts/db-backup-restore.sh`, already uses `PGPASSWORD` and documents why (`PGPASSWORD for the
password rather than putting it in the URL`) — this story's fix keeps that split (URL sites encode;
the one `psql` site stays on `PGPASSWORD`) rather than converging on one form everywhere.

## Verification

The failure mode is silent misdirection rather than an error, so inspection is weak evidence here:
a raw-interpolation site looks correct and works fine right up until the day it doesn't. The proof
is a rehearsal against a password containing the structural characters — ideally against a restored
copy or a scratch Flexible Server instance, not production.

A cheap intermediate check, run locally against the encoding logic these sites now share:

```
$ python3 -c "
from urllib.parse import quote, urlparse
pw = quote('Str0ng!Pass+With/Slash=@#', safe='')
url = f'postgresql://user:{pw}@db.example.com:5432/bibleapp?sslmode=require'
print(urlparse(url).hostname, urlparse(url).password)
"
db.example.com Str0ng!Pass+With/Slash=@#
```

confirms the encode/decode round-trips correctly for a password containing every structural
character called out above. **This is not the same as the AC's rehearsal**, which requires an
actual deploy or migration run against Azure with a password of this shape — that needs production
credentials and a live Container Apps / Flexible Server environment this session does not have
access to. Left as the one open item, in the same shape as BITB-097's "clear the stranded gate
runs" AC: real, but an operator action rather than a code change. Recorded here so the next session
picking up this story (or the operator during a credential rotation) knows exactly what proof is
still missing.

## Related

- **BITB-101** — the story whose `eval-prod` job hit this first; PR #1020 fixed that one site and
  filed this for the rest
- **BITB-099** — production Postgres connections encrypt but do not verify the server; same
  connection path, a different weakness in it
- **BITB-097 / BITB-100** — the "bound the database from the database, and make the rule checkable"
  precedent this story's guard test follows
- `deployment/main.tf`, `deployment/variables.tf`, `.github/workflows/azure-deploy.yml`,
  `api/tests/test_search_eval_workflow_credentials.py`
