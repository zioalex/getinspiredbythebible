---
id: BITB-298
status: todo
priority: P0
size: S
rank: 30
created: 2026-11-11
---

# BITB-298: Rate-Limit Search, Feedback and Church Endpoints; Bound Their Inputs

**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows R7–R10, R13.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 1. **Merge after BITB-297.**
**Commit:** `fix(api): rate-limit search, feedback and church endpoints (BITB-298)`

## Problem

Route guards dumped from the running app on 2026-11-11:

```text
GET   /scripture/search          (none)   <- paid embedding call per request
GET   /scripture/search/text     (none)
GET   /scripture/stats           (none)
POST  /feedback                  require_turnstile
POST  /feedback/contact          require_turnstile   <- sends email, writes a row
POST  /church/search             require_turnstile   <- 30 s call to a third-party site
```

- `/scripture/search` embeds the query on every call (`api/routes/scripture.py:282-290`).
  `q` has `min_length=2` and no maximum.
- No shipped client calls `/scripture/search`: `searchScripture`
  (`frontend/src/lib/api.ts:862`) has no non-test caller and Android has none.
- `FeedbackRequest.comment`, `.user_message`, `.assistant_response` and
  `ContactRequest.message` have no `max_length` (`api/feedback/models.py:29-57`);
  1,000,000-character values were accepted.
- `api/routes/church.py:75-82` calls `disciplestoday.org` with a forged Chrome
  `User-Agent`, `Origin` and `Referer`.

## Why `require_rate_limit` cannot simply be added

`require_rate_limit` (`api/utils/security.py:199-262`) reads `session_id` from the POST
body and counts the request against the **chat session lifetime cap** (10). Feedback and
contact bodies carry `session_id`, so adding the dependency would let a thumbs-up consume
a chat turn. This story adds a separate, IP-only limiter instead.

## Decisions already made

1. **New dependency factory** `require_ip_rate_limit(scope: str, per_minute: int)` in
   `api/utils/security.py`: IP only, no session, key namespaced by `scope` so it never
   shares a bucket with chat. Reuse the existing store (`RateLimiter` /
   `PostgresStore`); if the store has no namespace concept, prefix the key
   (`f"{scope}:{ip}"`) — do not add a table.
2. **Limits (per IP, per minute), each a setting:** search 30, feedback 20, contact 3,
   church 6.
3. **Search stays public** (no Turnstile): it is a `GET`, and the SEO pages in BITB-301
   are built without it. Rate limiting plus an input cap is enough.
4. **Verse, chapter, range, books, translations and book-name `GET`s stay unguarded.**
   They are database reads without paid calls, and BITB-302 fetches them server-side.
5. **`/scripture/stats` gets a 5-minute in-process cache**, no limiter.
6. **Field caps:** `comment` 2,000; `user_message` 2,000; `assistant_response` 20,000;
   `ContactRequest.message` 5,000; `user_agent` 500; `message_id`, `session_id`,
   `model_used`, `reason` 128; `verses_cited` at most 50 items of 100 characters. Over
   the cap → `422`. Check what the web and Android forms allow first; if a client allows
   more, raise the server cap to match rather than break the client.
7. **The church proxy identifies itself honestly:** `User-Agent: VoxQuieta/<version>
   (+https://voxquieta.org)`; drop the forged `Origin` and `Referer`. If the third-party
   API then refuses the request, keep the honest header, return the existing "unavailable"
   response, and record it under Owner steps — do not restore the disguise.
8. The monitor-probe bypass applies to the new dependency exactly as it does to the
   existing one.

## Requirements

1. Implement `require_ip_rate_limit` (decision 1) with the same `429` body shape and
   violation logging as the generic branch of `require_rate_limit`. It uses the resolver
   from BITB-297.
2. Apply it: `/scripture/search` and `/scripture/search/text` (scope `search`),
   `/feedback` (scope `feedback`), `/feedback/contact` (scope `contact`),
   `/church/search` (scope `church`).
3. `q` gets `max_length=200` on both search routes.
4. Field caps from decision 6 in `api/feedback/models.py`; add a cap to the church
   `location` field if it has none.
5. Cache `/scripture/stats` (decision 5).
6. Church proxy headers (decision 7).
7. Four new settings in `api/config.py` and `scripts/env-manifest.yaml`.
8. Read `/api/v1/client-events` and `/api/v1/client-errors` (`api/main.py:488-492,
   570-574`): they use `require_rate_limit`. If their bodies carry `session_id`, they
   have the lifetime-cap problem described above — switch them to the IP-only limiter
   (scope `telemetry`, 60/min) and add a regression test. If they do not, leave them and
   say so in the PR.

## Tests (minimum)

- Each guarded route returns `429` on request N+1 from one IP and `200` for a second IP.
- Scopes are independent: exhausting `feedback` does not affect `/chat` or `search`.
- **Regression:** 15 feedback posts with a `session_id` do not consume that session's
  chat lifetime cap (the next `/chat` call for that session is allowed).
- Probe secret bypasses the new limiter.
- Each capped field: at the cap → accepted; one over → `422`. Parametrize the comment and
  contact message with multi-byte text (ar, zh, hi, ko) to prove the cap counts
  characters, not bytes.
- `q` of 201 characters → `422`.
- `/scripture/stats` hits the database once for two calls within the cache window.
- Church proxy sends the honest `User-Agent` and no `Origin`/`Referer` (assert on the
  mocked outbound request).

## Acceptance criteria

- [ ] Route guard dump shows a limiter on all five routes
- [ ] Feedback never consumes chat session budget
- [ ] All text inputs on feedback, contact, church and search are bounded
- [ ] No forged browser headers in outbound requests
- [ ] **Owner step:** confirm the church finder still returns results in production after
      the header change; if not, contact the site owner for permission or an API key

## Out of scope

- Caching embeddings for repeated search queries (`CachingEmbeddingProvider` already
  exists — check whether search uses it and note the answer in the PR; do not change it).
- The full-scan behaviour of pure semantic search (July finding S2).

## Related

BITB-297, BITB-301, BITB-302, July audit S2, O5.
