# BITB-253: Integration Tests Intermittently Fail at "Load CI Test Data"

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-28
**Follow-up of:** BITB-250 (seen on PR #1226)

## Problem

On PR #1226 the `Integration Tests` job (`.github/workflows/test_update.yml`) failed twice in the setup step
"Load CI test data (1 Corinthians with embeddings)", before any test ran. The step runs
`scripts/load_bible.py --ci --translation web` and then `scripts/create_embeddings.py --ci` against the job's
Ollama (`mxbai-embed-large`). The PR did not touch that path. One re-run passed; the other failing commit was
superseded by green commits. A flaky setup step costs a re-run and teaches people to ignore red CI.

## Acceptance criteria

- [ ] Root cause found from the failing logs (e.g. Ollama or the model not ready, a download timeout, a
      Postgres race)
- [ ] The step waits for its dependency or retries the specific operation; no blanket job re-run
- [ ] The cause and the fix are noted here
