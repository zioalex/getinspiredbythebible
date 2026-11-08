# BITB-273: parity-ci oasdiff Job — Workspace-Relative Spec Paths for the Container Action

**Status:** 🚧 In Progress — PR #1255
**Priority:** P2
**Size:** S
**Created:** 2026-11-08
**Follow-up to:** BITB-261 (the oasdiff job landed in PR #1253)

## Bug Report

The warn-only `OpenAPI breaking changes (oasdiff, warn-only)` job of
`.github/workflows/parity-ci.yml` fails on **every** PR that triggers it —
first observed on PR #1241 (run 42504428717, job 128803889718), and it will
pollute every `api/**`-touching PR's status until fixed:

```
docker run ... --workdir /github/workspace
  -v "/home/runner/work/getinspiredbythebible/getinspiredbythebible":"/github/workspace"
  oasdiff-action "/home/runner/work/.../base-openapi.json" "/home/runner/work/.../head-openapi.json" ...
Error: failed to load base spec from
  "/home/runner/work/getinspiredbythebible/getinspiredbythebible/base-openapi.json":
  open .../base-openapi.json: no such file or directory
```

**Root cause (confirmed from the run log):** the step passes host-absolute
paths as the action's `base`/`revision` inputs:

```yaml
base: ${{ github.workspace }}/base-openapi.json
revision: ${{ github.workspace }}/head-openapi.json
```

`github.workspace` resolves on the **runner host** to
`/home/runner/work/...`, but `oasdiff/oasdiff-action` is a **docker** action:
the runner only mounts the workspace into the container at
`/github/workspace` (with `--workdir /github/workspace`) and passes the input
values verbatim as container arguments. The host path does not exist inside
the container, so oasdiff cannot open either spec — even though both are
correctly exported into `$GITHUB_WORKSPACE` (host) = `/github/workspace`
(container) by the earlier export steps.

## Requirements

1. Pass **workspace-relative filenames** to the action, per its documented
   path semantics (README, "Spec paths": the local-file format is a relative
   path such as `openapi.yaml`; git refs and URLs are also accepted):

   ```yaml
   base: base-openapi.json
   revision: head-openapi.json
   ```

   Inside the container these resolve against `--workdir /github/workspace`,
   i.e. exactly the mounted files the export steps produced.
2. Scan the repo for the same absolute-path-into-container anti-pattern:
   the only other `${{ github.workspace }}` use is
   `.github/workflows/kubeopencode-dev-image.yml` (`-v` bind-mount **source on
   the host-side docker CLI** — correct usage, untouched). The runner-side
   export steps keep `$GITHUB_WORKSPACE` — they run on the host, where it is
   correct.

## Acceptance Criteria

- [ ] The `OpenAPI breaking changes (oasdiff, warn-only)` job goes **green on
      this PR** — self-verifying, since the job runs on every PR and
      `parity-ci.yml`'s own path filter includes the workflow file
- [ ] The `oasdiff breaking-changes report` step inputs are the two bare
      filenames (`base-openapi.json`, `head-openapi.json`) with the
      container-path rationale recorded as a workflow comment
- [ ] No other workflow file shares the anti-pattern (verified:
      `kubeopencode-dev-image.yml`'s `-v` usage is host-side and correct)
- [ ] `make pre-commit` is clean

## Out of Scope

- Making oasdiff a hard CI gate (deliberate later decision, BITB-261 policy)
- Any change to the export steps or `scripts/export_openapi.py`
- oasdiff Pro review/approve gating

## Related

- **BITB-261** — the story that introduced the job (PR #1253); this is a
  follow-up bug fix to its CI wiring
- **docs/parity/README.md** — policy record (warn-only until the baseline is
  trusted)
