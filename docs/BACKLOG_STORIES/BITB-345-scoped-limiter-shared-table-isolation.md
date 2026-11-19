---
id: BITB-345
status: todo
priority: P2
size: S
created: 2026-11-19
depends_on: [BITB-298, BITB-310]
---

# BITB-345: Scoped Rate-Limit Buckets Are Never Tested Against the Shared `rate_limit_hits` Table

**Prompted by:** BITB-310 verification (finding 1).

## Problem

`require_ip_rate_limit` (`api/utils/security.py`) separates its six scopes — `search`,
`feedback`, `contact`, `church`, `chat_finalize`, `telemetry` — purely by the key it builds:
`check_rate_limit(f"{scope}:{ip_address}")`. Under the production `postgres` backend **every**
scoped limiter writes to the same `rate_limit_hits` table, so that prefix is the only thing
keeping one scope's traffic out of another scope's budget (and out of the chat IP bucket,
whose key is the bare IP).

Every existing test runs with `rate_limit_backend="memory"`, where
`get_scoped_rate_limiter` (`api/utils/rate_limiter.py`) hands each `(scope, per_minute)` pair
its own `RateLimiter` with its own `InMemoryStore`. Isolation therefore holds **by
construction** in tests, whatever the key looks like. A test that exhausts one scope and then
checks another scope still has budget proves nothing on the backend that actually matters.

BITB-310 closed the narrow version of this gap with a key-shape assertion
(`test_telemetry_bucket_is_scope_prefixed_and_leaves_chat_alone` in
`api/tests/test_client_errors.py`, which fails if the `f"{scope}:"` prefix is dropped). That
pins one scope's key format; it does not prove end-to-end isolation under a shared table, and
the other five scopes have no equivalent assertion.

## Requirements

1. An integration test, against a real PostgreSQL (the marker/fixture the existing
   `rate_limit_backend="postgres"` integration tests use), that exhausts one scope's bucket for
   an IP and asserts that **(a)** every other scope and **(b)** the chat IP bucket for the same
   IP still allow requests.
2. Parametrize it over all scopes registered via `require_ip_rate_limit`, so a newly added
   scope is covered without a new test.
3. Assert the stored key shape once (`ip:<scope>:<ip>` as `PostgresStore.check_and_record`
   writes it) so a future refactor of the key cannot silently merge buckets.

## Tests

The deliverable *is* tests; they must fail if the `f"{scope}:"` prefix is removed from
`api/utils/security.py`.

## Acceptance criteria

- [ ] Cross-scope isolation asserted against the `postgres` backend, not only `memory`
- [ ] Parametrized over every scope passed to `require_ip_rate_limit`
- [ ] Removing the scope prefix fails the new test

## Related

BITB-298 (introduced `require_ip_rate_limit` and the gap), BITB-310 (telemetry scope + the
narrow key assertion).
