# BITB-291: Synthetic Probe of the ML Content-Safety Path in prod-monitor

**Status:** 🚧 In Progress (2026-11-11)
**Priority:** P1
**Size:** M
**Created:** 2026-11-10
**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 req. 6: an outage of Llama Guard or the failover is currently found only when users hit the keyword fallback.

## Acceptance criteria

- [ ] `prod-monitor.yml` (or the BITB-224 availability tests) sends a benign Bible-narrative question and a known-unsafe probe and asserts the ML path (not the keyword fallback) decided, e.g. via a response header or metric
- [ ] Probe failure alerts the owner; the probe message is clearly synthetic and not stored as user data
- [ ] Documented in `docs/` with the zero-to-running steps


## Plan (2026-11-11)

**Gap confirmed on main:** the existing `content-safety` job in `prod-monitor.yml`
(`scripts/monitor/synthetic_content_safety.py`) only checks that a harmful message is blocked
(`provider == "content_safety"`) and a benign one is answered. With Llama Guard down, the keyword
fallback still blocks "build a bomb", so the probe stays green during an ML outage. Nothing in a
response says *which* classifier decided.

1. **Decision attribution.** `ContentSafetyCheckResult` gets `decided_by` (`disabled`,
   `stage1_keywords`, `llama_guard`, `openai_moderation`, `azure`, `keyword_fallback`,
   `default_allow`) and `failover: bool` (True when OpenAI Moderation decided as the `ml_only`
   failover). Set on every return path in `api/utils/content_safety.py`. No behaviour change.
2. **Probe-only endpoint.** `POST /health/content-safety-probe` (`include_in_schema=False`),
   authorized only by `is_monitor_probe()` (`X-Monitor-Probe-Secret`), otherwise **404** (does not
   reveal itself). Body `{message (1..500 chars), language (default "en")}`; runs
   `get_content_safety_service().check()` directly — no chat, no LLM answer, and **no
   `record_blocked_sample`**, so the synthetic message is never stored as user data. Returns
   `{allowed, decided_by, failover, ml_path, reason, duration_ms}` (`ml_path` = decided_by in
   llama_guard/openai_moderation/azure). The response is gated by the secret because which path
   decided is operationally sensitive (it tells an attacker when the keyword fallback is active).
3. **Monitor script** `scripts/monitor/synthetic_ml_safety_path.py`: sends a benign Bible-narrative
   question ("Why did Cain kill Abel?" — the classic keyword-fallback false positive) and an unsafe
   probe; asserts both were decided on the ML path with the right verdict. `keyword_fallback` or
   `stage1_keywords` deciding = fail. OpenAI Moderation failover = pass, reported as degraded in the
   output; `REQUIRE_PRIMARY=true` makes it a failure.
4. **New `ml-safety-path` job** in `prod-monitor.yml` with its own Telegram transition alert
   (`notify-telegram`, same pattern/secrets as `content-safety`).
5. **Docs:** zero-to-running section in `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md` + `docs/TROUBLESHOOTING.md` entry.

**Known trade-off:** each run adds two real content-safety checks (≈576/day) to the
Llama Guard / fallback metrics; BITB-290 must account for it in the fallback-share denominator.

## Notes

Related: BITB-224.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
