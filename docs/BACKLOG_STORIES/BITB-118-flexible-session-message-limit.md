# BITB-118: Make the Session Message Limit Flexible (Users Say 10 Is Too Few)

**Status:** 🎯 Todo

**Priority:** P2 — real user complaints, but the current limit is soft (users *can* continue),
so nobody is fully blocked

**Size:** M (1–2 days: backend config + web + Android + i18n across 11 locales)

**Created:** 2026-09-04

**Prompted by:** user feedback that ten interactions per session are too few for people who want
to keep exploring

**Related:** BITB-024 (built the 10-interaction limit + "Start New Session" reset),
BITB-061 (moved the counter into Postgres), BITB-080 (follow-up chips push users *toward* the cap)

---

## User Story

**As a** user in the middle of a fruitful conversation about scripture,

**I want** the message limit to bend to how I am actually using the app — more room when I am
genuinely exploring, and no loss of what we were just talking about when I do hit it,

**so that** a reflective nudge does not read as "you are done now" and interrupt the very
conversation it was meant to deepen.

---

## What the Limit Actually Is Today

Worth stating precisely, because "ten per session" is easy to mis-describe: this is not a rolling
request window, but an idle purge eventually resets the retained total.

| Knob (`api/config.py`) | Default | Scope |
|---|---|---|
| `rate_limit_session_max_requests` | **10** | Total per retained `session_id`; reset when its idle row is purged |
| `rate_limit_requests_per_session_minute` | 10 | Per session, 60s sliding window |
| `rate_limit_requests_per_minute` | 20 | Per IP, 60s sliding window |
| `rate_limit_session_ttl_seconds` | 3600 | In-memory backend idle TTL; see production caveat below |

Enforcement lives in `api/utils/rate_limiter.py` (Postgres-backed since BITB-061,
`rate_limit_sessions.total_requests`). The lifetime check deliberately runs *before* the
per-minute check so the farewell UX always wins. On the 11th message the backend returns
`429 {"error": "session_lifetime_limit"}` (`api/utils/security.py:247`); web
(`ChatIsland.tsx:726`) and Android (`ChatViewModel.kt:1230`) turn that into a localized
"take a break" message plus a **Start New Session** button.

The one-hour idle reset is not a precise rolling expiry in production. The in-memory store removes
a counter after `rate_limit_session_ttl_seconds` of inactivity, but the Postgres store does not read
that setting. Migration `scripts/migrations/010_schedule_rate_limit_purge.sql` runs an hourly
`pg_cron` job at minute 15 with a **hardcoded** `interval '1 hour'`. A production counter therefore
survives until the first purge after it has been idle for an hour (roughly one to two hours), and
changing the application setting alone does not change that behavior. This story must either make
the production purge horizon configurable from the same source or document and test the deliberate
fixed horizon; it must not describe the current cap as an unqualified lifetime total or the TTL as
an exact one-hour reset.

### The limit is already soft — and that is the problem

`handleNewSession()` (`ChatIsland.tsx:846`) rotates the `session_id` and **clears the entire
conversation**. So the user who wants an 11th message can have one immediately, at the price of
losing the thread. The cap therefore:

- **does not** cap anything for a determined user (rotate and continue; only the 20/min per-IP
  window is a real ceiling), and
- **does** punish the engaged user by wiping context exactly when the conversation got somewhere.

That is the worst of both worlds: no cost protection, maximum annoyance. Any fix should decide
which of the two jobs the number is doing.

### Raising it is *not* "a config change only"

BITB-024 recorded "changing the limit from 10 (config change only)" as out of scope. That is no
longer true — the number **10 is hardcoded in the copy** in:

- `frontend/messages/{en,de,it,es,fr,pt,ar,ru,zh,hi,ko}.json` → `Chat.sessionLimitMessage`
- `android/app/src/main/res/values/strings.xml:199` → `error_session_limit` (+ per-locale copies)

Bump the setting and eleven locales start lying to the user. The count must be interpolated
(ICU placeholder on web, `%1$d` on Android) before any number becomes tunable.

---

## Proposed Direction

**Split the one knob into the two jobs it is secretly doing.**

1. **The pastoral nudge** — "pause, reflect, go outside" — is a product feature and should stay.
   It just should not be a wall.
2. **The abuse / LLM-cost guard** — currently *not* actually served by this knob, since rotation
   is free.

### Recommended shape (v1)

- **Raise the reflective threshold and make it a nudge, not a stop.** Default
  `rate_limit_session_max_requests` 10 → **25**, and at the threshold show the existing farewell
  message with **two** buttons: *Start fresh* (today's behavior) and *Continue this conversation*.
- **"Continue" keeps the thread.** Rotate the `session_id` under the hood (so the counter resets)
  but **keep the messages on screen** and keep sending the same conversation history. This is the
  single change that removes the actual pain; the reflection prompt still gets shown.
- **Interpolate the count into all copy.** One source of truth: the backend reports the limit,
  clients render `{count}`.
- **Expose the limit to clients.** Return `X-Session-Limit` / `X-Session-Remaining` headers (or add
  the pair to the existing config/health surface) so web and Android can render "5 messages left"
  and never drift from the server's value.
- **Put a real ceiling where it belongs, after ingress identity is trustworthy.** First stop trusting
  arbitrary client-supplied `X-Forwarded-For` / `X-Real-IP`: accept forwarded addresses only from
  the known production ingress and define/test the trusted-proxy chain. Then evaluate a
  `rate_limit_ip_daily_max_requests` ceiling using production measurements. The selected cap must
  account for carrier-grade NAT, households, schools, churches, VPNs and other shared egress; an IP
  is neither a person nor a stable identity. Without both prerequisites, a daily IP cap is either
  spoofable or risks blocking many legitimate users together.

### Alternatives considered

| Option | Verdict |
|---|---|
| Just bump 10 → 30 and stop | Cheapest, but keeps the context wipe — the part users feel |
| Rolling window (N per hour/day) instead of lifetime-per-session | Cleaner mental model, but a break now *earns* nothing until the hour rolls; more moving parts |
| Cooldown ("continue in 60s") | Adds friction users read as punitive; the nudge already asks for a break |
| Accounts / paid tier for higher limits | Out of scope — the project is deliberately account-free |

### Measure before choosing the number

`ViolationType.RATE_LIMIT_LIFETIME` is already logged on every hit
(`api/utils/security.py:33,239`), but that event alone cannot reliably measure whether a user rotates
to a new ID or how long the conversation continues afterward. Before choosing 25 or any daily IP
cap, add privacy-reviewed, measurable instrumentation with documented event definitions and a
query/dashboard for: sessions reaching the threshold, *Start fresh* vs *Continue* selection,
post-threshold message depth, repeat thresholds, and the distribution of distinct sessions per
trusted client IP. Validate that the events arrive in production, then collect an agreed observation
window and record sample size and percentiles here. No threshold decision is accepted from
anecdotes, uncorrelatable logs, or an assumed query.

---

## Acceptance Criteria

- [ ] Privacy-reviewed instrumentation and its query/dashboard are deployed and validated before
      any threshold decision; this story records the observation window, sample size, threshold
      hits, action selected, post-threshold depth, repeat thresholds and relevant percentiles
- [ ] `rate_limit_session_max_requests` is genuinely tunable: changing it changes the enforced cap
      **and** every user-facing string, with no code or translation edit
- [ ] The count is interpolated in all 11 web locales and in Android `strings.xml` (all locales);
      no locale contains a literal "10"
- [ ] At the threshold, web and Android both offer **Continue this conversation** alongside
      **Start fresh**
- [ ] "Continue" preserves the on-screen conversation and the history sent to the backend, and the
      next message returns 200 (regression test — this is the BITB-024 bug's cousin)
- [ ] "Start fresh" still clears the thread exactly as today
- [ ] Clients read the limit from the server (header or config endpoint); no client-side constant
- [ ] Before an IP cap ships, forwarded headers are trusted only from configured production ingress,
      with direct-spoof and multi-proxy tests; deployment topology and trust assumptions are recorded
- [ ] Shared-IP/NAT measurements are reviewed (carrier NAT, households, institutions and VPNs), and
      the selected daily cap and false-positive safeguards are justified from those measurements
- [ ] New per-IP daily cap enforced in `rate_limiter.py` for both the Postgres and in-memory
      backends, with its own error code distinct from `session_lifetime_limit`
- [ ] The per-IP cap's 429 renders a *different*, non-pastoral message (it is an abuse guard, not
      an invitation to reflect)
- [ ] Backend tests cover: threshold enforced at the configured value, continue-path resets the
      counter, per-IP daily cap blocks after N and is unaffected by session rotation
- [ ] Idle expiry has one defined production behavior: the Postgres purge no longer silently
      hardcodes a horizon that can drift from `rate_limit_session_ttl_seconds`, with boundary tests
- [ ] Configuration/deployment scope is complete: `api/config.py`, Terraform variables and Container
      App environment manifest (`deployment/variables.tf`, `deployment/main.tf`), and
      `.env.production.example` expose and document the session, expiry and IP-cap knobs
- [ ] Both config consumers are updated: the backend `GET /config` contract plus web and Android
      config clients consume the published values and retain a documented fail-safe fallback
- [ ] Docs updated: `docs/USAGE_TRACKING.md`, `docs/SECURITY.md`, and the BITB-024 story's "Out of
      Scope" note, including trusted-ingress and shared-IP limitations

---

## Out of Scope

- Accounts, sign-in, or a paid tier that buys a higher limit
- Removing the reflective nudge entirely — it is the product's point of view, not an accident
- Per-user personalization of the threshold (needs identity we deliberately do not have)
- Reworking the per-minute IP/session windows (20/min, 10/min) — those are anti-burst and fine
- iOS (BITB-087) — inherits whatever ships here

---

## Open Questions for the Product Owner

1. **Does "Continue" keep the reflection prompt?** Recommendation: yes — show the message, but let
   the user decide when to step away. A nudge that can be declined is still a nudge.
2. **Is unlimited-with-a-nudge acceptable**, if trusted-ingress and NAT analysis support a separate
   abuse ceiling? If not, an explicit maximum ("you may continue twice") is a small delta.
3. **What threshold does the new instrumentation support?** Treat 25 only as a hypothesis; do not
   select it until the prerequisite telemetry has produced a representative observation window.
