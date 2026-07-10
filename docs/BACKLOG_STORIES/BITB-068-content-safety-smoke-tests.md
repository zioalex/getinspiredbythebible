# BITB-068: Content-Safety Smoke Tests — CI Gate + Functional + Deployed Probe

**Status:** ✅ Done — three-tier smoke coverage (self-contained CI, functional, deployed probe)
delivered on PR #850; also revived a smoke test that had been silently skipping itself.
**Priority:** P1 (High) — for a pastoral-care product screening self-harm/violence content, the
safety net had **no working end-to-end smoke test**: the one that existed was dead, and the unit
tests use mocked providers with only a single "legitimate request still passes" assertion.
**Size:** S–M (three test tiers + one prod-monitor job + a docs note)
**Created:** 2026-07-10
**Parent / audit ref:** BITB-061 (`docs/BACKLOG_STORIES/BITB-061-fail-closed-abuse-controls.md`) —
this is the verification safety net for that story's content-safety phase (PR #840).

## User Story

As the operator of Vox Quieta, I want an end-to-end smoke test of the content-safety pipeline that
runs **at every deployment stage** (on every PR, against a running backend, and against production),
and that verifies **both directions** — harmful content is intercepted **and** legitimate content is
answered — so that neither a silently-degraded safety net nor over-blocking of genuine help-seekers
can ship undetected.

## Problem / Motivation

Two gaps, found while reviewing PR #840:

1. **No working smoke test.** A blocked message is **not** an HTTP error — the current code returns a
   warm **HTTP 200** whose `provider == "content_safety"` (`ChatService._build_blocked_response` /
   `_stream_blocked_response`, `api/chat/service.py`). The existing `TestContentSafetySmoke`
   (`api/tests/functional/test_production_api.py`) still asserted the **old** contract — HTTP **400**
   with `{"detail": {"error": "content_safety_violation"}}`. Its `content_safety_active` fixture
   probed for that 400, saw a 200 instead, and **skipped the entire class**. The smoke suite had been
   silently inert.

2. **Unit tests only assert one direction.** PR #840's new tests mock the providers and (correctly)
   focus on the fail-closed block path; only a single assertion checks that a *legitimate* message is
   not over-blocked. Nothing exercised the real request path end-to-end.

The load-bearing discriminator between "blocked" and "answered" is the **`provider`** field
(`content_safety` vs. the real LLM provider), not the HTTP status — both are 200.

## Acceptance Criteria

- [x] **CI correctness gate (self-contained, no external keys).**
      `api/tests/test_content_safety_smoke.py` drives the real ASGI app through FastAPI `TestClient`
      in deterministic `keyword_only` mode (Stage-2 provider unavailable → local keyword fallback),
      with `app.dependency_overrides` neutralizing Turnstile / rate-limit / the separate keyword
      pre-filter and injecting a fake LLM/embedding + dummy DB. Asserts: harmful directed-harm and
      violence → 200 + `provider == "content_safety"`; benign and help-seeking → 200 +
      `provider != "content_safety"`; and the `/api/v1/chat/stream` path both ways (first `metadata`
      chunk's `provider`). Runs in the existing `backend-tests` job with no network. (7 tests.)
- [x] **Functional test against a running backend — dead test revived.** Rewrote
      `TestContentSafetySmoke` in `api/tests/functional/test_production_api.py` to the real
      200/`provider=="content_safety"` contract: the `content_safety_active` fixture now detects the
      feature via `provider`, the harmful/benign assertions use `provider`, a help-seeking case was
      added, the stream test parses the `metadata` chunk (not the now-nonexistent `error_code`), and
      the class docstring was corrected. Still `@pytest.mark.functional` (auto-skips with no backend);
      run via `make test-functional-local`.
- [x] **Deployed production probe.** `scripts/monitor/synthetic_content_safety.py` (modeled on
      `scripts/monitor/synthetic_chat.py`) sends a harmful and a benign message to
      `/api/v1/chat/stream` via the `X-Monitor-Probe-Secret` bypass (content filter still applies,
      per `api/utils/monitor_probe.py`) and **fails loudly** on either a degraded safety net (harmful
      answered) or a false-positive (benign blocked). Wired as the `content-safety` job in
      `.github/workflows/prod-monitor.yml` on the `*/5 * * * *` schedule with the shared
      `./.github/actions/notify-telegram` action and `gh-monitor-state` de-dup.
- [x] **Docs.** `AGENTS.md` clarifies why the Plan → Build → Verify relay keeps verification on the
      strongest model (independent fresh-context critic that runs the tests; Sonnet 5 acceptable as a
      supplementary uncorrelated pass; Haiku 4.5 only for cheap pre-gating).

## Notes / Reuse

- Response contract source of truth: `_build_blocked_response` / `_stream_blocked_response`
  (`api/chat/service.py`) and the normal streaming metadata (`provider = settings.llm_provider`).
- Deterministic offline mode: `content_safety_mode="keyword_only"` with no OpenAI key falls back to
  `_full_keyword_fallback` (`api/utils/content_safety.py`), which blocks directed-harm/violence and
  allows benign/help-seeking without any ML provider.
- Probe scaffolding mirrored: `scripts/monitor/synthetic_chat.py` (arg parsing, `--detail-out`,
  `httpx`, `MONITOR_PROBE_SECRET`, SSE parsing). Notification plumbing reused verbatim:
  `.github/actions/notify-telegram` + the per-job `Notify Telegram` step + `STATE_BRANCH` de-dup.
- The **offline CI tier deliberately omits** the context-aware "benign biblical violence is allowed"
  case (e.g. *"How did David kill Goliath?"*) — the dumb keyword fallback would over-block it; that
  case belongs to the functional + prod tiers, which run against real `ml_only` Llama Guard.
- Related observability thread: BITB-055 / BITB-056 / BITB-064 (the same "make it loud" pattern) and
  BITB-061 (the fail-closed refactor this verifies).

## Out of Scope

- Changes to the content-safety pipeline itself (that is BITB-061 / PR #840). This story only adds
  tests, a monitoring probe, and a docs note; it asserts behavior already present in `main`.
- Adding the functional suite to a CI job (it currently runs on demand / against a deployed backend).
  Optional follow-up: wire it into the `integration-tests` job in `test_update.yml`.

## Verification

- CI gate: `cd api && pytest tests/test_content_safety_smoke.py -v` → 7 passed with no network/keys;
  full backend suite green (**3462 passed, 11 skipped, 0 failed**); `ruff check` + `black --check`
  (line-length 100) clean on all touched files.
- Functional: with no backend, `pytest tests/functional/test_production_api.py` collects and skips
  cleanly (48). Against `make test-functional-local`, the smoke class now **runs** (no longer skips)
  and passes — proving the fixture-skip bug is fixed.
- Prod probe: `BACKEND_URL=… MONITOR_PROBE_SECRET=… python scripts/monitor/synthetic_content_safety.py --detail-out /tmp/d.txt`
  exits 0 when harmful is blocked and benign is answered; exits 1 with detail on either regression.
  `prod-monitor.yml` is valid YAML (7 jobs); trigger via `workflow_dispatch` + `force_alert` to
  confirm the Telegram path.
