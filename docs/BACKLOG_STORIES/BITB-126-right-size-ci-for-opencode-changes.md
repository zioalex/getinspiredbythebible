# BITB-126: Right-Size CI for opencode Agent-Config Changes

**Priority:** P2 (Medium)
**Status:** 🚧 In Progress
**Size:** S–M (one new workflow + path scoping + the missing tests)
**Created:** 2026-09-12
**Affects:** `.github/workflows/`, `scripts/`, `deployment/kubeopencode/` — no application code

---

## Background

CI for opencode agent-configuration changes is wrong in **both** directions: it
runs an enormous amount of irrelevant work, and it runs none of the relevant
work. Both were verified against `main` on 2026-09-12.

### Direction 1 — irrelevant CI runs

`.github/workflows/test_update.yml` triggers on `deployment/**` and `scripts/**`
(lines 19-20, 32-33). So editing `deployment/kubeopencode/README.md` — a
markdown file — starts:

| Job | Work triggered |
|---|---|
| `backend-tests` | PostgreSQL 16 + pgvector service, Ruff/Black/MyPy, `alembic upgrade head`, full pytest |
| `alembic-migrations` | Second PG service, upgrade → check → downgrade → upgrade roundtrip |
| `frontend-tests` | Node **22.x and 26.x matrix**: `npm ci`, vitest, lint, tsc, `npm run build` |
| `integration-tests` | Full `docker compose` stack, **pulls the `mxbai-embed-large` Ollama model**, loads Bible data, generates embeddings, calls the chat endpoint |
| `security-check` | Python `safety` + `npm audit` |

None of these can be affected by a KubeOpenCode manifest or an agent prompt.
`integration-tests` additionally consumes `secrets.TF_VAR_OPENROUTER_API_KEY`
and makes live LLM calls — real spend on a docs-only change.

### Direction 2 — the relevant CI does not exist

```
$ grep -rln "opencode" .github/workflows/
(no matches)
```

No workflow references opencode at all. Consequences:

1. **`scripts/test_generate_opencode_config.py` never runs in CI.** It holds 19
   regression tests written specifically to guard the BITB-123 fallback-routing
   regression. `backend-tests` runs `cd api && pytest`, which never collects
   `scripts/`. These tests are, in CI terms, dead code.
2. **`make verify-opencode-config` never runs in CI.** Its 12-agent count,
   `fallback_models`-present, and runtime-fallback-plugin assertions are only
   enforced if a human remembers to run the Makefile target.
3. **Nothing detects generated-artifact drift.** `.opencode/agents/*.md` is the
   documented source of truth and `opencode.json` is the committed generated
   artifact. Editing an agent `.md` and forgetting `make gen-opencode-config`
   produces a silently stale `opencode.json` — which is what
   `make sync-opencode-configmap` pushes to the cluster. `.opencode/**` and
   `opencode.json` match **no** workflow path filter, so only `pre-commit.yml`
   (formatting/lint) runs.

The sharpest expression of the inversion: **editing
`scripts/generate-opencode-config.py` runs the entire application test suite but
not that script's own 19 regression tests.**

This is precisely the BITB-123 failure class — config silently losing a property
and fallback routing going inert — with no automated guard.

---

## User Story

**As a** maintainer changing an agent definition or a KubeOpenCode manifest,
**I want** CI to run fast checks that actually validate that change and skip the
application test suite,
**so that** agent-config regressions are caught automatically and docs-only PRs
do not cost 30+ minutes of runners and live LLM spend.

---

## Scope of Work

### 1. New workflow `.github/workflows/opencode-ci.yml`

Fast, hermetic: no database, no Docker, no Node matrix, no secrets. Target < 2
minutes.

Triggers (`pull_request` + `push` to `main`):

```yaml
paths:
  - ".opencode/**"
  - "opencode.json"
  - "scripts/generate-opencode-config.py"
  - "scripts/test_generate_opencode_config.py"
  - "deployment/kubeopencode/**"
  - ".github/workflows/opencode-ci.yml"
```

Jobs:

- `config-tests` — `pytest scripts/test_generate_opencode_config.py -v`
- `config-verify` — `make verify-opencode-config`
- `config-drift` — regenerate and diff against the committed artifact
- `manifests` — validate the KubeOpenCode YAML

**Implementation note — the generator needs PyYAML.**
`scripts/generate-opencode-config.py` does `import yaml`, which is not in the
stdlib. On a bare `actions/setup-python` runner it fails with
`ModuleNotFoundError: No module named 'yaml'`, and a naive `config-drift` step
that pipes the generator into a file would produce an **empty** file and report a
false drift. The workflow must `pip install pyyaml pytest` and must fail on the
generator's non-zero exit rather than only diffing its output.

**Cost baseline (measured 2026-09-12):** the 19 existing tests run in **0.35 s**.
Adding them to CI is effectively free; the only reason they do not run today is
that no workflow points at them.

### 2. Scope `test_update.yml` down

Exclude the KubeOpenCode folder from the application suite, on **both** the
`pull_request` and `push` trigger blocks:

```yaml
paths:
  - "deployment/**"
  - "!deployment/kubeopencode/**"
```

`scripts/**` stays broad — it holds migration, embedding, and monitor code that
genuinely affects the application — but the three opencode-only scripts are
excluded by name:

```yaml
paths:
  - "scripts/**"
  - "!scripts/generate-opencode-config.py"
  - "!scripts/test_generate_opencode_config.py"
  - "!scripts/test_kubeopencode_manifests.py"
```

Without this, the story's own motivating example is unfixed: editing the
generator would still start the full suite *and* now additionally start
`opencode-ci.yml`, so net CI cost for those paths would go **up**.

### Required-status-check interaction (checked 2026-09-12)

A path-filtered-out workflow leaves its checks `Pending`, not `Skipped`, and a PR
requiring them would be blocked from merging forever. Verified this is **not** a
risk here: the active rulesets on the default branch require only
`Lint Commit Messages`, `Lint PR Title` and `Pre-Commit Hooks` — all from
workflows with no path filters. None of the `test_update.yml` jobs are required.
**If any of them is ever made a required check, these exclusions must be
revisited** (the usual mitigation is a same-named stub job).

### 3. Missing tests to add

Evaluated against existing coverage: `scripts/test_generate_opencode_config.py`
already covers agent presence, fallbacks, tools/permission forwarding, plugin and
provider options, prompt/roster content, determinism, and the `agents.md` model
table. It does **not** cover the committed artifact or any manifest. Add:

| ID | Test | Guards |
|---|---|---|
| **T1** | Committed `opencode.json` byte-identical to generator output | Stale artifact shipped to the ConfigMap — the primary gap |
| **T2** | `agent.yaml` parses; `spec.configRef.configMapRef.name` equals the ConfigMap name created by `make sync-opencode-configmap`; `key` is `opencode.json`; namespace consistent across manifests | A rename on one side leaves the Agent pointing at a ConfigMap that does not exist — README says it then never starts |
| **T3** | Every `credentials[].secretRef` in `agent.yaml` is documented in `README.md` | Undocumented secret ⇒ agent silently degrades to the free fallback model |
| **T4** | Every `make` target referenced in `deployment/kubeopencode/README.md` exists in the `Makefile` | Documentation rot in the only runbook for this deployment |
| **T5** | Volume claims referenced by `agent.yaml` exist in `pvc.yaml`, with `accessModes` and a size set (once **BITB-125** lands) | Agent references a non-existent PVC and stays `Pending` |
| **T6** | `make verify-opencode-config` exits 0 in CI | 12-agent count, `fallback_models`, runtime-fallback plugin |

T1–T5 belong in `scripts/test_generate_opencode_config.py` (or a sibling
`scripts/test_kubeopencode_manifests.py`) so they run locally *and* in CI. T6 is
a workflow step.

**T1 is the highest-value test in this story** — it is the one that closes the
BITB-123 regression class for good.

---

## Acceptance Criteria

- [x] `.github/workflows/opencode-ci.yml` exists with the path filters above and
      completes in under 2 minutes with no DB, Docker, Node matrix, or secrets
- [x] `test_update.yml` excludes `deployment/kubeopencode/**` on both triggers
- [x] `scripts/test_generate_opencode_config.py` runs in CI (all 19 existing
      tests execute and pass)
- [x] `make verify-opencode-config` runs in CI
- [x] Tests T1–T6 implemented and passing (T5 landed with BITB-125 in this branch)
- [x] Tests mutation-proven non-vacuous: drift, ConfigMap rename (incl. a decoy
      later Makefile target), and a deleted `persistence` block each fail the suite
- [ ] `make pre-commit` green; PR title uses `ci:`

---

## Verification

1. **Scoping:** open a PR touching only `deployment/kubeopencode/README.md`.
   Expect `opencode-ci`, `pre-commit`, `commitlint` — and **no** `backend-tests`,
   `alembic-migrations`, `frontend-tests`, `integration-tests`, `security-check`.
2. **Drift is caught (T1):** edit `.opencode/agents/i18n-qa.md` without running
   `make gen-opencode-config`. `config-drift` must fail with a readable diff.
   Regenerate → green. (Baseline: `opencode.json` was confirmed **in sync** with
   the generator on `main` on 2026-09-12, so the test starts from green.)
3. **A missing PyYAML does not masquerade as drift:** the drift job fails with the
   generator's own error, not an empty-output diff.
4. **Fallback regression is caught (T6):** temporarily remove `fallback_models`
   from one agent `.md`. `config-verify` must fail.
5. **Manifest mismatch is caught (T2):** temporarily rename the ConfigMap in
   `agent.yaml`. `manifests` must fail.
6. **No regression in application CI:** a PR touching `api/` still runs the full
   suite exactly as before.

---

## Out of Scope

- Restructuring `test_update.yml` beyond the `deployment/kubeopencode/**`
  exclusion (broader path-filter work is BITB-028)
- Running a live agent or any LLM call in CI
- Changing agent models, prompts, or the fallback plugin version

---

## Related

- BITB-123 — created the generator, the 19 regression tests, and
  `deployment/kubeopencode/`; the fallback-inert regression this story automates
- BITB-125 — persistent workspace volume; source of the T5 manifest assertions
- BITB-028 — pipeline path filters (prior art for path-based CI scoping)
- `.github/workflows/test_update.yml:19-20,32-33` — the `deployment/**` and
  `scripts/**` filters
- `Makefile` — `gen-opencode-config`, `verify-opencode-config`,
  `sync-opencode-configmap`
