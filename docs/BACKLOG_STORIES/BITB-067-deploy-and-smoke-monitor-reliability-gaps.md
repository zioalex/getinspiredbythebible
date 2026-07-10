# BITB-067: Deploy & Smoke-Monitor Reliability — Gaps From the 2026-07-07 False-Alarm Incident

**Status:** 🚧 In Progress (gaps #2/#3/#4 shipped in PR #845; #1/#5/#6 open — Terraform/Azure infra work)
**Priority:** P1 (High) — the monitoring we just added (BITB-064/065/066) produced a false "production
down" alert while the site was healthy, and a routine deploy silently broke origin TLS. These gaps
erode trust in the alerts and can turn a no-op deploy into an outage.
**Size:** M (several small, independent hardening items)
**Created:** 2026-07-07
**Incident ref:** After PR #839 merged, the hourly `prod-browser-smoke` job failed for hours
(`getByTestId('assistant-message') — element(s) not found`) while chat worked fine for users; a
follow-up deploy then failed the post-deploy health check with
`api.voxquieta.org returned 525 (SSL Handshake Failed)`.

## User Story

As the operator of Vox Quieta, I want deploys and the production smoke monitor to fail **only when the
service is actually broken**, to **self-diagnose** the common failure modes, and to **not create new
outages as a side effect of routine changes**, so that a green pipeline means a healthy site and a red
alert means real user impact.

## Gaps found (each is an independently shippable fix)

### 1. Monitoring merges but never deploys → false "down" alerts

`azure-deploy` runs sit in a `waiting` approval gate indefinitely (several July 3–7 runs never
completed). PR #839 merged but its deploy stayed pending, so production kept serving the **pre-#839
frontend bundle** — which has no `data-testid="assistant-message"` / smoke reader. The browser smoke
test then failed for hours on a missing selector while chat was perfectly healthy.
**Fix direction:** don't leave prod-affecting deploys parked silently — either auto-deploy `main` on
merge, or alert when a merged commit hasn't reached production within N minutes (a "deployed SHA vs
`main` SHA" drift check; the backend already exposes build info via `/config`/health — expose the
frontend build SHA similarly and let the smoke test assert it).

### 2. Smoke test can't distinguish "service down" from "stale/mismatched bundle"

The locator waited 60s and reported a generic timeout, giving no hint that the real cause was an
undeployed bundle. **Fix:** immediately after submit, assert the **user** bubble
(`data-testid="user-message"`, renders synchronously) with a short timeout and a message naming the
likely cause ("deployed bundle predates the smoke instrumentation — is the deploy pending?"), so the
failure is fast and self-explanatory.

### 3. Playwright test-timeout shorter than its own assertions

`frontend/playwright.config.ts` sets no `timeout`, so the default **30s test timeout** caps the
spec even though its assertions use 60s ("generous cold-start") budgets — the cold-start tolerance is
unreachable and any slow start flakes. **Fix:** set `test.setTimeout(...)` (or a config `timeout`)
larger than the sum of step timeouts.

### 4. No failure diagnostics from the smoke job

`prod-browser-smoke.yml` uploads no Playwright trace/report artifact on failure and writes no
`detail.txt`, so the Telegram alert was a bare "DOWN" with no link to a trace. **Fix:** `if: failure()`
upload `frontend/test-results/` + `frontend/playwright-report/` as an artifact, and write a one-line
`$RUNNER_TEMP/detail.txt` (which `notify-telegram` already appends) pointing at the artifact + the
"check the deploy" hypothesis.

### 5. Routine deploys can break origin TLS (Cloudflare 525) — recurring

A deploy failed post-check with `525 SSL Handshake Failed` on `api.voxquieta.org` (origin cert
missing/unbound). This has recurred (the repo already ships a "Rollback: Emergency Cert Rebind"
runbook and a `backend_ssl_cert_bind` null_resource). The Container App custom-domain cert binding is
**imperative and lost whenever the app is replaced** — and BITB-064 *added a new
`terraform_data.backend_secret_trigger` input (`smoke_probe_secret`) that forces a backend
replacement*, i.e. adding a monitoring secret can now trigger the exact replace→unbind→525 sequence.
**Fix direction:** make the cert bind reliably re-run after any backend replacement (correct
`depends_on`/trigger wiring so the rebind is not skipped), and/or decouple secret changes from full app
replacement; add an automatic post-deploy rebind-and-retry rather than a manual runbook.

### 6. Secret rotation is coupled to full app replacement

Because probe secrets are hashed into `terraform_data.backend_secret_trigger`, rotating
`MONITOR_PROBE_SECRET` / `SMOKE_PROBE_SECRET` replaces the backend Container App (brief downtime +
the cert-rebind dependency in gap #5). **Fix direction:** evaluate moving these to a plain secret
update (`az containerapp secret set`) or Key Vault reference that doesn't force replacement.

## Acceptance Criteria

- [ ] A merged prod-affecting change either deploys automatically or alerts if it hasn't reached
      production within a bounded time (deployed-SHA vs `main`-SHA drift signal).
- [x] `prod-chat-smoke.spec.ts` fails fast with a descriptive message on a stale/mismatched bundle
      (asserts the user bubble first), and its test-level timeout exceeds its assertion budgets.
- [x] `prod-browser-smoke.yml` uploads a trace/report artifact and a `detail.txt` on failure.
- [ ] A backend app replacement (incl. secret rotation) reliably re-binds the origin cert with no
      manual runbook step; a deploy that would leave origin TLS broken fails loudly *before* flipping
      traffic, or auto-remediates.
- [ ] (Investigate) probe-secret changes no longer force a full Container App replacement.

## Notes / Reuse

- Smoke test + workflow: `frontend/e2e/prod-chat-smoke.spec.ts`, `frontend/playwright.config.ts`,
  `.github/workflows/prod-browser-smoke.yml`, `.github/actions/notify-telegram` (already appends
  `detail.txt`).
- Cert/replace machinery: `deployment/main.tf` — `terraform_data.backend_secret_trigger` (:533),
  `null_resource.backend_ssl_cert_bind` (:992), and the "Rollback: Emergency Cert Rebind" section in
  `deployment/README.md` (the manual procedure this story aims to automate).
- Deploy pipeline + approval gate: `.github/workflows/azure-deploy.yml`.
- Frontend build-SHA exposure (for gap #1's drift check): backend `/config` already reports
  telemetry/build info; mirror a `NEXT_PUBLIC_BUILD_SHA` the smoke test can assert.

## Out of Scope

- The already-shipped BITB-064/065/066 monitoring itself (this hardens its reliability, not its scope).
- Multi-region / blue-green deploy (a larger effort; these fixes target the current single-app deploy).

## Verification

- Simulate a stale bundle (point the smoke test at a build without the testid) → confirm the new fast,
  descriptive failure + uploaded trace artifact + Telegram detail line.
- Rotate a probe secret in a non-prod/staging apply → confirm the backend either isn't replaced, or is
  replaced *and* the cert re-binds automatically (origin `curl https://api.<domain>/health` returns
  200 through Cloudflare, no 525).
- Merge a trivial change without approving the deploy → confirm the drift signal fires within the
  bounded window instead of a browser-smoke false alarm hours later.
