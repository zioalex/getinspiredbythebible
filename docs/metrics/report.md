# Repo productivity report

*Generated 2026-07-13 by `tools/repo-metrics/` — history 2026-01-18 → 2026-07-12. Interactive dashboard: [index.html](./index.html).*

## Headline

| Metric | Value |
|---|---|
| Units of work landed on main (PRs + direct commits, release bumps excluded) | **670** |
| Calendar span | 176 days (141 active — 80%) |
| Code lines added / deleted | +141,809 / −21,630 (net +120,179) |
| Releases shipped | 80 |
| fix : feat ratio | **1.76** |
| Same-day hotfix releases (<24h after previous) | 27 |
| Regression fixes (fix ≤7 days after related feat) | 169 (62 same-scope) |
| Fix chains (≥2 fixes, same scope, ≤7-day gaps) | 25 |
| Reverts | 2 |

## Velocity

| Phase | Units | Active days | Units/active day | feat | fix | fix:feat | Code +/− |
|---|---|---|---|---|---|---|---|
| Pre-launch (→ v0.1.0, 2026-05-02) | 396 | 77/104 | 5.14 | 76 | 164 | 2.16 | +95,585 / −15,378 |
| Post-launch | 274 | 62/72 | 4.42 | 71 | 94 | 1.32 | +46,224 / −6,252 |

Work landed by type:

| Type | Count |
|---|---|
| fix | 258 |
| feat | 147 |
| build | 101 |
| docs | 44 |
| other | 43 |
| ci | 42 |
| test | 15 |
| refactor | 7 |
| chore | 7 |
| perf | 5 |
| revert | 1 |

## Churn & rework

Overall churn ratio (deleted/added code lines): **0.153** — 15% of written code was later removed or rewritten.

Top fix chains (bursts of fixes on one scope):

| Scope | Fixes | Window | PRs |
|---|---|---|---|
| android | 34 | 2026-04-27 → 2026-05-20 | [#439](https://github.com/zioalex/getinspiredbythebible/pull/439), [#452](https://github.com/zioalex/getinspiredbythebible/pull/452), [#453](https://github.com/zioalex/getinspiredbythebible/pull/453), [#454](https://github.com/zioalex/getinspiredbythebible/pull/454), [#457](https://github.com/zioalex/getinspiredbythebible/pull/457), [#458](https://github.com/zioalex/getinspiredbythebible/pull/458), [#455](https://github.com/zioalex/getinspiredbythebible/pull/455), [#459](https://github.com/zioalex/getinspiredbythebible/pull/459) +26 more |
| android | 12 | 2026-03-07 → 2026-03-28 | [#252](https://github.com/zioalex/getinspiredbythebible/pull/252), [#298](https://github.com/zioalex/getinspiredbythebible/pull/298), [#295](https://github.com/zioalex/getinspiredbythebible/pull/295), [#303](https://github.com/zioalex/getinspiredbythebible/pull/303), [#304](https://github.com/zioalex/getinspiredbythebible/pull/304), [#313](https://github.com/zioalex/getinspiredbythebible/pull/313), [#341](https://github.com/zioalex/getinspiredbythebible/pull/341), [#346](https://github.com/zioalex/getinspiredbythebible/pull/346) +4 more |
| android | 10 | 2026-05-30 → 2026-06-22 | [#648](https://github.com/zioalex/getinspiredbythebible/pull/648), [#661](https://github.com/zioalex/getinspiredbythebible/pull/661), [#689](https://github.com/zioalex/getinspiredbythebible/pull/689), [#692](https://github.com/zioalex/getinspiredbythebible/pull/692), [#694](https://github.com/zioalex/getinspiredbythebible/pull/694), [#722](https://github.com/zioalex/getinspiredbythebible/pull/722), [#740](https://github.com/zioalex/getinspiredbythebible/pull/740), [#743](https://github.com/zioalex/getinspiredbythebible/pull/743) +2 more |
| ops | 6 | 2026-04-26 → 2026-04-30 | [#435](https://github.com/zioalex/getinspiredbythebible/pull/435), [#436](https://github.com/zioalex/getinspiredbythebible/pull/436), [#462](https://github.com/zioalex/getinspiredbythebible/pull/462), [#464](https://github.com/zioalex/getinspiredbythebible/pull/464), [#465](https://github.com/zioalex/getinspiredbythebible/pull/465), [#466](https://github.com/zioalex/getinspiredbythebible/pull/466) |
| ci | 5 | 2026-03-04 → 2026-03-08 | [#224](https://github.com/zioalex/getinspiredbythebible/pull/224), [#225](https://github.com/zioalex/getinspiredbythebible/pull/225), [#231](https://github.com/zioalex/getinspiredbythebible/pull/231), [#232](https://github.com/zioalex/getinspiredbythebible/pull/232), [#264](https://github.com/zioalex/getinspiredbythebible/pull/264) |
| frontend | 5 | 2026-03-09 → 2026-03-10 | [#285](https://github.com/zioalex/getinspiredbythebible/pull/285), [#287](https://github.com/zioalex/getinspiredbythebible/pull/287), [#289](https://github.com/zioalex/getinspiredbythebible/pull/289), [#290](https://github.com/zioalex/getinspiredbythebible/pull/290), [#294](https://github.com/zioalex/getinspiredbythebible/pull/294) |
| frontend | 5 | 2026-05-07 → 2026-05-23 | [#498](https://github.com/zioalex/getinspiredbythebible/pull/498), [#508](https://github.com/zioalex/getinspiredbythebible/pull/508), [#521](https://github.com/zioalex/getinspiredbythebible/pull/521), [#577](https://github.com/zioalex/getinspiredbythebible/pull/577), [#607](https://github.com/zioalex/getinspiredbythebible/pull/607) |
| frontend | 5 | 2026-06-02 → 2026-06-13 | [#674](https://github.com/zioalex/getinspiredbythebible/pull/674), [#699](https://github.com/zioalex/getinspiredbythebible/pull/699), [#709](https://github.com/zioalex/getinspiredbythebible/pull/709), [#721](https://github.com/zioalex/getinspiredbythebible/pull/721), [#739](https://github.com/zioalex/getinspiredbythebible/pull/739) |
| api | 4 | 2026-07-03 → 2026-07-10 | [#811](https://github.com/zioalex/getinspiredbythebible/pull/811), [#815](https://github.com/zioalex/getinspiredbythebible/pull/815), [#824](https://github.com/zioalex/getinspiredbythebible/pull/824), [#843](https://github.com/zioalex/getinspiredbythebible/pull/843) |
| api | 3 | 2026-06-05 → 2026-06-10 | [#682](https://github.com/zioalex/getinspiredbythebible/pull/682), [#700](https://github.com/zioalex/getinspiredbythebible/pull/700), [#712](https://github.com/zioalex/getinspiredbythebible/pull/712) |

Hotspot files (code files touched by the most units of work):

| File | Changes |
|---|---|
| `.github/workflows/azure-deploy.yml` | 77 |
| `api/config.py` | 49 |
| `frontend/package.json` | 46 |
| `android/app/src/main/res/values/strings.xml` | 45 |
| `android/app/src/main/res/values-it/strings.xml` | 41 |
| `android/app/src/main/res/values-de/strings.xml` | 41 |
| `android/app/src/main/res/values-fr/strings.xml` | 41 |
| `android/app/src/main/res/values-es/strings.xml` | 41 |
| `android/app/src/main/res/values-pt/strings.xml` | 41 |
| `android/app/src/main/res/values-ar/strings.xml` | 41 |
| `frontend/src/lib/api.ts` | 38 |
| `.github/workflows/android-ci.yml` | 38 |
| `api/chat/service.py` | 37 |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt` | 36 |
| `frontend/src/app/[locale]/page.tsx` | 34 |

## Quality & errors

Monthly fix vs feat:

| Month | feat | fix | fix:feat |
|---|---|---|---|
| 2026-01 | 2 | 17 | 8.5 |
| 2026-02 | 23 | 50 | 2.17 |
| 2026-03 | 46 | 58 | 1.26 |
| 2026-04 | 5 | 37 | 7.4 |
| 2026-05 | 35 | 48 | 1.37 |
| 2026-06 | 18 | 31 | 1.72 |
| 2026-07 | 18 | 17 | 0.94 |

Production-incident proxies: 27 same-day hotfix releases out of 80 total; 2 reverts.

- 2026-03-14 revert: revert DB backup retention to 7 days and disable geo-redundant backup [#321](https://github.com/zioalex/getinspiredbythebible/pull/321)
- 2026-05-07 revert: restore manifest + build.gradle.kts to pre-AD_ID-fix state [#491](https://github.com/zioalex/getinspiredbythebible/pull/491)

Most bug-prone scopes (by fix count):

| Scope | Total units | feat | fix |
|---|---|---|---|
| android | 111 | 40 | 60 |
| frontend | 21 | 3 | 16 |
| ci | 19 | 3 | 16 |
| api | 33 | 16 | 14 |
| ops | 8 | 1 | 7 |
| web | 8 | 3 | 5 |
| chat | 5 | 1 | 3 |
| android-publish | 5 | 0 | 3 |
| migrations | 4 | 1 | 3 |
| deploy | 3 | 0 | 3 |

## Process timeline

Dated process changes, mined from the first/last commit touching each marker file, aligned with the monthly fix:feat series. Correlation, not causation: months are confounded (launch freezes, platform pushes), a partial month distorts the ratio, and a change's effect may land pre-merge where these numbers can't see it. — means the month had no feats to divide by.

| Date | Process change | fix:feat month before | month of | month after |
|---|---|---|---|---|
| 2026-01-20 | Structured agent context file introduced (CLAUDE.md → AGENTS.md) | — | 8.5 | 2.17 |
| 2026-03-03 | opencode multi-agent harness introduced | 2.17 | 1.26 | 7.4 |
| 2026-05-02 | Conventional commits enforced + release-please automation | 7.4 | 1.37 | 1.72 |
| 2026-05-24 | opencode config last touched (harness parked) | 7.4 | 1.37 | 1.72 |
| 2026-06-08 | Plan→Build→Verify relay codified as the default workflow | 1.37 | 1.72 | 0.94 |
| 2026-07-03 | Adversarial risk audit: playbook, /risk-audit command, baseline report | 1.72 | 0.94 | — |
| 2026-07-03 | Self-measuring productivity metrics tooling added | 1.72 | 0.94 | — |

## Models & harness

Of 1,115 commits in the full graph, 129 are automation bots; of the rest, **617 (63%) carry an AI co-author trailer**. Per-commit Co-Authored-By trailers across all commits (branch commits included; release/dependabot bot commits counted separately). Absence of a trailer does not prove no AI was involved — early history under-reports.

| Model / author | Commits | feat | fix | About |
|---|---|---|---|---|
| human/unattributed | 369 | 52 | 111 |  |
| Claude (unversioned) | 292 | 78 | 122 | Commits co-authored as plain 'Claude' via Claude Code before version names were recorded in trailers. |
| Claude Opus 4.5 | 168 | 42 | 69 | Anthropic's frontier Opus-tier model (released Nov 2025) — the strongest reasoning/agentic tier of its generation; workhorse of this repo's pre-launch phase. |
| Android Dev alias | 57 | 21 | 26 | Commit persona used by the opencode Android subagents (`android-dev@bibleinspiration.app`). |
| Claude Opus 4.6 | 56 | 11 | 30 | Opus-tier successor (early 2026) with adaptive thinking and a 1M-token context window; used in the later phase and as the opencode orchestrator. |
| GitHub Copilot | 23 | 1 | 15 | GitHub's autonomous coding agent (copilot-swe-agent) — assigned issues/PRs directly on GitHub. |
| Claude Sonnet 4.6 | 11 | 3 | 4 | Sonnet-tier successor (early 2026); the 'build' model in the Plan→Build→Verify relay documented in AGENTS.md. |
| Claude Sonnet 4.5 | 9 | 0 | 0 | Mid-tier Anthropic model balancing speed and capability; used for implementation-heavy subtasks. |
| Claude (moonshotai/kimi-k2.5) | 1 | 1 | 0 | A third-party model (Moonshot Kimi K2.5) driven through a Claude-Code-style harness. |

- **Claude Code** — AGENTS.md context file; Plan→Build→Verify relay across models; Claude Co-Authored-By trailers. Models: Claude Opus (plan + verify), Claude Sonnet (build).
- **opencode** — opencode.json multi-agent config (orchestrator + specialist subagents). Models: github-copilot/claude-opus-4.6, opencode/minimax-m2.5-free, openrouter/qwen/qwen3-coder, qwen3.5:cloud, qwen3:30b-a3b, qwen3:8b-16k.
- **GitHub Copilot coding agent** — 23 commits co-authored by Copilot / copilot-swe-agent[bot].

## Codebase health

| Component | Files | LOC | Test files | Test LOC |
|---|---|---|---|---|
| android | 222 | 26,491 | 46 | 9,328 |
| api | 156 | 47,146 | 68 | 27,071 |
| ci | 23 | 5,507 | 1 | 521 |
| data | 5 | 0 | 0 | 0 |
| docs | 179 | 48,626 | 0 | 0 |
| frontend | 133 | 32,281 | 35 | 8,691 |
| infra | 26 | 6,945 | 0 | 0 |
| root | 29 | 3,807 | 0 | 0 |
| scripts | 39 | 6,988 | 3 | 773 |
| tools | 8 | 2,774 | 1 | 96 |

Leftover cruft (candidates for deletion):

- `AGENTS.md.old`
- `AGENTS.old.md`
- `frontend/src/components/ChapterModal.test.tsx.backup`
- `scripts/load_bible.py.backup`

## Run-over-run

| Snapshot | Units | fix:feat | Net code LOC | Releases | Regression fixes |
|---|---|---|---|---|---|
| 2026-07-03 | 610 | 1.88 | 105,514 | 67 | 158 |
| 2026-07-04 | 618 | 1.81 | 112,736 | 67 | 159 |
| 2026-07-13 | 670 | 1.76 | 120,179 | 80 | 169 |

## Methodology

- One *unit of work* = one first-parent commit on `main`: a squash-merged PR, a merge commit (pre-squash era), or a direct commit (earliest era). `release-please` version-bump PRs are excluded from work counts.
- Line counts exclude generated files (lockfiles, CHANGELOG) and `data/`; docs (`.md`) are counted separately from code.
- *Regression fix* = a `fix` landing ≤7 days after a `feat` with the same scope or touching a shared code file — a proxy, not a verdict.
- *Hotfix release* = a patch release tagged <24 h after the previous release.
- Regenerate with `make repo-metrics`.
