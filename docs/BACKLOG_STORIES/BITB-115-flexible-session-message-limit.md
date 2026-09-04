# BITB-115: Make the Session Message Limit Flexible (Users Say 10 Is Too Few)

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

Worth stating precisely, because "ten per session" is easy to mis-describe — **there is no time
window on it at all.**

| Knob (`api/config.py`) | Default | Scope |
|---|---|---|
| `rate_limit_session_max_requests` | **10** | **Lifetime** total per `session_id` — no window |
| `rate_limit_requests_per_session_minute` | 10 | Per session, 60s sliding window |
| `rate_limit_requests_per_minute` | 20 | Per IP, 60s sliding window |
| `rate_limit_session_ttl_seconds` | 3600 | How long an idle session's counter is retained |

Enforcement lives in `api/utils/rate_limiter.py` (Postgres-backed since BITB-061,
`rate_limit_sessions.total_requests`). The lifetime check deliberately runs *before* the
per-minute check so the farewell UX always wins. On the 11th message the backend returns
`429 {"error": "session_lifetime_limit"}` (`api/utils/security.py:247`); web
(`ChatIsland.tsx:726`) and Android (`ChatViewModel.kt:1230`) turn that into a localized
"take a break" message plus a **Start New Session** button.

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
- **Put a real ceiling where it belongs.** Add `rate_limit_ip_daily_max_requests` (suggest 150,
  generous for a human, cheap insurance against a scripted loop) so cost is bounded by something
  that rotation cannot reset. This is the guard the session cap was never actually providing.

### Alternatives considered

| Option | Verdict |
|---|---|
| Just bump 10 → 30 and stop | Cheapest, but keeps the context wipe — the part users feel |
| Rolling window (N per hour/day) instead of lifetime-per-session | Cleaner mental model, but a break now *earns* nothing until the hour rolls; more moving parts |
| Cooldown ("continue in 60s") | Adds friction users read as punitive; the nudge already asks for a break |
| Accounts / paid tier for higher limits | Out of scope — the project is deliberately account-free |

### Measure before choosing the number

`ViolationType.RATE_LIMIT_LIFETIME` is already logged on every hit
(`api/utils/security.py:33,239`). Before picking 25, pull a week: how many sessions reach 10, how
many rotate and keep going, and what the message count looks like *after* rotation. If the median
"engaged" user stops at 13, the number is 15, not 25. This is one query, not a spike.

---

## Acceptance Criteria

- [ ] A week of `rate_limit_lifetime` violation data is summarized in this story (sessions hitting
      the cap, rotation rate, post-rotation length) and the chosen default is justified by it
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
- [ ] New per-IP daily cap enforced in `rate_limiter.py` for both the Postgres and in-memory
      backends, with its own error code distinct from `session_lifetime_limit`
- [ ] The per-IP cap's 429 renders a *different*, non-pastoral message (it is an abuse guard, not
      an invitation to reflect)
- [ ] Backend tests cover: threshold enforced at the configured value, continue-path resets the
      counter, per-IP daily cap blocks after N and is unaffected by session rotation
- [ ] `.env.production.example` documents both knobs
- [ ] Docs updated: `docs/USAGE_TRACKING.md` and the BITB-024 story's "Out of Scope" note

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
2. **Is unlimited-with-a-nudge acceptable**, given the per-IP daily cap becomes the real ceiling?
   If not, an explicit maximum ("you may continue twice") is a small delta on this design.
3. **25, or something the data picks?** Recommendation: let the data pick; 25 is the placeholder.
