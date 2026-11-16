# How to Export Feedback and Contact Messages

Users can rate an answer (thumbs up/down, with an optional reason and comment) and can
write to us through the contact form. The text they wrote is stored in the database for a
limited time, but the **notification e-mails do not contain it** (BITB-329): they carry
identifiers only and tell you which command to run. This doc is that command's manual.

See also: [`scripts/export_feedback.py`](../scripts/export_feedback.py),
[`api/feedback/retention.py`](../api/feedback/retention.py),
[`api/feedback/models.py`](../api/feedback/models.py), the public
[Privacy Policy](../frontend/public/legal/privacy-policy.md) and the sibling how-to
[HOW-TO-EXPORT-BLOCKED-SAMPLES.md](HOW-TO-EXPORT-BLOCKED-SAMPLES.md).

## Quick start (copy-paste)

The owner ran this sequence against production on 2026-11-16 (then with `DB_USER=bibleadmin PG_DB=bibleapp` and `PGSSLROOTCERT=system` set by hand; the script now does both itself). No `DB_USER` / `PG_DB` overrides are needed:
`make db-server-url` takes the user and database from `deployment/terraform.tfvars`
(`db_admin_username` = `bibleadmin`, `db_name` = `bibleapp`); override them with
`DB_USER=... PG_DB=... make -s db-server-url SERVER=...` only for a differently named server.

```bash
make az-pg-add-ip
export PGPASSWORD='<database admin password>'   # the Terraform db_admin_password / TF_VAR_DB_ADMIN_PASSWORD secret
export DATABASE_URL="$(make -s db-server-url SERVER=bible-app-db-mb0172)"
make export-feedback ARGS="--message-id <uuid>"          # or --contacts --id <n>, or --since/--until
make az-pg-remove-ip RULE=bible-app-db-mb0172
```

### Prerequisites

- `az login` done and the right subscription selected (`az account show`); read access to
  resource group `bible-app-rg` (`az-pg-add-ip` and `db-server-url` call `az postgres flexible-server`;
  adding the firewall rule needs Contributor on the server).
- `make` and the Python environment: `make setup-dev`, or just run `make export-feedback`, whose
  `install-deps` step creates the venv.
- The database admin password (`PGPASSWORD`).
- Certificates: the exporter adds `sslrootcert=system` itself (OS trust store). For `pg_dump`/`psql`
  (`make db-backup`) the script sets `PGSSLROOTCERT=system` automatically on libpq >= 16 when
  `~/.postgresql/root.crt` is absent.

One-time setup for libpq older than 16 (`pg_dump --version`): install the Azure root CAs.

```bash
mkdir -p ~/.postgresql
curl -fsSL https://cacerts.digicert.com/DigiCertGlobalRootG2.crt.pem > ~/.postgresql/root.crt
curl -fsSL 'https://www.microsoft.com/pkiops/certs/Microsoft%20RSA%20Root%20Certificate%20Authority%202017.crt' \
  | openssl x509 -inform DER >> ~/.postgresql/root.crt
```

## What is stored, and for how long

| Data | Table / columns | Kept |
| ---- | --------------- | ---- |
| The user's question, the AI reply, the optional comment | `feedback.user_message`, `assistant_response`, `comment` | **30 days**, then set to `NULL` (`FEEDBACK_TEXT_RETENTION_DAYS`) |
| Rating, reason, message id, verses, model, timing, session hash | rest of the `feedback` row | **90 days**, then the row is deleted (`FEEDBACK_RETENTION_DAYS`) |
| Contact form: subject, message, optional reply e-mail, status, session hash | `contact_submissions` | **90 days**, then deleted (`CONTACT_RETENTION_DAYS`) |

- Ages count from `created_at`. Nothing ever refreshes it, so retention cannot be extended.
- The API deletes/clears expired data in an hourly sweep (and once at startup). Until the next
  sweep a row can still exist past its limit, so the exporter also filters on age: it never
  returns a row past its row window and never returns feedback text past 30 days.
- The session id is stored only as a one-way SHA-256 hash (the same function as the
  blocked-message samples). The contact form's user agent is not stored at all.
- Once the text is gone it cannot be recovered. **Export anything worth keeping before the
  date printed in the notification e-mail** ("Text available until ...").

## The notification e-mails

The e-mail for a feedback item contains: rating, reason, message id, model, response time,
verse references, whether a comment was left (yes/no) and the timestamp. A contact e-mail
contains: subject, submission id, whether a reply address was left (yes/no) and the timestamp.
Neither contains message text, AI replies, comments or the sender's address, and neither sets
a `Reply-To`. Each ends with a "How to read the full text" block with the commands below,
already filled in for that item, plus the date the text is deleted.

## Reading the full text

The production Postgres firewall only admits allow-listed IPs, so allow yours first and
remove the rule afterwards. Prerequisites: the Azure CLI (`az login` done), `make` and the
repository's Python environment (`make export-feedback` installs it), and the database admin
password (see the Quick start above for details and certificate behaviour). Set
`PGSSLROOTCERT` to use a different CA file.

```bash
make az-pg-add-ip
export PGPASSWORD='<database admin password>'
export DATABASE_URL="$(make -s db-server-url SERVER=<server>)"
make export-feedback ARGS="--message-id <uuid>"      # a feedback item
make export-feedback ARGS="--contacts --id <n>"      # a contact submission
make az-pg-remove-ip RULE=<server>
```

- `<server>` is the production server name, e.g. `bible-app-db-mb0172` (the notification
  e-mail has it filled in; otherwise run `make az-pg-list-rules`, or check
  `deployment/terraform.tfvars`).
- `make az-pg-add-ip` names the firewall rule after the server, so the rule to remove is the
  server name. Check with `make az-pg-list-rules`.
- `make db-server-url` prints a URL **without** a password; `PGPASSWORD` supplies it.

### More selectors

```bash
# Latest negative feedback since 1 November, as CSV to a file
make export-feedback ARGS="--rating negative --since 2026-11-01 --format csv --output negative.csv"

# One feedback row by its database id
make export-feedback ARGS="--id 123"

# Contact messages about bugs
make export-feedback ARGS="--contacts --subject bug --limit 20"
```

### Directly

```bash
DATABASE_URL=postgresql://... python scripts/export_feedback.py --help
```

| Flag | Meaning |
| ---- | ------- |
| `--message-id <uuid>` | Feedback only: the chat message id (in the e-mail). |
| `--id <n>` | Row id: `feedback.id`, or the contact id with `--contacts`. |
| `--contacts` | Export contact submissions instead of feedback. |
| `--rating positive\|negative` | Feedback only. |
| `--subject spiritual\|bug\|feature\|feedback\|other` | Contacts only. |
| `--since YYYY-MM-DD` / `--until YYYY-MM-DD` | Inclusive lower / exclusive upper bound on `created_at`. |
| `--limit N` | Maximum rows. |
| `--format json\|csv` | Output format (default JSON). |
| `--output FILE` | Write to a file instead of stdout. |

The exporter is read-only (`SELECT` only).

## Troubleshooting

| Error | Cause and fix |
| ----- | ------------- |
| `root certificate file ".../.postgresql/root.crt" does not exist` | libpq has no CA file for `sslmode=verify-full`. `export PGSSLROOTCERT=system` (libpq >= 16; `make db-*` does it for you), or do the one-time `root.crt` install above. |
| `FATAL: password authentication failed for user "bible"` | Old default user. Update to a branch with this fix, or pass `DB_USER=bibleadmin PG_DB=bibleapp` to `make -s db-server-url`; also check `PGPASSWORD` is the admin password. |
| Connection timeout / hangs | Your IP is not on the firewall: `make az-pg-add-ip` (your IP may have changed; list with `make az-pg-list-rules`). |

## Answering a privacy request

Feedback and contact data can be found and deleted on request. Users cannot see a message id,
so ask for the approximate date and time the feedback was sent (or the e-mail address used for a
contact submission). Find the row by time window with the exporter (`--since` / `--until`, UTC,
`--until` exclusive), confirm it with the requester, then delete it from a database client:

```bash
make export-feedback ARGS="--since 2026-11-16T10:00 --until 2026-11-16T11:00"   # rows in that hour
```

```sql
DELETE FROM feedback WHERE message_id = '<uuid>';          -- or: WHERE id = <n>
DELETE FROM feedback WHERE created_at >= '2026-11-16 10:00+00'
                       AND created_at <  '2026-11-16 11:00+00';  -- only if exactly the rows found
DELETE FROM contact_submissions WHERE id = <n>;
```

## Changing the retention

The numbers are quoted in the privacy policy (11 languages), and a test ties them to the
defaults. Changing `FEEDBACK_TEXT_RETENTION_DAYS`, `FEEDBACK_RETENTION_DAYS` or
`CONTACT_RETENTION_DAYS` therefore also needs a policy update. The settings are validated:
`1 <= FEEDBACK_TEXT_RETENTION_DAYS <= FEEDBACK_RETENTION_DAYS <= 3650`, and
`1 <= CONTACT_RETENTION_DAYS <= 3650`.
