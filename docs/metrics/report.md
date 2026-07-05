# Repo productivity report

*Generated 2026-07-03 by `tools/repo-metrics/` — history 2026-01-18 → 2026-07-02. Interactive dashboard: [index.html](./index.html).*

## Headline

| Metric | Value |
|---|---|
| Units of work landed on main (PRs + direct commits, release bumps excluded) | **610** |
| Calendar span | 166 days (132 active — 80%) |
| Code lines added / deleted | +126,470 / −20,956 (net +105,514) |
| Releases shipped | 67 |
| fix : feat ratio | **1.88** |
| Same-day hotfix releases (<24h after previous) | 24 |
| Regression fixes (fix ≤7 days after related feat) | 158 (57 same-scope) |
| Fix chains (≥2 fixes, same scope, ≤7-day gaps) | 24 |
| Reverts | 2 |

## Velocity

| Phase | Units | Active days | Units/active day | feat | fix | fix:feat | Code +/− |
|---|---|---|---|---|---|---|---|
| Pre-launch (→ v0.1.0, 2026-05-02) | 396 | 77/104 | 5.14 | 76 | 164 | 2.16 | +95,585 / −15,378 |
| Post-launch | 214 | 53/62 | 4.04 | 54 | 81 | 1.5 | +30,885 / −5,578 |

Work landed by type:

| Type | Count |
|---|---|
| fix | 245 |
| feat | 130 |
| build | 83 |
| other | 43 |
| docs | 40 |
| ci | 35 |
| test | 14 |
| refactor | 7 |
| chore | 7 |
| perf | 5 |
| revert | 1 |

## Churn & rework

Overall churn ratio (deleted/added code lines): **0.166** — 17% of written code was later removed or rewritten.

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
| `api/config.py` | 46 |
| `android/app/src/main/res/values/strings.xml` | 43 |
| `frontend/package.json` | 40 |
| `android/app/src/main/res/values-it/strings.xml` | 39 |
| `android/app/src/main/res/values-de/strings.xml` | 39 |
| `android/app/src/main/res/values-es/strings.xml` | 39 |
| `android/app/src/main/res/values-ar/strings.xml` | 39 |
| `android/app/src/main/res/values-pt/strings.xml` | 39 |
| `android/app/src/main/res/values-fr/strings.xml` | 39 |
| `frontend/src/lib/api.ts` | 37 |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt` | 35 |
| `api/chat/service.py` | 34 |
| `frontend/src/app/[locale]/page.tsx` | 34 |
| `.github/workflows/android-ci.yml` | 34 |

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
| 2026-07 | 1 | 4 | 4.0 |

Production-incident proxies: 24 same-day hotfix releases out of 67 total; 2 reverts.

- 2026-03-14 revert: revert DB backup retention to 7 days and disable geo-redundant backup [#321](https://github.com/zioalex/getinspiredbythebible/pull/321)
- 2026-05-07 revert: restore manifest + build.gradle.kts to pre-AD_ID-fix state [#491](https://github.com/zioalex/getinspiredbythebible/pull/491)

Most bug-prone scopes (by fix count):

| Scope | Total units | feat | fix |
|---|---|---|---|
| android | 107 | 37 | 59 |
| frontend | 21 | 3 | 16 |
| ci | 19 | 3 | 16 |
| api | 24 | 12 | 10 |
| ops | 8 | 1 | 7 |
| web | 6 | 1 | 5 |
| chat | 5 | 1 | 3 |
| android-publish | 5 | 0 | 3 |
| migrations | 4 | 1 | 3 |
| verse-links | 3 | 0 | 3 |

## Codebase health

| Component | Files | LOC | Test files | Test LOC |
|---|---|---|---|---|
| android | 218 | 25,917 | 44 | 9,139 |
| api | 141 | 43,112 | 59 | 24,808 |
| ci | 18 | 4,715 | 1 | 492 |
| data | 4 | 0 | 0 | 0 |
| docs | 146 | 31,150 | 0 | 0 |
| frontend | 126 | 32,004 | 32 | 8,324 |
| infra | 26 | 6,456 | 0 | 0 |
| root | 24 | 3,515 | 0 | 0 |
| scripts | 34 | 6,085 | 3 | 773 |

Leftover cruft (candidates for deletion):

- `AGENTS.md.old`
- `AGENTS.old.md`
- `frontend/src/components/ChapterModal.test.tsx.backup`
- `scripts/load_bible.py.backup`

## Methodology

- One *unit of work* = one first-parent commit on `main`: a squash-merged PR, a merge commit (pre-squash era), or a direct commit (earliest era). `release-please` version-bump PRs are excluded from work counts.
- Line counts exclude generated files (lockfiles, CHANGELOG) and `data/`; docs (`.md`) are counted separately from code.
- *Regression fix* = a `fix` landing ≤7 days after a `feat` with the same scope or touching a shared code file — a proxy, not a verdict.
- *Hotfix release* = a patch release tagged <24 h after the previous release.
- Regenerate with `make repo-metrics`.
