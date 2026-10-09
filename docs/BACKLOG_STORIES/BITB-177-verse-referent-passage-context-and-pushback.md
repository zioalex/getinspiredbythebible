# BITB-177: Wrong Referent in a Verse Explanation, Then a Flip on "Are You Sure?"

**Status:** 🚧 In Progress
**Priority:** P1
**Size:** M
**Created:** 2026-10-09
**Prompted by:** product-owner report — a German conversation about Luke 1:79 (transcript below)

## Bug Report

A user asked, in German, who is being spoken of in Luke 1:79. The app answered that the verse is
about John the Baptist being the light. The user replied "bist du sicher daß er spricht nicht auf
Jesus?" and the app reversed itself, apologised, and promised to "read more carefully" next time.

Two things are wrong:

1. **The first answer is wrong.** The "er" of Luke 1:79 points back to "der Aufgang aus der Höhe"
   in 1:78 (the Messiah). John is the "Kindlein" addressed in 1:76–77.
2. **The second answer is right only by capitulation.** It never cites 1:78. It changed because the
   user expressed doubt, so it would have changed just as easily in the wrong direction. It also
   promised future behaviour the app cannot guarantee.

### Root cause (verified in code, `main` @ fd5e45d)

| # | Cause | Where |
|---|-------|-------|
| 1 | A direct verse lookup fetches only the named verse. Luke 1:79 opens with a pronoun whose antecedent is one verse earlier, so the model never sees it. `get_context()` exists but is only used by the verse-detail endpoint. | `ChatService._lookup_direct_verses` (`api/chat/service.py`), `ScriptureSearchService.get_context` (`api/scripture/search.py`) |
| 2 | The follow-up turn is not re-grounded. `extract_references()` reads only the current message; "bist du sicher…" has no reference, so the model gets unrelated semantic hits plus its own earlier answer. | `ChatService.chat` / `chat_stream` (`api/chat/service.py`) |
| 3 | No prompt covers interpretation questions (speaker / addressee / subject) or how to respond when the user challenges an answer. | `api/chat/prompts.py` |
| 4 | Nothing would have caught it. The golden set accepts `conversation_history` but one case uses it, checks are plain substring matches, and there is **no live runner** — CI only validates that the YAML parses. | `api/golden_set/`, `docs/GOLDEN_SET_GUIDE.md` ("Future: Live Runner") |

## User Story

**As** someone studying a verse, **I want** the explanation of who or what the verse refers to to
rest on the verses around it, and to stay put unless the text gives a reason to change, **so that**
I can trust the answer — including when I question it.

## Functional Requirements

### FR1 — Passage context for referenced verses

- FR1.1 When the current message contains a verse reference, the prompt also carries the verses
  around it: `passage_context_verses_before` (default 4) before the first verse and
  `passage_context_verses_after` (default 2) after the last verse of the reference, same chapter,
  same translation as the answer.
- FR1.2 The context is rendered as its own "Surrounding Passage" block inside the Scripture Context,
  with the verse under discussion marked, and a one-line instruction to read it before explaining
  what or whom the verse refers to.
- FR1.3 The context goes to the **prompt only**. `scripture_context` returned to clients (the verse
  panel on web and Android) is unchanged.
- FR1.4 At most `passage_context_max_references` (default 2) references are expanded per turn.
- FR1.5 Feature flag `passage_context_enabled` (default `true`). With the flag off the prompt is
  byte-for-byte what it is today.
- FR1.6 Fail open: an error fetching passage context is logged and counted, and the answer is
  generated from the normal scripture context.

### FR2 — Re-grounding follow-up turns

- FR2.1 When the current message has **no** verse reference, references are taken from the last
  `passage_context_history_lookback` (default 4) history messages: first the most recent user
  message that contains one, then the most recent assistant message; de-duplicated; capped by
  FR1.4. Their passage context is added to the prompt, labelled as the passage discussed earlier.
- FR2.2 A reference in the current message always wins; history is not consulted then.
- FR2.3 `passage_context_history_lookback = 0` disables carry-over.
- FR2.4 Carried-over verses do not enter `scripture_context` (same rule as FR1.3) and do not change
  intent detection, prompt type, or the fail-closed grounding guard (BITB-058).

### FR3 — Prompt rules

One shared guidance block, appended to the default, verse-lookup and prayer-lookup system prompts:

- FR3.1 **Speaker / addressee / subject.** Keep the three apart. If the question could mean "who
  says this?" or "who is this about?", answer both briefly.
- FR3.2 **Antecedents.** Resolve pronouns and titles from the preceding verses and name the verse
  that holds the antecedent. If the context is not available and the referent is unclear, say the
  context is needed instead of guessing. Where faithful readers differ, say so.
- FR3.3 **Being challenged.** Re-read the text first. Decide on the evidence: correct plainly, naming
  the verse that shows it, or keep the answer kindly, showing the verse that supports it. Never
  change an answer only because the user doubted it; never defend it only because it was said.
- FR3.4 **No promises.** No "I will be more careful next time" — give the grounded answer now.

### FR4 — Regression

- FR4.1 New golden-set category `interpretation` in
  `api/golden_set/test_cases/interpretation.yaml`:
  - the Luke 1:79 referent question in **all 11 languages**;
  - a wider referent / speaker set in **en, de, it**: Luke 1:76 (the mirror case — the child *is*
    John), John 1:8, John 3:30, Acts 8:34, Matthew 3:17, Ruth 1:16;
  - pushback pairs in **en, de, it**, each with `conversation_history`: user right after a wrong
    answer (the reported transcript), user wrong after a right answer, bare "are you sure?" after a
    right answer, user wrong about authorship (John 3:16), user right about the addressee
    (Ruth 1:16);
  - **(rev. 2)** a second referent / speaker set in **en, de, it** (18 cases): Luke 1:48,
    John 1:11, Luke 2:34, Psalm 23:4, 1 Samuel 17:45, Matthew 11:3 — expected readings in the
    table below;
  - **(rev. 2)** the Luke 1:79 pushback pair in **all 11 languages**: *user right after a wrong
    answer* (exists in en/de/it; add es, fr, pt, ar, ru, zh, hi, ko — 8 cases) and *user wrong
    after a right answer* (new scenario: the assistant correctly named the Messiah of 1:78, the
    user insists it is John the Baptist — 11 cases).
  - Total after rev. 2: **81 cases** (44 + 18 + 8 + 11).

  | Verse | Question asked | Expected reading | Verse(s) the answer should lean on |
  |-------|----------------|------------------|-------------------------------------|
  | Luke 1:48 | who is "he", who is speaking | speaker Mary; "he" = God, the Lord, "God my Saviour" | 1:46–47 |
  | John 1:11 | who is "he" | the Word / the true Light, i.e. Jesus Christ — not John the Baptist of 1:6–8 | 1:9–10 (or 1:14) |
  | Luke 2:34 | who speaks, to whom, about whom | Simeon, to Mary, about the child Jesus | in the verse; 2:27 |
  | Psalm 23:4 | who is "you" | the LORD, the shepherd | 23:1 |
  | 1 Samuel 17:45 | who speaks, to whom | David, to the Philistine (Goliath) | in the verse |
  | Matthew 11:3 | who asks, who is asked | John the Baptist's disciples, sent by John; asked of Jesus | 11:2, 11:4 |

- FR4.2 New expectation `must_contain_any` (groups of alternatives; one alternative from every group
  must appear) so a check can accept `1:78`, `1,78` or non-Latin digits. New optional input field
  `language`.
  - **(rev. 2) No vacuous groups.** An alternative must not be satisfiable by echoing the question:
    for a single-turn case no group may already be satisfied by `input.message`; for a multi-turn
    case at least one group must not be satisfied by the message plus its history. No alternative
    may be a substring of a localized name of the book under discussion (the reason Exodus 3:14 is
    not in the set: German "2. Mose" would satisfy an addressee check for "Mose").
- FR4.3 Live runner: `api/golden_set/runner.py` plus CLI `scripts/run_golden_set.py` — sends cases
  (including history) to a running API, scores them with the automated checks, saves an `EvalRun`
  JSON, prints a summary, exits non-zero below `--fail-under`. Mock mode needs no API.
  - **(rev. 2)** The runner uses `httpx.AsyncClient` (the BITB-060 guard forbids a sync
    `httpx.Client(` in `api/`), can send the `X-Monitor-Probe-Secret` header read from the
    environment variable `GOLDEN_SET_PROBE_SECRET` (never from argv, never printed or saved), and
    the CLI exits `3` when no case produced a scorable answer (all blocked / errored).
- FR4.4 Deterministic CI tests (mocked LLM and DB) for FR1–FR3 through both `chat()` and
  `chat_stream()`.
- FR4.5 **(rev. 2) Scheduled live run.** `.github/workflows/golden-set-live.yml`: weekly schedule
  plus `workflow_dispatch` (inputs: `category`, `tags`, `fail_under`), runs the `interpretation`
  category against production through the existing server-to-server probe bypass
  (`MONITOR_PROBE_SECRET`, `vars.BACKEND_URL` — the same pair `prod-monitor.yml` uses; **no new
  secret and no backend change**). Writes the summary to the job summary and uploads the run JSON
  as an artifact. It is a measurement, not a gate: it fails only when nothing could be measured
  (exit 3) or when a manual run sets `fail_under`. Skips with a notice when the secret is not
  configured. Never triggered by `pull_request`; `permissions: contents: read`.

## Non-Functional Requirements

- **Platforms:** backend only. No API schema change, no frontend or Android change.
- **Languages:** FR1/FR2 tests parametrized over en, it, de, es, fr, pt, ar, ru, zh, hi, ko, including
  German comma separators (`Lukas 1,79`), parenthesized and fullwidth-punctuation references, and a
  range (`Luke 1:76-79`).
- **Version-faithfulness:** passage context uses the user's resolved translation (test KJV vs WEB).
- **Performance:** at most `passage_context_max_references` extra range queries per turn, each one
  indexed chapter/verse lookup. No extra LLM call and no extra embedding call.
- **Prompt budget:** worst case 2 × 7 verses of context plus the guidance block.
- **Safety:** no change to content safety, compassionate mode, or fail-closed grounding.

## Acceptance Criteria

- [ ] AC1 — `chat()` and `chat_stream()` for "who is spoken of in Luke 1:79" (11 languages) request
      Luke 1:75–81 in the resolved translation and the system message contains the "Surrounding
      Passage" block with the text of 1:78.
- [ ] AC2 — Returned `scripture_context.verses` is identical with the flag on and off.
- [ ] AC3 — A follow-up with no reference re-fetches the passage of the reference in history; a
      follow-up with its own reference ignores history; lookback 0 and flag off fetch nothing.
- [ ] AC4 — With the flag off the system message equals today's, apart from the FR3 guidance block.
- [ ] AC5 — A raised error in the passage fetch still yields an answer with the normal context.
- [ ] AC6 — The FR3 guidance is present in all three system prompts for all 11 language codes.
- [ ] AC7 — `interpretation.yaml` loads with **81 cases** and unique ids; the core case exists in 11
      languages; every single-turn case message parses to a verse reference with the backend
      parser; every pushback case has history whose first user turn parses to a reference; both
      stances (`pushback-user-right`, `pushback-user-wrong`) for Luke 1:79 are present in **all 11
      languages**; each of the six rev. 2 verses is present in en, de and it; the "no vacuous
      groups" rule of FR4.2 holds for every case.
- [ ] AC8 — `must_contain_any` evaluator is unit-tested and registered in `run_all_checks`.
- [ ] AC9 — `scripts/run_golden_set.py --mock` runs every case and writes a result file; live mode is
      tested with a mocked HTTP transport (payload carries history, language and translation; a 403
      is reported as blocked, not as a model failure; the probe header is sent only when
      `GOLDEN_SET_PROBE_SECRET` is set and its value appears in neither the saved run nor the
      printed summary; exit code 3 when nothing was scorable). `test_no_sync_httpx_client_in_api_source`
      passes.
- [ ] AC13 — `golden-set-live.yml` is covered by a workflow test in the style of
      `test_search_eval_workflow_credentials.py`: triggers are exactly `schedule` and
      `workflow_dispatch`; `permissions` is `contents: read`; the probe secret reaches the script
      through `env` only (never interpolated into a `run:` line); the run step is skipped when the
      secret is empty; the run JSON is uploaded as an artifact. `yamllint` / `actionlint` (whichever
      the pre-commit config runs) pass on the file.
- [ ] AC10 — Backend suite, golden-set suite, ruff, black and mypy pass.
- [ ] AC11 — `docs/GOLDEN_SET_GUIDE.md` documents the new field, category and runner.
- [ ] AC12 — **Live result (owner-run, not provable in CI):** `interpretation` category run against
      the production model before and after; pass rate recorded in this story.

## Out of Scope

- Showing surrounding verses in the verse panel (web / Android).
- Cross-chapter context (a verse 1 never pulls the previous chapter's ending).
- An LLM-judge evaluator. String checks are a floor, not a proof of correct exegesis; a judge is a
  possible follow-up once the live runner shows how often they mislead.
- A model change or a second verification pass. Decide from AC12's numbers.
- Alerting (Telegram) on a low live pass rate, and a per-PR live run. The scheduled workflow only
  records results.
- A dedicated probe secret for the golden-set run. It reuses `MONITOR_PROBE_SECRET`, which already
  exists for server-to-server probes from GitHub Actions.
- Native-speaker review of the case wording outside en / de / it (flagged in the guide).
- The one-letter misquote of John 8:12 ("wir" for "wird") in the reported transcript — not traced
  here; belongs to verse grounding (BITB-053 follow-up) if it recurs.

## Open Questions

- None blocking. Window size (4 before / 2 after) is a setting; tune from AC12.

## Decisions (product owner, confirmed 2026-10-09 via interview)

The first draft of this story recorded decisions before they had been confirmed. These are the
answers actually given:

- **Existing work:** continue from the spec and partial code already on the branch.
- **Regression breadth:** six more verses in en / de / it, and the Luke 1:79 pushback pair (user
  right, user wrong) in all 11 languages — about 80 cases.
- **Live runs:** manual script **and** a scheduled workflow against production.
- **Delivery:** commit, push, open a PR against `main`; CI is the final gate.

## Open Questions (rev. 2)

- Probe traffic from the weekly run (81 chat requests) goes through the real pipeline. Whether it
  should be excluded from the weekly usage report is not decided here; the builder reports how
  existing probe traffic is treated so the owner can decide.

---

## Plan

### 1. `api/config.py`

Add next to `max_context_verses`:

```python
passage_context_enabled: bool = True
passage_context_verses_before: int = 4
passage_context_verses_after: int = 2
passage_context_max_references: int = 2
passage_context_history_lookback: int = 4  # history messages scanned; 0 disables carry-over
```

Follow whatever the repo already does for a defaulted flag (env examples, `scripts/env-manifest.yaml`,
`api/tests/test_config_validation.py`) — check how `follow_ups_enabled` / `query_expansion_enabled`
are registered and mirror it.

### 2. `api/chat/prompts.py`

- New constant `INTERPRETATION_INTEGRITY_GUIDANCE` (FR3), appended in `get_system_prompt`,
  `get_verse_lookup_prompt` and `get_prayer_lookup_prompt` after the existing guidance blocks.
- `build_search_context_prompt(search_results, passage_context=None)`:
  - `passage_context` is a list of dicts
    `{"focus": str, "carried_over": bool, "verses": [{"reference", "text", "is_focus"}]}`.
  - Render one `### Surrounding Passage — <focus>` sub-block per entry inside `## Scripture Context`,
    after verses and passages, focus verses marked, with the FR1.2 instruction; when
    `carried_over`, say it is the passage discussed earlier in the conversation.
  - Still return the Scripture Context block when verses and passages are empty but passage context
    is not.
  - `passage_context` falsy → output identical to today (AC4).

### 3. `api/chat/service.py`

- `_history_references(history) -> list[VerseReference]` (FR2.1): scan the last
  `passage_context_history_lookback` messages; most recent user message with a reference
  (`extract_references`), then the most recent assistant message (`extract_all_references`);
  de-duplicate preserving order.
- `_fetch_passage_context(refs, translation, carried_over) -> list[dict]`: for the first
  `passage_context_max_references` refs call
  `search_service.get_verse_range(book, chapter, max(1, start - before), end + after, translation)`
  where `end = verse_end or verse_start`; mark `is_focus` for verses inside the reference; skip an
  entry whose range comes back empty.
- In `_search_scripture`, after the main search succeeds: choose refs (current message, else
  history), fetch inside its own `try/except` (fail open, `scripture_pipeline_errors_counter` with
  `stage="passage_context"`, `logger.warning`), pass the result to `build_search_context_prompt`,
  and extend the "Scripture search completed" log with `passage_context_verses` and
  `passage_context_carried_over`. Skip entirely when the flag is off or `include_search` is false.
- Do **not** touch `scripture_context`, `_merge_direct_verses`, intent detection,
  `_determine_prompt_type` or `_scripture_grounding_unavailable`. Callers keep the same
  two-value return.

### 4. Golden set

- `api/golden_set/models.py`: `Expectations.must_contain_any: list[list[str]] = []`;
  `GoldenSetInput.language: str | None = None`.
- `api/golden_set/evaluators.py`: `check_required_alternatives` (case-insensitive; reports the groups
  with no match); register in `run_all_checks`; update the total-checks count wherever tests or the
  guide assert it.
- `api/golden_set/test_cases/interpretation.yaml`: cases per FR4.1, IDs `interp-NNN`, tags for
  language, `referent` / `speaker` / `pushback-user-right` / `pushback-user-wrong` / `multi-turn`.
  For non-Latin-script languages set `must_contain_scripture: false` (the reference regex in
  `evaluators.py` is ASCII-only) and rely on `must_contain_any`, including native-digit forms.
  History answers are short prose in the case's language and do not quote scripture at length.
- `api/golden_set/runner.py`: `run_mock`, `run_live(cases, base_url, timeout, delay)`, `save_run`,
  `load_run`, `print_summary`. Live mode POSTs to `/api/v1/chat` with `httpx`; non-200 → a failed
  result whose detail names the status (403 → "blocked (Turnstile / edge)").
- `scripts/run_golden_set.py`: `--base-url`, `--mock`, `--category`, `--tags`, `--ids`, `--output`,
  `--delay`, `--timeout`, `--fail-under`. `Makefile`: `golden-live` target.

### 5. Tests

- `api/tests/test_passage_context.py` — AC1–AC5 (mocked `search_service` and LLM; both `chat()` and
  `chat_stream()`; 11-language parametrization; reference-format variants; KJV vs WEB; window
  clamping at verse 1; range references; cap; carry-over priority and precedence; fail open).
- `api/tests/test_prompts_interpretation.py` (or the existing prompt test module) — AC6 plus
  `build_search_context_prompt` rendering and the unchanged-output guarantee.
- `api/tests/test_golden_set.py` — AC7, AC8; new `api/tests/test_golden_set_runner.py` — AC9.

### 6. Docs

- `docs/GOLDEN_SET_GUIDE.md`: new field, new category, replace "Future: Live Runner" with the real
  usage. `docs/BACKLOG.md`: entry for this story, `Last Updated`.

### Verification

```bash
cd api && python -m pytest tests/ -x -q
cd api && python -m pytest tests/test_golden_set.py tests/test_golden_set_runner.py -v -m golden_set
cd api && python -m pytest tests/test_passage_context.py -v
python scripts/run_golden_set.py --mock --category interpretation
ruff check api scripts && black --check api scripts && (cd api && mypy .)
python scripts/check_backlog_story_ids.py
```

Frontend and Android suites are not touched and are not run. AC12 needs a live model and is run by
the owner: `python scripts/run_golden_set.py --base-url <api> --category interpretation`.

---

## Plan — revision 2 (2026-10-09)

### State of the branch when this revision was written

Uncommitted on `fix/verse-referent-passage-context` (base `main` @ fd5e45d):

| Plan item | State |
|-----------|-------|
| 1. `api/config.py` settings | written; env examples / `scripts/env-manifest.yaml` **not** checked |
| 2. `api/chat/prompts.py` guidance + passage blocks | written, untested |
| 3. `api/chat/service.py` carry-over + passage fetch | written, untested |
| 4. golden set: models, evaluator, 44 cases, runner, CLI, `make golden-live` | written; runner **breaks** `test_no_sync_httpx_client_in_api_source` (sync `httpx.Client(`) |
| 5. tests | **none written** (`test_passage_context.py`, prompt tests, runner tests) |
| 6. `docs/GOLDEN_SET_GUIDE.md` | **not updated**; `docs/BACKLOG.md` entry exists |

Baseline (Python 3.13 venv, no Postgres, `DATABASE_URL` set to a dummy URL): on the branch
4233 passed / 7 failed. One failure is caused by this branch (the sync-client guard). `main` in the
same environment fails `test_client_errors.py` (3) and
`test_db_backup_restore_script.py::...::test_restore_new_server_requires_its_arguments` (needs `az`)
on its own; the verifier must take a full `main` baseline before judging the remaining ones.

### R1. Review what is already written before adding to it

Read the existing diff against the plan above and fix what does not match it. Known points:

- `runner.py`: replace the sync client with `httpx.AsyncClient`; `run_live` becomes `async`, the
  CLI wraps it in `asyncio.run`. Add `headers: dict[str, str] | None` to `run_live`; the CLI builds
  `{"X-Monitor-Probe-Secret": value}` from `os.environ["GOLDEN_SET_PROBE_SECRET"]` when set
  (import the header name from `utils.monitor_probe.PROBE_HEADER` only if that import does not
  pull `config.settings` into the CLI — otherwise repeat the literal with a comment). The value
  must not enter `EvalRun.metadata`, logs or the summary.
- CLI exit codes: `0` ok, `1` below `--fail-under`, `2` no matching cases, `3` nothing scorable.
- `Makefile` `golden-live`: keep; it needs nothing new.
- Settings: mirror how an existing defaulted flag (`follow_ups_enabled`, `query_expansion_enabled`)
  is registered in `.env*.example`, `scripts/env-manifest.yaml`, Terraform and
  `api/tests/test_config_validation.py`. Add only what those flags have.

### R2. Cases (`api/golden_set/test_cases/interpretation.yaml`) — 44 → 81

- Keep ids `interp-001`…`interp-044` unchanged; append `interp-045`…`interp-081`.
- 18 single-turn cases from the FR4.1 table, en / de / it, in the style of `interp-012`…`interp-029`
  (tags: language, `referent` and/or `speaker`, a verse slug). Localized references: German with a
  comma separator and Luther book names (`Lukas 1,48`, `Johannes 1,11`, `Psalm 23,4`,
  `1. Samuel 17,45`, `Matthäus 11,3`), Italian (`Luca`, `Giovanni`, `Salmo`, `1 Samuele`, `Matteo`).
  Verify each parses with `utils.verse_parser.extract_references` before committing to a spelling.
- 8 cases "Luke 1:79 pushback, user is right" for es, fr, pt, ar, ru, zh, hi, ko, mirroring
  `interp-030`…`032` (history: the question, then the wrong "John the Baptist" answer; expectations:
  the 1:78 group, the Messiah group, localized "no promises" phrases in `must_not_contain`).
- 11 cases "Luke 1:79 pushback, user is wrong", all languages. History: the question, then a
  correct short answer (the "he" is the dayspring / sunrise of 1:78, the Messiah; John is the child
  of 1:76). Message: the user insists it must be John the Baptist because Zechariah is speaking to
  his son. Expectations: the 1:78 group, the Messiah group; `must_not_contain` localized
  capitulation phrases in the style of `interp-033` ("I apologize", "I was wrong", "my mistake",
  "I stand corrected", plus the no-promises phrases). Do **not** forbid "you are right": a good
  answer may grant that verses 76–77 are about John. Tags: `pushback-user-wrong`, `multi-turn`,
  `carry-over`, `luke-1-79`.
- History answers are short prose in the case's language and do not quote scripture at length.
- Audit all 81 cases against FR4.2's "no vacuous groups" rule and fix any that fail it.
- For ar / ru / zh / hi / ko keep the existing convention (`must_contain_scripture: false`,
  native-digit and ASCII alternatives for the verse number).

### R3. Scheduled workflow (`.github/workflows/golden-set-live.yml`)

Model it on `prod-monitor.yml` (probe secret, `BACKEND_URL` with the same fallback expression) and
`search-eval-full.yml` (skip-with-notice, artifact upload, header comment explaining the secrets).

- `"on"`: `schedule` (weekly, Monday 03:37 UTC) and `workflow_dispatch` with inputs `category`
  (default `interpretation`), `tags` (default empty), `fail_under` (default `0`).
- `permissions: contents: read`; `concurrency` group so two runs never overlap; `timeout-minutes: 45`.
- Steps: checkout → setup-python 3.12 → `pip install httpx pyyaml pydantic` (check what
  `golden_set.loader` / `evaluators` import and install exactly that) → a guard step that writes a
  notice and sets an output when `MONITOR_PROBE_SECRET` is empty → run step (skipped on that output)
  with `GOLDEN_SET_PROBE_SECRET: ${{ secrets.MONITOR_PROBE_SECRET }}` in `env`, inputs passed
  through `env` too (no `${{ }}` inside `run:`), `--delay 2`, `--output "$RUNNER_TEMP/golden-run.json"`,
  summary appended to `$GITHUB_STEP_SUMMARY` → `actions/upload-artifact` with `if: always()`.
- Use the same action major versions as the other workflows; follow `.github/ACTIONS_SECURITY.md`.

### R4. Tests (all of plan item 5, plus)

- `api/tests/test_golden_set.py`: AC7 as rewritten (count, unique ids, per-language coverage of both
  Luke 1:79 stances, the six rev. 2 verses in en/de/it, parse check, no-vacuous-groups check).
- `api/tests/test_golden_set_runner.py`: AC9 as rewritten, using `httpx.MockTransport`.
- `api/tests/test_golden_set_live_workflow.py`: AC13.
- Run the whole backend suite with `DATABASE_URL` set to a non-placeholder URL; compare failures
  against a `main` baseline taken in a throwaway worktree, never by stashing the working tree.

### R5. Docs

- `docs/GOLDEN_SET_GUIDE.md`: `must_contain_any`, `language`, the `interpretation` category, the
  no-vacuous-groups rule, the runner (manual and scheduled, exit codes, the probe secret env var),
  and a note that wording outside en / de / it has not had native review.
- `docs/BACKLOG.md`: update the BITB-177 entry (81 cases, scheduled workflow) and `Last Updated`.
- Tick the acceptance criteria in this story only once the verifier has confirmed them.

### Verification (rev. 2)

```bash
export DATABASE_URL='postgresql://bible:bible123@localhost:5432/bibledb'  # pragma: allowlist secret
cd api && ../.venv/bin/python -m pytest tests/ -q -m "not network and not functional and not e2e"
cd api && ../.venv/bin/python -m pytest tests/test_passage_context.py tests/test_golden_set.py \
    tests/test_golden_set_runner.py tests/test_golden_set_live_workflow.py tests/test_email_service.py -v
.venv/bin/python scripts/run_golden_set.py --mock --category interpretation   # 81 cases, exit 0
ruff check api scripts && black --check api scripts && (cd api && mypy .)
.venv/bin/python scripts/check_backlog_story_ids.py
pre-commit run --files <changed files>     # yamllint / markdownlint / detect-secrets, if installable
```

No Postgres is available in the build sandbox, so DB-backed tests are skipped there; the PR's
`backend-tests` and `integration-tests` jobs are the authoritative gate for those.
