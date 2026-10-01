# BITB-125: `scripts/migrations/utils.py` Silently Drops TLS Entirely for `?ssl=verify-ca`/`?ssl=verify-full`

**Status:** 🎯 Todo
**Priority:** P2 — latent, not currently triggered by any DSN in this repo, but a real correctness gap
**Size:** S
**Created:** 2026-09-09
**Prompted by:** the independent Verify pass on BITB-099

## The Finding

`scripts/migrations/utils.py::get_migration_connection_params()` and
`api/scripture/database.py::get_async_database_url()` are documented as mirrors of each other, but
they diverge on the asyncpg-spelling (`?ssl=...`, as opposed to the libpq-spelling `?sslmode=...`)
query parameter:

```python
# scripts/migrations/utils.py
if sslmode in ("require", "verify-ca", "verify-full") or ssl_param == "require":
    ssl_context = ssl.create_default_context()
    if sslmode == "require" or ssl_param == "require":
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    conn_kwargs["ssl"] = ssl_context
```

`ssl_param` (the value of `?ssl=...`) is only ever checked against `"require"`. A DSN spelled
`?ssl=verify-ca` or `?ssl=verify-full` makes the top `if` condition false (`sslmode` is `None`, and
`ssl_param == "require"` is false), so **no `ssl` key is added to `conn_kwargs` at all** — asyncpg
then connects with no TLS configuration, i.e. **plaintext**, not merely unverified. This is a worse
outcome than `sslmode=require`'s `CERT_NONE`, not a smaller one.

`api/scripture/database.py::get_async_database_url()` does not have this gap — it does
`sslmode = sslmode or ssl_param` before branching, so `?ssl=verify-full` and `?sslmode=verify-full`
behave identically there.

## Why It's Latent, Not Active

No DSN anywhere in this repo currently uses the `?ssl=verify-ca`/`?ssl=verify-full` spelling — every
production caller was moved to `?sslmode=verify-full` by BITB-099. But
`docs/MIGRATION_GUIDELINES.md`'s Rule #1 example now shows `?ssl=verify-full` as the **"WRONG"**
example (illustrating the asyncpg param-name rejection, not the mode value) immediately next to
prose about `verify-full` being the correct mode — an operator skimming that page and constructing
a DSN by hand could plausibly type `?ssl=verify-full`, expecting either a clear failure (like the
`ssl=require` case this rule documents) or working verification, and instead get a connection that
silently drops TLS entirely with no error.

## Acceptance Criteria

- [ ] `get_migration_connection_params()` matches `get_async_database_url()`'s handling: normalize
      `sslmode = sslmode or ssl_param` (or equivalent) before branching, so `?ssl=verify-ca` and
      `?ssl=verify-full` build the same verified `SSLContext` as their `sslmode=` spelling
- [ ] A regression test asserting `?ssl=verify-full` (and `?ssl=verify-ca`) produce
      `verify_mode=CERT_REQUIRED`/`check_hostname=True`, not a missing `ssl` kwarg
- [ ] A regression test asserting the *absence* of any DSN that would hit this gap and connect
      fully unencrypted (i.e. that `conn_kwargs` never lacks an `ssl` key when the caller asked for
      any of `require`/`verify-ca`/`verify-full` in either spelling)

## Related

- BITB-099 — moved every real DSN in this repo to `sslmode=verify-full`; this story is the
  divergence its Verify pass found between the two "mirror" helpers, filed as a separate follow-up
  rather than folded into that PR (unrelated to its DSN-value scope)
- BITB-016 — introduced the asyncpg `ssl`-vs-`sslmode` parameter-name distinction this bug hides in
- `scripts/migrations/utils.py`, `api/scripture/database.py`, `docs/MIGRATION_GUIDELINES.md`
