# BITB-156: Android Server-Driven Session Limit + BITB-118 Instrumentation/IP-Cap Follow-Up

**Status:** 🚧 In Progress (PR #1103 open — Part A: Android server-driven limit + "Continue this
conversation". Parts B/C/D — instrumentation, IP-cap prerequisites, purge-horizon — remain
deferred/unstarted.)

**Priority:** P2

**Size:** M

**Created:** 2026-09-16

**Split from:** BITB-118 — the backend + web slice of that story shipped first (server-published
`chat.session_max_requests`, a non-destructive "Continue this conversation" action, and
ICU-interpolated locale copy on web); this story is everything BITB-118 scoped that the web PR
deliberately left out, so each PR stays reviewable.

**Related:** BITB-118 (parent story, full context and rationale), BITB-024 (built the original
10-message limit + "Start New Session" reset), BITB-061 (moved the counter into Postgres)

---

## Why this is split out, not just "the rest of BITB-118"

BITB-118's acceptance criteria bundle four genuinely different kinds of work:

1. A client-side UX fix (non-destructive "continue") — safely shippable in one PR, no production
   access needed. **Shipped for web** in the BITB-118 PR.
2. The same UX fix, on a second platform (Android) — same pattern, different codebase, its own
   review surface. **This story.**
3. Privacy-reviewed production instrumentation, deployed and observed over a real window, before
   any default-value or IP-cap decision is made. This cannot be "finished" inside a single
   autonomous PR — it requires a live deploy and a waiting period for the data to accumulate.
   **This story tracks it, does not attempt to complete it in one sitting.**
4. A production-Terraform/Postgres-migration change (the idle-purge-horizon mismatch) that touches
   infrastructure this development environment cannot safely apply or verify against a real
   cluster. **This story tracks it as a named follow-up, not a code diff to write blind.**

Filing all four as one open-ended story made it easy to either attempt too much in one PR or
avoid starting at all. Splitting keeps the Android port genuinely completable while keeping the
production-dependent work visible instead of silently dropped.

---

## Part A — Android UX parity (completable without production access)

Mirrors the web implementation, file for file:

| Web (shipped) | Android (this story) |
|---|---|
| `useServerConfig()` fetches `chat.session_max_requests` from `GET /config`, falls back to `MAX_SESSION_REQUESTS = 10` | Same fetch, same fallback value, needs its own Android-side config client (check whether one already exists for `max_message_length` parity — Android already reads that field, per the BITB-075 precedent, so the wiring should already exist to extend) |
| `Chat.sessionLimitMessage` interpolates `{max}` in all 11 `frontend/messages/*.json` | `error_session_limit` becomes a `%1$d` format string in `android/app/src/main/res/values/strings.xml:199` and all 11 `values-*/strings.xml` copies |
| `handleContinueConversation()` in `ChatIsland.tsx`: rotates `session_id` only, does not touch `messages`/`conversationId`/etc. | A new `continueConversation()` in `ChatViewModel.kt` alongside the existing `startNewConversation()` (~line 778-799): rotate the persisted session id via `sessionPreferences`, reset `isSessionLimitReached`, but leave `messages` and `currentConversationId` untouched |
| Primary "Continue" button + secondary "Start New Session" button in `ChatIsland.tsx` (~line 1186) | Same pairing in `ChatScreen.kt` (~line 488-495), wired to the new `continueConversation()` |
| `const val MAX_INTERACTIONS = 10` still exists as the fail-open fallback in `frontend/src/lib/api.ts` | `ChatViewModel.kt:171`'s `MAX_INTERACTIONS` becomes the fallback used until `/config` resolves, used at its existing call sites (~316, ~590) |

**Acceptance Criteria (Part A):**

- [ ] `MAX_INTERACTIONS` in `ChatViewModel.kt` is fed from server config; no locale's
      `strings.xml` contains a literal "10" for `error_session_limit`
- [ ] A "Continue this conversation" action exists in `ChatScreen.kt` / `ChatViewModel.kt`,
      preserves `messages` and `currentConversationId`, and the next message succeeds (200)
- [ ] "Start New Session" / `startNewConversation()` is unchanged (regression guard)
- [ ] New Robolectric/unit tests mirroring the web suite: continue keeps messages, start-new
      clears them, the interpolated string renders the server (or fallback) value

---

## Part B — Instrumentation (blocked on a production deploy + observation window)

Carried over verbatim from BITB-118's "Measure before choosing the number" section: add
privacy-reviewed, documented event definitions for sessions reaching the threshold, "Start fresh"
vs. "Continue" selection, post-threshold message depth, repeat thresholds, and the distribution of
distinct sessions per trusted client IP — then deploy, validate the events actually arrive in
production, and only then record an observation window with sample size and percentiles.

**This cannot be completed by an autonomous coding session in one pass** — it requires the
instrumentation to be live in production for a real window before there is anything to record. The
acceptance criterion below is written to reflect that: implementing the instrumentation is
completable now; the observation and decision are not.

**Acceptance Criteria (Part B):**

- [ ] Instrumentation code + dashboard/query exist and are deployed
- [ ] Events verified arriving in production (not just passing in a test)
- [ ] An observation window is recorded here with sample size and percentiles before any threshold
      or IP-cap decision is made from it

---

## Part C — Trusted-ingress + shared-IP/NAT prerequisites for any future IP cap

BITB-118 was explicit that a per-IP daily cap must not ship before (a) forwarded-IP headers
(`X-Forwarded-For`/`X-Real-IP`) are trusted only from the known production ingress, with
direct-spoof and multi-proxy tests, and (b) shared-IP/NAT exposure (carrier-grade NAT, households,
schools, churches, VPNs) is measured so the cap doesn't collectively block unrelated legitimate
users. Neither prerequisite is attempted here.

**Acceptance Criteria (Part C):**

- [ ] Trusted-proxy chain documented and tested (direct-spoof + multi-proxy cases)
- [ ] Shared-IP/NAT measurement reviewed and referenced before any IP-cap proposal
- [ ] No per-IP daily cap is implemented until both of the above are satisfied

---

## Part D — Idle-purge horizon mismatch

`scripts/migrations/010_schedule_rate_limit_purge.sql` runs an hourly `pg_cron` job with a
**hardcoded** `interval '1 hour'`, independent of the `rate_limit_session_ttl_seconds` setting the
in-memory backend actually honors. Production Postgres counters therefore survive until the first
purge after an idle hour, regardless of what the config setting says.

**Acceptance Criteria (Part D):**

- [ ] Either the Postgres purge horizon reads `rate_limit_session_ttl_seconds`, or the fixed
      one-hour horizon is explicitly documented as intentional (not merely inherited from the
      in-memory backend's default) with a boundary test locking in the current behavior

---

## Out of Scope

Same exclusions as the parent story BITB-118: accounts/sign-in/paid tiers, removing the reflective
nudge, per-user threshold personalization, reworking the per-minute IP/session windows, and iOS
(BITB-087, which inherits whatever ships here and in BITB-118).
