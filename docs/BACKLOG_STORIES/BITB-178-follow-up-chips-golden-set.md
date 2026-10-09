# BITB-178: Follow-Up Chips — Curated Golden Set, Live Runner, and Flag Plumbing

**Status:** 🚧 In Progress
**Priority:** P2
**Size:** M
**Created:** 2026-10-09
**Parent refs:** BITB-080 (backend + web follow-up chips), BITB-149 (Android chips, PR #1109)

## User Story

**As** the product owner testing suggested follow-up chips (BITB-080/149) before turning them on
in production, **I want** a curated, repeatable set of questions with the expected chip behaviour
for each, and a runner that checks a live backend against it, **so that** I can tell whether the
chips are good enough to enable, in every supported language, and see them on a debug Android build
without hand-editing compose files.

## Context

The follow-up chips shipped dark: `chat_follow_ups_enabled` defaults to `False` (`api/config.py`)
and nothing sets `CHAT_FOLLOW_UPS_ENABLED` anywhere — no compose file passes it through (their
`environment:` lists are explicit, so `--env-file` alone cannot set it) and Terraform never maps it.
So Android 1.56.0 correctly shows no chips, and there is no way to switch the flag on locally
without editing a compose file. BITB-080's open acceptance criterion ("measure before flipping the
flag on") has no tooling behind it either.

## Functional Requirements

1. **Curated golden set** `api/golden_set/test_cases/follow_ups.yaml` (category `follow_ups`)
   covering all 11 languages (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) × four scenarios:
   - **expected** — normal study / theology / prayer questions: 2–3 chips must appear.
   - **verse-citing** — questions about a specific passage, likely to produce chips that mention
     a verse; any reference in a chip must also be cited in the answer (no fabricated refs).
   - **suppressed** — crisis/help-seeking (compassionate path) and off-topic messages: no chips.
   - **multi-turn** — the runner taps the first chip and sends it as turn 2 (with history);
     turn 2 must also yield valid chips, not repeat the tapped question, and not repeat
     turn 1's chip set verbatim.
2. **Evaluator** for follow-ups (count 2–3 / exactly 0, ≤120 chars each, no markup, no
   duplicates, chips in the expected language, no `FOLLOWUPS` trailer leaking into the answer,
   no fabricated references — using the canonical multilingual `utils.verse_parser`).
3. **Live runner** `scripts/run_follow_up_eval.py` that sends each case to a running backend
   (default `http://localhost:8000`) through the **streaming** endpoint the apps use (JSON
   endpoint selectable), evaluates it, prints a per-case / per-language / per-scenario report,
   exits non-zero on failure, and can print a **markdown checklist** for manual on-device testing.
4. **Flag plumbing**: `CHAT_FOLLOW_UPS_ENABLED` passed through every compose file's API service
   (default `false`) and a Terraform variable `chat_follow_ups_enabled` (default `false`) mapped
   into the backend Container App env. Production behaviour unchanged.
5. **How-to doc** for testing on Android against a local backend.

## Non-Functional Requirements

- All existing CI suites stay green (backend pytest, `scripts/validate-env.py`, pre-commit).
- No network/LLM needed in CI: the runner's logic is unit-tested with a mocked HTTP transport.
- Existing golden-set cases and `run_all_checks` behaviour unchanged (follow-up checks only run
  when follow-ups are supplied).
- Runner respects rate limiting (handles 429 + `Retry-After`, configurable delay) and uses a
  fresh `session_id` per case so the session cap never trips mid-run.

## Acceptance Criteria

- [ ] `follow_ups.yaml` has ≥1 case per (language × scenario) for all 11 languages and 4 scenarios;
      a data-integrity test enforces this.
- [ ] Follow-up evaluator unit-tested for every check incl. CJK, RTL and Devanagari chips.
- [ ] Runner unit-tested end to end against a mocked backend (stream + JSON, multi-turn, 429 retry,
      suppressed, failure exit code, checklist output).
- [ ] `CHAT_FOLLOW_UPS_ENABLED=true` in `.env.local` / `.env.production` reaches the API container
      in every compose stack; default stays `false`.
- [ ] Terraform variable defaults to `false`; `validate-env.py` passes; a test pins both.
- [ ] `make follow-up-eval` runs the runner; docs explain the Android debug-build flow.

## Out of Scope

- Turning the flag on in production (a separate decision once the runner results are reviewed).
- Human quality scoring of chip text (the existing `HumanScore` model can be used later).
- Running the live eval in CI (needs LLM credentials and costs money).

## Open Questions

- Crisis detection depends on the configured content-safety provider; a crisis case that yields
  chips locally may point at the safety config rather than the chips feature. The report says so.

## Implementation Plan

### 1. Golden-set models (`api/golden_set/models.py`) — additive, backward compatible

- `GoldenSetInput`: add `language: str | None = None` (sent as `ChatRequest.language`, exactly as
  the apps do) and `tap_follow_up: bool = False` (multi-turn: runner sends the first chip of
  turn 1 as turn 2).
- `Expectations`: add `follow_ups: Literal["expected", "suppressed", "any"] = "any"`. Default
  `"any"` keeps every existing case valid and unchanged.

### 2. Evaluator (`api/golden_set/follow_up_evaluators.py`, new)

`check_follow_ups(follow_ups, response, expectations) -> list[(name, passed, detail)]` plus
`run_follow_up_checks(...) -> AutomatedScore`. Individual checks:

| check | rule |
|---|---|
| `follow_up_count` | expected → 2 ≤ n ≤ 3; suppressed → n == 0; any → n == 0 or 2 ≤ n ≤ 3 |
| `follow_up_length` | every chip ≤ 120 chars (mirror `_MAX_FOLLOW_UP_LEN` — import it, don't copy) |
| `follow_up_markup` | no `<`, `>` or `<!--` in any chip |
| `follow_up_unique` | no duplicates (case-insensitive, whitespace-normalized) |
| `follow_up_language` | `utils.language.detect_language(" ".join(chips)) == expectations.response_language`; skip (pass with detail) if no chips or detector unavailable |
| `follow_up_no_trailer_leak` | `"FOLLOWUPS"` and `"<!--"` absent from the answer body |
| `follow_up_no_fabricated_refs` | every `str(ref)` from `utils.verse_parser.extract_all_references(chip)` is in `{str(r) for r in extract_all_references(response)}` (same rule as `ChatService._filter_fabricated_follow_ups`) |

Plus `check_multi_turn(turn1_chips, tapped, turn2_chips)`: turn-2 chips don't contain the tapped
text (normalized) and aren't an identical set to turn 1.

Do **not** change `run_all_checks` in `evaluators.py` (existing tests pin its `total_checks`).

### 3. Curated cases (`api/golden_set/test_cases/follow_ups.yaml`, new)

`category: follow_ups`. Five cases per language × 11 languages = 55 cases, ids
`fu-<lang>-<nn>`, tags always include the language code and exactly one scenario tag:

- `expected` ×2 (one study/theology question, one prayer/practical-faith question)
- `verse-citing` ×1 (question about a specific passage, e.g. Romans 8:28 / Psalm 23 / John 15,
  written with that language's native book name and separator — German `Römer 8,28`, zh/ko no
  space, Arabic, Devanagari)
- `suppressed` ×1 crisis/help-seeking (e.g. "I feel hopeless and don't want to go on") **and**
  ×1 off-topic (e.g. a recipe or football question) — so 6 per language, 66 total
- `multi-turn` ×1 with `tap_follow_up: true`, `follow_ups: expected`

Each case: `input.message` natural in that language, `input.language: <code>`,
`expectations.response_language: <code>`, `expectations.must_contain_scripture: false` (the
English-only scripture regex would false-fail non-English; this set measures chips),
`expectations.follow_ups: expected|suppressed`. Write messages a native speaker would type;
crisis wording must clearly be help-seeking, not graphic.

### 4. Runner core (`api/golden_set/follow_up_runner.py`, new) — pure + injectable

- `run_case(client: httpx.Client, case, *, mode: "stream"|"json", sleep=time.sleep) -> FollowUpCaseResult`
  - POST `/api/v1/chat/stream` (parse SSE `data:` lines; `content` tokens concatenated; the
    `completion` event's `corrected_message` if present replaces the body; `follow_ups` absent
    → `[]`; an `error` event → case error) or `/api/v1/chat` (JSON `message` + `follow_ups`).
  - Request body: `message`, `conversation_history`, `include_search`, `preferred_translation`,
    `language`, `session_id = "fu-eval-" + uuid4().hex[:12]` (fresh per case).
  - 429 / 503 → honour `Retry-After` (default 10s), max 3 retries, via the injected `sleep`.
  - `tap_follow_up`: if turn 1 has chips, send `chips[0]` with history
    `[{"role":"user",...},{"role":"assistant",...}]` (same session id), evaluate turn 2 with
    `follow_ups: expected` + `check_multi_turn`; if turn 1 had no chips, the case fails with
    detail "no chip to tap".
- `FollowUpCaseResult` (pydantic): case id, language, scenario tag, chips per turn, answer
  excerpt, `AutomatedScore`, elapsed ms, error.
- `summarize(results)` → totals per language and per scenario; `hint` string when every
  `expected` case returned zero chips: "CHAT_FOLLOW_UPS_ENABLED is probably off on this backend".
  Note in the report that crisis cases depend on the content-safety provider.
- `render_text_report`, `render_json`, `render_checklist(cases)` → markdown checklist grouped by
  language: `- [ ] **fu-it-01** (expected) — "message"` + expected behaviour line.

### 5. CLI (`scripts/run_follow_up_eval.py`, new)

Thin wrapper (same `sys.path` bootstrap as `scripts/run_search_eval.py`). Flags: `--base-url`
(default `http://localhost:8000`), `--mode stream|json` (default stream), `--language` (repeatable
or comma list), `--scenario`, `--case`, `--delay` (seconds between cases, default 3),
`--timeout` (default 120), `--json`, `--out PATH` (write JSON results), `--checklist` (print the
markdown checklist and exit; no network). Exit 0 all pass, 1 any failure, 2 backend unreachable
(clear message, no traceback).

Makefile: `follow-up-eval` (`ARGS=` passthrough) and `follow-up-checklist` targets.

### 6. Flag plumbing

- Add `- CHAT_FOLLOW_UPS_ENABLED=${CHAT_FOLLOW_UPS_ENABLED:-false}` to the **api service**
  `environment:` of `docker-compose.yml`, `docker-compose.dev.yml`,
  `docker-compose.local-prod.yml`, `docker-compose.local-prod-acr-be.yml` (with a one-line
  BITB-080/178 comment). Not `docker-compose.prod.yml` unless it has an api service built the
  same way — check and follow the pattern.
- `deployment/variables.tf`: `variable "chat_follow_ups_enabled"` (bool, default `false`,
  description referencing BITB-080). `deployment/main.tf` backend env map:
  `"CHAT_FOLLOW_UPS_ENABLED" = { value = tostring(var.chat_follow_ups_enabled) }` (keep the map
  alphabetical if it is). `deployment/terraform.tfvars.example`: commented line.
- `scripts/env-manifest.yaml`: `CHAT_FOLLOW_UPS_ENABLED` (`required_in: both`, default
  `"false"`). Add a commented `# CHAT_FOLLOW_UPS_ENABLED=false` to `.env.local.example`,
  `.env.dev.example`, `.env.production.example`.
- `python scripts/validate-env.py --strict` must pass.

### 7. Tests

- `api/tests/test_golden_set.py` (extend): follow_ups.yaml loads; every one of the 11 languages
  has ≥1 case per scenario tag (expected, verse-citing, suppressed, multi-turn); every case in the
  file has `follow_ups != "any"`, `input.language == expectations.response_language`; suppressed
  cases never set `tap_follow_up`; existing categories still pass `minimum_cases_per_category`.
- `api/tests/test_follow_up_evaluators.py` (new): each check pass + fail; parametrized chip
  language across all 11 languages (skip cleanly if lingua is unavailable — follow how
  `TestResponseLanguageCheck` handles it); fabricated-ref check with CJK (`约翰福音3:16`),
  Korean, Arabic, Devanagari and German comma refs; trailer leak; multi-turn repeat.
- `api/tests/test_follow_up_runner.py` (new): `httpx.MockTransport` backend — stream parse incl.
  `corrected_message`, missing `follow_ups`, `error` event; JSON mode; multi-turn sends history +
  tapped chip; 429 then 200 honours `Retry-After` via fake sleep; summary hint when all expected
  cases empty; checklist renders every case; CLI exit codes (load the script via
  `importlib.util` like `test_run_search_eval_cli.py`), unreachable → 2.
- `api/tests/test_follow_ups_flag_plumbing.py` (new): each compose file's api service env
  contains `CHAT_FOLLOW_UPS_ENABLED=${CHAT_FOLLOW_UPS_ENABLED:-false}`; `variables.tf` default
  false; `main.tf` maps it; `Settings(chat_follow_ups_enabled=...)` reads `CHAT_FOLLOW_UPS_ENABLED`
  env `"true"` → True and defaults False.

### 8. Docs / backlog

- `docs/FOLLOW_UPS_TESTING.md`: enabling the flag locally, running the runner, reading the
  report, the Android debug flow (emulator `make android-build`; USB `adb reverse tcp:8000
  tcp:8000` + `-PbaseUrl=http://localhost:8000/`; LAN IP), what "suppressed" means, the
  content-safety caveat, and that a small local Ollama model may not emit the trailer reliably.
- `docs/BACKLOG.md`: BITB-178 entry (P2), bump `Last Updated`.

### Verification

`cd api && python -m pytest tests/ -x -q`; `ruff check`, `black --check`, `mypy` on new modules;
`python scripts/validate-env.py --strict`; `terraform fmt -check deployment/` if terraform is
installed; `python scripts/run_follow_up_eval.py --checklist` runs offline.
