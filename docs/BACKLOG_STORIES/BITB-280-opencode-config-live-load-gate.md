---
id: BITB-280
status: in-progress
priority: P2
size: M
rank: 120
created: 2026-11-08
---

# BITB-280: Pre-Merge Live-Config Load Gate — Boot a Scratch opencode on the Committed Config Before It Reaches the Pod

**Migration note (2026-11-13, status):** PR pending review
**Incident:** 2026-11-08 18:51 (the motivating failure this gate exists to make impossible to repeat)

## Bug Report (the gap this gate closes)

At 18:51 on 2026-11-08 the task-reliability plugin shipped with **26 green
unit tests** and was merged and synced — and the live opencode 1.18.31
loader rejected it instantly:

```
message="failed to load plugin"
  path=file:///workspace/repo/.opencode/plugin/task-reliability.ts
  error="Plugin export is not a function"
```

The loader iterates `Object.values(module)` over the plugin's *entire*
export surface and requires every distinct export to be a function; the
plugin's `export const DEFAULT_REGISTRY_PATH` (a string) killed it. The
plugin was silently skipped, the stuck-subagent watchdog never armed, and
nothing in CI noticed — because **nothing in CI ever loads the config in a
real opencode runtime.** Unit tests assert the plugin's logic; the loader
asserts the plugin's *shape*. Green unit tests and a dead live loader are
fully compatible states. The same gap applies to the config itself: an
`opencode.json` that parses and generates cleanly can still be rejected, or
misbehave, at boot.

The BITB-269 fix (PR #1254) repaired the plugin. This story makes the
*class* of failure unmergeable: any change to `opencode.json`,
`.opencode/**`, or the generator now boots a scratch opencode instance
against the tree's **committed** config in CI and fails the PR if the
runtime won't accept it.

## Requirements

1. **`scripts/test-opencode-config-live.py`** (Python 3, stdlib-only — the
   brief offered bash or python; JSON rewriting, roster extraction, log
   classification and bounded subprocess handling made python the sane
   choice, and a python file under the brief's `.sh` name would trip the
   shellcheck pre-push hook). Runs anywhere: CI runner, pod, laptop.
   Numbered, fail-loud assertions:
   - **[1]** committed `opencode.json` parses as JSON
   - **[2]** expected agent roster present (`.opencode/agents/*.md` ⊆ config)
   - **[3]** every `mode: subagent` agent that DECLARES the `question`
     permission carries `question: deny`; a permission block without the
     question key is a loud warning (its posture is #1254's lane); blocks
     absent entirely are counted and reported
   - **[4]** config-listed `file://` plugin entries point at real files
     (pod-specific absolute paths are rewritten to the invoking tree in the
     scratch COPY — test-only shim, committed config never modified)
   - **[5]** `make verify-opencode-config` passes (invoke, don't duplicate)
   - **[6]** node plugin suite green when `.opencode/plugin/*.test.ts` exists
   - **[7]** scratch live boot: **zero** `failed to load plugin` for every
     config-listed `file://` entry (STRICT). npm-resolved entries
     (e.g. `opencode-runtime-fallback@0.2.4`) that fail to resolve in the
     scratch env are WARNINGS — registry flakiness is infra, not our code.
     Failures from **not-listed tree plugins** (runtime auto-discovery) are
     loud warnings whose strict enforcement activates once the config lists
     them; failures **outside the tree** (in-pod `/tools/opencode.json`
     leak) are attributed warnings. Until #1254 merges, main's config lists
     no `file://` entry, so the strict scope is honestly reported as
     vacuous — while the auto-discovery warning still surfaces main's known
     broken plugin copy.
   - **[8]** env-gated dispatch: with a provider key, dispatch a
     (preferably free-tier) subagent and assert the child session is
     created (`parentID=ses_…`, `(@<agent> subagent)` title) and completes;
     registry created/idle lines are asserted when the config lists a
     registry-writing plugin. Without a key: **SKIP loudly** ("dispatch-level
     validation deferred to pod pre-flight"), never silently.
2. **`--self-test` mode**: copy the first config-listed plugin (else the
   tree's first plugin file), append
   `export const CANARY_LOAD_BREAKER = "x";` — the exact 18:51 defect class
   — point a scratch config entry at the copy, boot, and REQUIRE the gate's
   detection to fire with the load error surfaced. The self-test passes
   only if the injected bug is caught; a blind gate fails.
3. **Makefile**: `test-opencode-config-live` and
   `test-opencode-config-live-selftest` targets.
4. **CI job** (`opencode-ci.yml` → `opencode Live Config Gate`), path-filtered
   on `.opencode/**`, `opencode.json`, the generator, the gate script, and
   the Makefile: Node 22 + Python 3.12, install the PINNED opencode binary
   via `npm install -g opencode-ai@$(--print-version)`, run both modes —
   the job is green only if normal mode passes AND the self-test catches
   the injected bug.
5. **Pinned version**: `PINNED_OPENCODE_VERSION = "1.18.31"` in the script
   is the single constant; CI installs it, the gate asserts the booted
   binary reports exactly it, and it cross-checks the `oc<x.y.z>` suffix of
   `agentImage` in `deployment/kubeopencode/agent.yaml` (the deployed pin). *(retargeted to
   `k8s/kubeopencode/agent-default-wf2.yaml` by BITB-285)*
   Bumping the pod's opencode without bumping the constant fails the gate —
   by design.
6. **In-pod pre-flight extension** (`sync-opencode-workspace.sh`): SKIPPED —
   that script exists only on PR #1254's unmerged branch, which this work
   must not touch. When #1254 merges, extend its pre-flight to run
   `make test-opencode-config-live` in-pod (full mode incl. dispatch) before
   the ConfigMap is touched (filed as the open item below).

## Empirically verified opencode 1.18.31 behaviors (probes, 2026-11-08)

All of these are load-bearing for the gate and were re-verified with
scratch canaries before relying on them (scratch dirs under
`/tmp/opencode/`):

| Behavior | Evidence |
| --- | --- |
| `OPENCODE_CONFIG` is IGNORED | invalid-JSON canary: boot crashes when placed at `$XDG_CONFIG_HOME/opencode/config.json`, boots happily when pointed at via `OPENCODE_CONFIG` |
| Plugin loading is LAZY | bare `opencode serve` boots with zero plugin lines in the log; `opencode run` loads config-listed + auto-discovered plugins right after config loading, before the first model call |
| `/tools/opencode.json` leaks into every boot | the kubeopencode binary loads it (compiled-in); in-pod scratch instances merge the live config — outside-tree plugin failures are attributed warnings |
| `.opencode/plugin/*` auto-discovery from cwd | main's not-listed broken plugin failed with the exact 18:51 error from a config that doesn't list it |
| Plugin entries must be 2-element `[name, options]` | 1-element entry → fatal `Missing key plugin.1.1` |
| Fresh-scratch npm resolution can stall pre-init | signature: log has config-loading lines, no `message=init`; recovered on retry; the gate retries once, then fails loudly |
| Keyless runs slog through fallback retries | with the runtime-fallback plugin loaded, a keyless model call can spend minutes in retry/cooldown machinery — so the gate polls the log for `message=init` evidence and kills the run instead of waiting for completion |
| Dispatch evidence shape | child log line carries `parentID=ses_…`, `agent=<name>`, title `"Dispatch <name> agent (@<name> subagent)"`; stdout carries the `✓ Dispatch` completion marker |

## Acceptance Criteria

- [x] Live gate normal mode passes on this branch (8/8 groups; scratch log:
      zero load failures for config-listed entries; warnings attribute the
      known main-state gap and the /tools leak)
- [x] Live gate `--self-test` catches the injected 18:51 canary with the
      load error surfaced (`error="Plugin export is not a function"`)
- [x] In-pod full-mode proof (dispatch included): child session created +
      completed (agent=i18n-qa on main's free lane; registry assertion N/A
      until #1254's config entry lands — noted loudly by the gate)
- [x] `make verify-opencode-config` + node plugin suite green via the gate
- [x] CI job added; the PR's own run executes both modes
- [x] Pinned version constant + agent.yaml cross-check + `--print-version`
      for CI install
- [ ] (follow-up, after #1254 merges) extend
      `scripts/sync-opencode-workspace.sh` pod pre-flight with the live gate
      (full mode incl. dispatch) before the ConfigMap is touched
- [ ] (after #1254 merges) the strict scope activates: the config-listed
      fixed plugin must load with zero failures, registry created/idle lines
      must be asserted on dispatch, and question-deny becomes strict for
      every subagent permission block

## Out of Scope

- Fixing the broken plugin copy on main (BITB-269 / PR #1254's lane)
- The fallback-chain model matrix (BITB-279 / PR #1259's lane)
- Positive confirmation of successful plugin loads (1.18.31 logs only
  failures; the self-test's canary proves the detection path end-to-end,
  which is the assurance that matters)

## References

- The 18:51 incident: BITB-269 story + PR #1254 (plugin fix, loader
  contract)
- BITB-279 (fallback chains) — its story anticipates this gate
- Loader contract: opencode 1.18.31 iterates `Object.values(module)`;
  every export must be callable (single-`default` plugins are the known-good
  shape)
- Live log (incident): `/tmp/.local/share/opencode/log/opencode.log`
  18:52:00Z `failed to load plugin`
