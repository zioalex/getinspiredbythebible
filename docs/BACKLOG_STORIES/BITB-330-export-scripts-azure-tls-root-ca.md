---
id: BITB-330
status: in-review
priority: P1
size: S
created: 2026-11-17
---

# BITB-330: Export scripts fail with "certificate verify failed" against Azure Postgres

**Bug.** Running the commands from the feedback notification e-mail
(`make export-feedback ...` with the `DATABASE_URL` from `make db-server-url`) fails with
`SSL error: certificate verify failed`. The exporters defaulted to `sslrootcert=system`; the OS
store often lacks `Microsoft RSA Root Certificate Authority 2017` (the Azure chain since the 2026
rotation) and `psycopg2-binary`'s bundled OpenSSL may not read the OS store at all.

**Fix.** `scripts/pg_tls.py` supplies an explicit CA bundle (certifi, which has DigiCert Global
Root G2, plus the vendored `scripts/certs/microsoft-rsa-root-2017.pem`) to `export_feedback.py`,
`export_blocked_samples.py` and `export_retrieval_misses.py`. An existing `~/.postgresql/root.crt`
is left to libpq; `PGSSLROOTCERT` / explicit `sslrootcert` still win. The e-mailed commands now work
as pasted.

## Acceptance criteria

- [x] verify-full/verify-ca URLs default to a CA file containing both Azure roots (all 3 exporters).
- [x] Regression tests in `api/tests/test_export_feedback.py` (`TestSslRootCert`).
- [ ] Owner step: rerun the e-mail's commands against production and confirm the export connects
      (not testable from CI; no production credentials).
