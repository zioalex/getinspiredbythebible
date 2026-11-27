---
id: BITB-341
status: in-progress
priority: P1
kind: chore
size: S
created: 2026-11-18
follow_ups: [BITB-342, BITB-343]
---

# BITB-341: Playwright Browser Install Blows the Job Timeout, Cancelling `Frontend E2E` and False-Alarming the Prod Smoke

**Bug (CI stability).** On 2026-11-17 three consecutive `Frontend E2E` runs were cancelled at the
15-minute job timeout, leaving the latest run red on PRs #1312, #1306 and #1308:

| Run | PR | Conclusion | Cancelled at |
| --- | --- | --- | --- |
| [117](https://github.com/zioalex/getinspiredbythebible/actions/runs/44193112249) | #1312 | cancelled | 23:06:11 UTC |
| [116](https://github.com/zioalex/getinspiredbythebible/actions/runs/44192192472) | #1306 | cancelled | 23:06:11 UTC |
| [115](https://github.com/zioalex/getinspiredbythebible/actions/runs/44192177882) | #1308 | cancelled | 23:01:46 UTC |

These are not concurrency cancels: each was the newest run for its ref, with no later push.

**It recurred while this fix sat unmerged.**
[Run 127](https://github.com/zioalex/getinspiredbythebible/actions/runs/45304189532) on
2026-11-24 01:19 UTC (dependabot styling PR) was cancelled the same way: the **webkit** leg's
`Install Playwright browser` step ran 01:24:39 -> 01:38:49 (14m10s) and died on the 15-minute job
timeout, while chromium, firefox and Mobile Safari installed in 16-25s on the same run. Six days
after the first occurrence, same step, same engine. Over the 60 most recent `frontend-e2e` runs
(2026-11-16 -> 2026-11-27) that is 2 newest-per-ref cancellations from this cause; the other 8
`cancelled` runs in the window are ordinary `cancel-in-progress` supersessions.

**Root cause.** Every matrix leg spends most of its budget in
`npx playwright install --with-deps <browser>`, whose `--with-deps` half is an `apt-get install` of
the engine's system libraries. The Ubuntu mirror (`us-east-2.ec2.archive.ubuntu.com`) crawled for
~12 minutes that evening — the webkit leg's log shows `Get:` lines arriving seconds apart and the
job was killed at `Get:96` of ~100 packages, i.e. *almost finished*:

```text
2026-11-17T23:05:58.7791940Z Get:96 .../libsoup-3.0-0 amd64 3.6.6-1ubuntu0.3 [295 kB]
2026-11-17T23:06:07.2832889Z ##[error]The operation was canceled.
2026-11-17T23:06:07.4744966Z Terminate orphan process: pid (2636) (npm exec playwright install --with-deps webkit)
```

The `webkit` and `Mobile Safari` legs are worst hit: `--with-deps webkit` pulls the whole GStreamer
stack (~100 packages), against ~40 for chromium. A healthy run finishes the *entire* job in ~4
minutes ([run 111](https://github.com/zioalex/getinspiredbythebible/actions/runs/44190262286): webkit
leg 22:29:16 → 22:33:20), so `timeout-minutes: 15` looks generous but leaves almost no headroom once
a mirror degrades — and nothing retries, so one slow mirror wastes the whole budget in a single
attempt.

**Blast radius.**

- `frontend-e2e.yml` is deliberately not a required check yet ("make it required once it has been
  stable for a while" — BITB-250), so merges are not blocked. But a cancelled run on every
  `frontend/**` PR makes the signal worthless and keeps the check from ever being promoted, which
  was BITB-250's stated goal.
- `prod-browser-smoke.yml` (BITB-064) has the *same* unretried `playwright install --with-deps`
  step on a tighter `timeout-minutes: 10`, and it notifies Telegram on failure. There, the identical
  mirror hiccup pages the owner about production while production is perfectly healthy.

## Fix

Same shape in both workflows. The two halves of `playwright install --with-deps` fail for
different reasons and are treated differently — that asymmetry is the heart of the fix:

1. **Split the install.** `playwright install-deps <browser>` (the apt half) and
   `playwright install <browser>` (the browser binary) become separate steps, so a slow mirror is
   attributable in the log instead of hidden inside one opaque step.
2. **Retry the binary half only** — 3 attempts, each bounded by `timeout 2m`, 15 s apart. It is a
   plain CDN fetch that holds no system locks, so retrying it is free.
3. **Do *not* retry the apt half.** `timeout` sends TERM to `npx`, which orphans the `sudo apt-get`
   beneath it; that orphan keeps `/var/lib/dpkg/lock-frontend`, so a second attempt dies instantly
   on "Could not get lock" and a merely-slow mirror becomes a hard failure — *faster* than the
   status quo, not better. apt already retries its own downloads (`Acquire::Retries`). The apt step
   therefore gets one attempt with a generous step-level `timeout-minutes` (14m e2e / 10m smoke) as
   its bound; the 2026-11-17 event needed ~13m, so it would now pass.
4. **Cache the browser binaries** (`~/.cache/ms-playwright`, `actions/cache@v6`, keyed on runner OS,
   engine and `frontend/package-lock.json`, with a prefix `restore-keys` fallback) so the binary
   download disappears on a cache hit and only the apt half stays variable. Deliberately *not*
   gated on `cache-hit`: `playwright install` is a no-op when the binary is present, and gating
   would break a partially restored cache.
5. **Give the job real headroom**, sized so the worst case still fits:
   - `frontend-e2e`: 15m → 30m. deps 14m + browser 3 × 2m + spec 6m = 26m, leaving ~4m for
     checkout / `npm ci` / build. A healthy leg finishes the whole job in ~4m.
   - `prod-browser-smoke`: 10m → 24m. deps 10m + chromium 3 × 2m + smoke 4m = 20m.
6. **Step-level `timeout-minutes` on the Playwright test steps**, so a hang in the *spec* is never
   misattributed to the install.
7. **Resolve the browser name once** (`Mobile Safari` → `webkit`) into a step output instead of
   repeating the ternary at each use.

## Non-functional requirements

- No change to what the specs assert or to which engines run: the matrix stays
  chromium / firefox / webkit / Mobile Safari.
- No new secrets, services or network destinations.
- A cache miss must degrade to today's behaviour (a full install), never to a failure.

## Acceptance criteria

- [x] `.github/workflows/frontend-e2e.yml`: install split into deps + browser; the binary half
      retried with a bounded per-attempt timeout; the apt half a single attempt bounded by its step
      timeout; `~/.cache/ms-playwright` cached; job `timeout-minutes` >= 25; the spec step has its
      own `timeout-minutes`
- [x] `.github/workflows/prod-browser-smoke.yml`: same treatment, job `timeout-minutes` >= 20
- [x] Regression test (`api/tests/test_frontend_e2e_workflow.py`, in the always-on Backend API Tests
      job) parses both workflows and asserts: the two halves are separate steps and `--with-deps`
      is gone, the binary half retries with a bounded per-attempt timeout, **the apt half is not
      retry-wrapped** (the dpkg-lock guard — this is the assertion that encodes the reasoning), the
      worst-case budget fits the job `timeout-minutes`, the browser cache path is cached, and the
      engine matrix is unchanged. 17 tests; each invariant verified against a deliberately broken
      workflow, not just asserted
- [x] `yamllint` / pre-commit and `make backlog-check` pass
- [x] The PR's own `Frontend E2E` run is green on all four engines (the workflow's path filter
      includes itself, so the fix tests itself).
      [Run 118](https://github.com/zioalex/getinspiredbythebible/actions/runs/44215478870), PR #1317,
      2026-11-18 01:23 UTC — firefox 2m38s, chromium 2m53s, webkit 3m04s, Mobile Safari 3m25s.
      All four well inside the new budget, and the webkit legs that were cancelled at 15m on
      2026-11-17 now finish in about three minutes. (First data point for BITB-343.)

## Out of scope

- Moving the matrix into the official `mcr.microsoft.com/playwright` container image, which would
  remove the apt and browser-download steps entirely but couples the image tag to the
  `@playwright/test` version in the lockfile. Filed as BITB-342.
- Promoting `Frontend E2E` to a required check (BITB-250's open goal): that needs a stretch of
  stable runs *after* this fix. Filed as BITB-343.
- BITB-253 (`Integration Tests` flaking in "Load CI test data") is a different flake in a different
  workflow and stays separate.

## Follow-ups

- BITB-342 — run the Playwright matrix in the official Playwright container image
- BITB-343 — promote `Frontend E2E` to a required check once it has been stable
