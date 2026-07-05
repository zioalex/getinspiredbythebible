# Repo productivity report

*Generated 2026-07-05 by `tools/repo-metrics/` — history 2026-01-18 → 2026-07-05. Interactive dashboard: [index.html](./index.html).*

## Headline

| Metric | Value |
|---|---|
| Units of work landed on main (PRs + direct commits, release bumps excluded) | **639** |
| Calendar span | 169 days (135 active — 80%) |
| Code lines added / deleted | +137,683 / −21,251 (net +116,432) |
| Releases shipped | 73 |
| fix : feat ratio | **1.79** |
| Same-day hotfix releases (<24h after previous) | 25 |
| Regression fixes (fix ≤7 days after related feat) | 164 (60 same-scope) |
| Fix chains (≥2 fixes, same scope, ≤7-day gaps) | 25 |
| Reverts | 2 |

## Velocity

| Phase | Units | Active days | Units/active day | feat | fix | fix:feat | Code +/− |
|---|---|---|---|---|---|---|---|
| Pre-launch (→ v0.1.0, 2026-05-02) | 396 | 77/104 | 5.14 | 76 | 164 | 2.16 | +95,585 / −15,378 |
| Post-launch | 243 | 56/65 | 4.34 | 65 | 88 | 1.35 | +42,098 / −5,873 |

Work landed by type:

| Type | Count |
|---|---|
| fix | 252 |
| feat | 141 |
| build | 92 |
| other | 43 |
| docs | 41 |
| ci | 36 |
| test | 14 |
| refactor | 7 |
| chore | 7 |
| perf | 5 |
| revert | 1 |

## Churn & rework

Overall churn ratio (deleted/added code lines): **0.154** — 15% of written code was later removed or rewritten.

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
| api | 3 | 2026-06-05 → 2026-06-10 | [#682](https://github.com/zioalex/getinspiredbythebible/pull/682), [#700](https://github.com/zioalex/getinspiredbythebible/pull/700), [#712](https://github.com/zioalex/getinspiredbythebible/pull/712) |
| api | 3 | 2026-06-19 → 2026-06-20 | [#759](https://github.com/zioalex/getinspiredbythebible/pull/759), [#764](https://github.com/zioalex/getinspiredbythebible/pull/764), [#768](https://github.com/zioalex/getinspiredbythebible/pull/768) |

Hotspot files (code files touched by the most units of work):

| File | Changes |
|---|---|
| `.github/workflows/azure-deploy.yml` | 74 |
| `api/config.py` | 48 |
| `android/app/src/main/res/values/strings.xml` | 44 |
| `frontend/package.json` | 43 |
| `android/app/src/main/res/values-pt/strings.xml` | 40 |
| `android/app/src/main/res/values-it/strings.xml` | 40 |
| `android/app/src/main/res/values-de/strings.xml` | 40 |
| `android/app/src/main/res/values-es/strings.xml` | 40 |
| `android/app/src/main/res/values-fr/strings.xml` | 40 |
| `android/app/src/main/res/values-ar/strings.xml` | 40 |
| `api/chat/service.py` | 37 |
| `frontend/src/lib/api.ts` | 37 |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt` | 36 |
| `.github/workflows/android-ci.yml` | 35 |
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
| 2026-07 | 12 | 11 | 0.92 |

Production-incident proxies: 25 same-day hotfix releases out of 73 total; 2 reverts.

- 2026-03-14 revert: revert DB backup retention to 7 days and disable geo-redundant backup [#321](https://github.com/zioalex/getinspiredbythebible/pull/321)
- 2026-05-07 revert: restore manifest + build.gradle.kts to pre-AD_ID-fix state [#491](https://github.com/zioalex/getinspiredbythebible/pull/491)

Most bug-prone scopes (by fix count):

| Scope | Total units | feat | fix |
|---|---|---|---|
| android | 109 | 39 | 59 |
| frontend | 21 | 3 | 16 |
| ci | 19 | 3 | 16 |
| api | 29 | 14 | 13 |
| ops | 8 | 1 | 7 |
| web | 8 | 3 | 5 |
| chat | 5 | 1 | 3 |
| android-publish | 5 | 0 | 3 |
| migrations | 4 | 1 | 3 |
| verse-links | 3 | 0 | 3 |

## Codebase health

| Component | Files | LOC | Test files | Test LOC |
|---|---|---|---|---|
| android | 219 | 26,121 | 45 | 9,208 |
| api | 148 | 45,950 | 63 | 26,245 |
| ci | 20 | 5,043 | 1 | 521 |
| data | 4 | 0 | 0 | 0 |
| docs | 165 | 37,578 | 0 | 0 |
| frontend | 128 | 31,868 | 33 | 8,529 |
| infra | 26 | 6,521 | 0 | 0 |
| root | 26 | 3,696 | 0 | 0 |
| scripts | 36 | 6,221 | 3 | 773 |
| tools | 8 | 2,391 | 1 | 96 |

Leftover cruft (candidates for deletion):

- `AGENTS.md.old`
- `AGENTS.old.md`
- `frontend/src/components/ChapterModal.test.tsx.backup`
- `scripts/load_bible.py.backup`

## Run-over-run

| Snapshot | Units | fix:feat | Net code LOC | Releases | Regression fixes |
|---|---|---|---|---|---|
| 2026-07-03 | 610 | 1.88 | 105,514 | 67 | 158 |
| 2026-07-05 | 639 | 1.79 | 116,432 | 73 | 164 |

## Methodology

- One *unit of work* = one first-parent commit on `main`: a squash-merged PR, a merge commit (pre-squash era), or a direct commit (earliest era). `release-please` version-bump PRs are excluded from work counts.
- Line counts exclude generated files (lockfiles, CHANGELOG) and `data/`; docs (`.md`) are counted separately from code.
- *Regression fix* = a `fix` landing ≤7 days after a `feat` with the same scope or touching a shared code file — a proxy, not a verdict.
- *Hotfix release* = a patch release tagged <24 h after the previous release.
- Regenerate with `make repo-metrics`.
