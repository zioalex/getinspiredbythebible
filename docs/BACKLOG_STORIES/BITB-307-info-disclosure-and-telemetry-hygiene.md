---
id: BITB-307
status: done
priority: P2
size: S
rank: 40
created: 2026-11-11
prs: [1297]
follow_ups: [BITB-317, BITB-318]
---

# BITB-307: Trim `/config`, Stop Leaking Upstream Errors, Drop the Session Metric Label, Tighten CORS

**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows R14, R15, R16, R18.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), any wave.
**Commit:** `fix(api): trim public config, generic upstream errors, bounded metric labels (BITB-307)`

## Problem

Four small exposures, each cheap to close:

1. **`GET /config` is public and over-shares** (`api/main.py:413-457`; live `200` with
   top-level keys `chat`, `embedding`, `features`, `llm`, `security`, `telemetry`). It
   names the LLM and embedding providers and models alongside the values clients
   actually need (session limits, message length, Turnstile site key). The model
   name tells an attacker which jailbreaks to try.
2. **The provider error handler returns the upstream exception text** to the client,
   plus the hint "Check if Ollama is running: ollama serve" (`api/main.py:686-696`).
3. **A client-chosen `session_id` is a metric label**
   (`chat_sessions_counter.add(1, {"session_token": request.session_id})`,
   `api/routes/chat.py:82` and `:136`). Every new session creates a new time series;
   anyone can create millions. Application Insights bills by ingestion.
4. **CORS** allows credentials with `*` methods and headers, and always includes
   `http://localhost:3000` and `:3001`, in production too (`api/main.py:338-350`,
   `:371-377`; July finding O4).

## Decisions already made

1. **`/config` returns only what a shipped client reads.** Find the readers first:
   `grep -rn "/config" frontend/src android/app/src/main`. Keep exactly those fields.
   Provider, model and temperature are removed unless a client displays them — if one
   does, keep the field and say so in the PR rather than break the client.
2. **Diagnostic detail moves behind the probe secret:** a new
   `GET /api/v1/admin/config` (same guard pattern as `api/routes/admin.py`) returns the
   removed fields for operators and monitors. Check the workflows for readers of the
   removed fields (`grep -rn "/config" .github/workflows scripts`) and point them at the
   admin endpoint.
3. **Upstream errors are logged in full and returned generic:** status and machine code
   unchanged, message "The AI service is temporarily unavailable." No exception text,
   no hints.
4. **The session label is dropped.** The counter stays, without the label. Distinct
   sessions are already countable from the `sessions` table
   (`docs/USAGE_TRACKING.md`); update that document and any workbook or KQL query that
   groups by `session_token`
   (`grep -rn "session_token" deployment docs scripts .github`).
5. **CORS:** methods are the ones the API uses (`GET, POST, OPTIONS`); headers are an
   explicit list built from what the clients send (content type, the Turnstile token
   header, the probe header, correlation ID — read `frontend/src/lib/api.ts` and the
   Android interceptors for the real names). Localhost origins are added only when
   `settings.debug` is true or a new `CORS_ALLOW_LOCALHOST=true` is set.
   `allow_credentials` becomes `False` if no client sends cookies or HTTP auth — check;
   the session ID travels in the body.
6. **Local and CI stacks keep working:** set `CORS_ALLOW_LOCALHOST=true` in every
   compose file and CI job where a browser on `localhost` calls the API (the
   `integration-tests` job in `test_update.yml`, `docker-compose*.yml`, the e2e setup).
   The BITB-064 cross-origin smoke probe must stay green.

## Requirements

Implement decisions 1–6. Add `CORS_ALLOW_LOCALHOST` to `api/config.py` and
`scripts/env-manifest.yaml`. Update `docs/SECURITY.md` or the document that describes
CORS, if one does.

## Tests (minimum)

- `/config` response keys equal an explicit allowlist (a snapshot test, so adding a field
  is a deliberate act); it contains no provider or model name.
- `/api/v1/admin/config`: `401` without the secret; full detail with it.
- Provider failure → response body contains none of the exception text (inject an
  exception with a sentinel string and assert it is absent from the body and present in
  the log).
- Metric: after a chat call the counter was incremented with no `session_token`
  attribute (assert on the mocked counter).
- CORS preflight from `https://voxquieta.org` → allowed; from `http://localhost:3000`
  with debug off and the flag unset → not allowed; with the flag set → allowed; a
  disallowed method or header → not allowed.
- Web and Android unit tests that parse `/config` still pass against the trimmed
  payload (update fixtures in both).

## Acceptance criteria

All five verified against production on 2026-11-18, after #1297 merged
(see *Post-deploy verification* below for the commands).

- [x] `curl https://api.voxquieta.org/config` shows no provider or model (**owner step**
      after deploy) — live response is `chat` / `features` / `security` only; the
      `has("llm") or has("embedding") or has("telemetry") | not` check returns `true`
- [x] No client or workflow broke: frontend, Android and integration suites are green —
      Backend API Tests, Frontend Tests (22.x and 26.x) and Integration Tests all green on
      the merged head `f063c20`; Android was untouched by the diff
- [x] No client-chosen value is used as a metric label anywhere
      (`grep -rn "session_token" api --include=*.py` outside tests shows no metric call) —
      the remaining hits are `api/utils/session_tracker.py` SQL and log calls, no metric
      attributes
- [x] Production CORS no longer lists localhost — a live preflight from
      `http://localhost:3000` is refused (`400`), while `https://voxquieta.org` is allowed
      with `access-control-allow-methods: GET, POST, OPTIONS` and no
      `access-control-allow-credentials`
- [x] The cross-origin smoke probe is green after deploy (**owner step**) — `Prod Browser
      Smoke` (BITB-064) and `Prod Monitor`, which includes the synthetic preflight, are
      both green on post-merge `main`

## Post-deploy verification

The recipe an operator can re-run at any time (also in #1297's description).

**Public endpoint — only the client allowlist comes back:**

```bash
curl -fsS https://api.voxquieta.org/config | jq -S 'map_values(keys)'
```

```json
{
  "chat": ["max_message_length", "session_max_requests"],
  "features": ["tts_enabled"],
  "security": ["turnstile_enabled", "turnstile_site_key"]
}
```

Mechanical pass/fail — prints `true` and exits 0 when the trimmed config is live:

```bash
curl -fsS https://api.voxquieta.org/config | jq -e 'has("llm") or has("embedding") or has("telemetry") | not'
```

If `llm`, `embedding` or `telemetry` is still present, an old revision is still serving
traffic; check the `azure-deploy` run and the backend Container App revision, then re-run.

**Operator endpoint — the same detail behind the probe secret.** The repo secret
`MONITOR_PROBE_SECRET` cannot be read back from GitHub; read the same value off the
Container App, via an env var so it stays out of shell history:

```bash
export MONITOR_PROBE_SECRET=$(az containerapp secret show --name bible-app-backend --resource-group bible-app-rg --secret-name monitor-probe-secret --query value -o tsv)
curl -fsS https://api.voxquieta.org/api/v1/admin/config -H "X-Monitor-Probe-Secret: $MONITOR_PROBE_SECRET" | jq -S 'map_values(keys)'
```

That returns the three public blocks plus the three that moved off `/config`:
`embedding` (`dimensions`, `model`, `provider`), `llm` (`max_tokens`, `model`, `provider`,
`temperature`) and `telemetry` (`appinsights_configured`, `appinsights_initialized`).

**The guard is fail-closed —** both of these print `401`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://api.voxquieta.org/api/v1/admin/config
curl -s -o /dev/null -w '%{http_code}\n' https://api.voxquieta.org/api/v1/admin/config -H 'X-Monitor-Probe-Secret: wrong'
```

`/api/v1/admin/config` is registered `include_in_schema=False`, so its absence from
`/docs` and `/openapi.json` is by design, not a failed deploy.

**CORS:**

```bash
curl -s -o /dev/null -D - -X OPTIONS https://api.voxquieta.org/api/v1/chat \
  -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: POST' \
  -w 'http_code=%{http_code}\n' | grep -i 'access-control-allow-origin\|http_code'
```

Production must refuse that origin (`400`, no `access-control-allow-origin`); swapping in
`Origin: https://voxquieta.org` must return `200` with
`access-control-allow-methods: GET, POST, OPTIONS`.

## Out of scope

- Authentication for `/config`.
- Changing which origins production allows beyond removing localhost.

## Related

July audit O4, O5; BITB-064, BITB-118, BITB-156 (Android reads limits from `/config`).

## Follow-ups

- BITB-317 — `/health/ready` echoes raw database exception text to anonymous callers.
- BITB-318 — chat responses still name the LLM provider and model (owner decision).
