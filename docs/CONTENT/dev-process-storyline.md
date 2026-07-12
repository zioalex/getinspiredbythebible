# "I Let the AI That Built My App Audit It" — Video & Post Storyline

Storyline for a YouTube long-form video (8–15 min) and a conference-talk
adaptation about the development process of Vox Quieta
(getinspiredbythebible). Audience: developers and tech leads. Language:
English.

Every number below comes from the repo's own published analysis:

- Productivity dashboard: <https://zioalex.github.io/getinspiredbythebible/>
  (source: `tools/repo-metrics/`, written report `docs/metrics/report.md`)
- Audit trend dashboard: <https://zioalex.github.io/getinspiredbythebible/audit>
  (source: `tools/audit-metrics/`, full audit `docs/audits/2026-07-adversarial-audit.md`)

---

## The one-line pitch

> One person and a relay of AI agents shipped a three-platform AI product in
> six months — then turned the AI on its own code, published the brutal audit,
> and built dashboards so the numbers can't be hidden.

Three true hooks, braided into one arc:

1. **Solo + AI agents at scale** (Act 1 — the build)
2. **Self-measuring project** (Act 2 — the numbers)
3. **Radical transparency** (Act 3 — the audit)

---

## Cold open (0:00–0:45)

On screen: the executive summary of the July 2026 adversarial audit, slowly
scrolling. Read it aloud:

> "This project ships, works, and is visibly loved. It is also a
> three-platform product held together by hand-synchronized copies of the same
> logic, running on a single small database exposed to the public internet,
> behind security controls that fail open by design…"

Beat. Then:

> "An AI wrote that. About an app that AI helped me build. And I published it.
> Here's the whole story — the velocity, the mess, and the receipts."

Title card.

---

## Act 1 — The Build: one human, a relay of agents (0:45–4:30)

### What got built

- **Vox Quieta**: a conversational AI for spiritual encouragement — chat about
  life situations, get grounded answers with clickable Bible verse references.
- **Three platforms**: FastAPI + PostgreSQL/pgvector backend, Next.js web app,
  native Android (Kotlin/Jetpack Compose). Deployed on Azure via Terraform.
- **Multilingual**: EN, IT, DE, ES, FR, PT, AR string resources; multiple
  Bible translations (KJV, Luther 1912, Elberfelder 1871, …).
- Semantic scripture search (embeddings + hybrid HNSW SQL), multi-provider
  LLM fallback chain (Ollama local → Claude / OpenRouter).

### The headline numbers (from the productivity dashboard)

| Stat | Value |
|---|---|
| Calendar span | **166 days** (2026-01-18 → 2026-07-02) |
| Active days | **132 — 80% of all days** |
| Units of work landed on main | **610** (PRs + direct commits, release bumps excluded) |
| Code | **+126,470 / −20,956 lines** (net +105,514) |
| Releases | **67** |
| Pre-launch velocity | **5.14 units of work per active day** |

Narration beat: "Five PRs a day, sustained for months, by one person. That's
not typing speed. That's orchestration."

### How: the Plan → Build → Verify relay

The core workflow (documented in `AGENTS.md`, runnable as
`/plan-build-verify`):

1. **Plan — Opus** (strong model): explore the codebase, write an explicit
   per-file plan, create the backlog story, resolve ambiguity *before* coding.
2. **Build — Sonnet** (fast model): a subagent implements the approved plan —
   code, tests, migrations, i18n.
3. **Verify — Opus** (strong model again): a *separate fresh subagent* with no
   build context independently runs the test suites and reviews the diff
   against acceptance criteria.

Key insight to spell out on a slide:

> **Verification is the hardest reasoning step, so it gets the strongest
> model.** A cheap verifier rubber-stamps the very bugs it should catch. The
> independence comes from a fresh agent that actually runs the tests — not
> from model diversity.

Supporting practices worth a quick montage: every change ships with tests
(the repo holds ~43k test LOC across platforms), every change has a backlog
story (BITB-xxx), conventional commits + release-please automate the 67
releases, pre-commit + detect-secrets, delegation format docs so subagents
don't get blocked.

**B-roll**: terminal with the relay running; the PR list scrolling; the
architecture diagram from the README; the release timeline on the dashboard.

---

## Act 2 — The Reality: what the honest numbers say (4:30–8:00)

Transition: "Every AI-coding demo shows the velocity. Almost nobody shows the
other column. So I built a dashboard that computes it from git history —
stdlib-only Python, runs monthly in CI, publishes to GitHub Pages. I can't
quietly delete a bad month."

### The uncomfortable table (show the dashboard live)

| Stat | Value | What it means |
|---|---|---|
| fix : feat ratio | **1.88** | Nearly two fixes for every feature |
| Regression fixes (fix ≤7 days after related feat) | **158** | "Done" often wasn't done |
| Same-day hotfix releases | **24 of 67** | A third of releases chased the previous one within 24 h |
| Fix chains (≥2 fixes, same scope, ≤7-day gaps) | **24** | Bug whack-a-mole bursts |
| Churn ratio | **0.166** | 17% of all written code was later deleted or rewritten |
| Reverts | **2** | Full rollbacks stayed rare |

### Stories inside the numbers

- **The Android wall**: the single biggest fix chain is **34 Android fixes in
  three weeks** (Apr 27 → May 20) — right at launch. Android is the most
  bug-prone scope overall: 107 units, 59 of them fixes. Native mobile is where
  AI-generated velocity met device reality (16 KB page-size support, AGP
  upgrades, Play Store publishing…).
- **Launch pattern**: pre-launch fix:feat was 2.16; post-launch it *dropped*
  to 1.5. The system stabilized rather than collapsed — the opposite of the
  usual "demo rots after launch" story.
- **Hotspot files tell you where the pain lives**: `azure-deploy.yml` touched
  **74 times** (CI/CD is a codebase too, and it was the most-churned file in
  the repo), `api/config.py` 46×, seven parallel `strings.xml` locale files
  ~39× each — hand-synchronized translation cost made visible.
- **Monthly rhythm** (chart): January is 17 fixes vs 2 feats (bootstrap
  chaos), March is the feature peak (46 feats), April is the pre-launch
  hardening crunch (fix:feat 7.4), then the curve calms.

Narration beat: "None of this is an argument against AI-assisted development.
It's the *price list*. Velocity is real, and so is the rework tax — about one
line deleted for every six written."

**B-roll**: the interactive charts on the Pages site; zoom on the fix-chain
table; the hotspot bar chart.

---

## Act 3 — The Audit: turning the AI on itself (8:00–12:00)

Setup: "Metrics tell you *how much* got rebuilt. They don't tell you what's
quietly rotting. For that I gave the AI a different job description."

### The setup (great slide material)

- A `/risk-audit` slash command with a persona: **"Cynical Principal Software
  Architect & Adversarial Project Risk Auditor. Praise is rationed."**
- Four parallel read-only auditor subagents sweep api / frontend / android /
  infra; every CRITICAL/HIGH finding is hand re-verified against real
  file:line evidence — "nothing is speculative."
- Runs quarterly per a written playbook (`docs/AUDIT_PLAYBOOK.md`); reports
  are never overwritten, because *the diff between audits is the point*.

### The verdict: 47 findings — 2 CRITICAL, 15 HIGH, 24 MEDIUM, 6 LOW. Risk score 149.

Walk the top findings (each is a mini-story a dev audience will feel):

1. **The verse parser exists three times** — Kotlin, TypeScript, Python,
   synchronized by hand and by "mirrors the web" comments. The commit log
   proves the drift: PRs #799, #801, #804 are all drift repairs. The parity
   test only compares *entry counts* — contents can diverge silently.
2. **Sync HTTP inside async routes**: one feedback email during SMTP latency
   can freeze every concurrent chat on that backend replica for up to 10 s.
3. **The abuse-control stack fails open at every layer**: Turnstile returns
   "allow" on any exception, the rate limiter is per-process in-memory, the
   content-safety master switch defaults to off.
4. **The public search endpoint runs the exact full-scan query the hybrid
   path was rewritten to avoid** — on a 2-vCPU Postgres.
5. **A total LLM outage returns a generic 500 instead of the intended 503** —
   the one scenario the fallback chain was built for is the one it misreports.

Balance it — the audit also lists **load-bearing strengths** ("do not break
these while refactoring"): the hybrid-search CTE, the embedding resilience
layer (circuit breaker, jittered retry), a genuinely large test corpus
(a 2,370-line test file for verse extraction), production-grade DB pooling.

### The meta-punchline (don't skip this)

The audit initially hand-counted **36** findings. The real number was **47**.
So the count itself became code: `tools/audit-metrics/` parses every audit
report, fails CI if a finding is malformed, and tracks the risk score,
hotspot file sizes, and grep-based hygiene counters (sync clients, broad
excepts, TODOs, `.old`/`.backup` cruft) over time on the `/audit` dashboard.

> "Even the auditor gets audited. The tally is machine-verified because the
> first hand count was wrong by eleven."

**B-roll**: the audit markdown scrolling; the `/audit` dashboard trend tables;
the risk-score number card.

---

## Close — What I'd tell you to steal (12:00–14:00)

Five takeaways, one screen each:

1. **Make the strongest model the critic, not the author.** Verification is
   harder than generation. Fresh context + actually running the tests beats
   model diversity.
2. **Instrument honesty.** A monthly CI job that computes fix:feat, churn,
   and hotfix counts from git history costs ~an afternoon and removes the
   option of lying to yourself. (Stdlib-only; steal `tools/repo-metrics/`.)
3. **Schedule adversarial audits with a persona that's paid to be mean.**
   "Praise is rationed" produced findings a friendly review never would.
   Never overwrite old reports — trend is the product.
4. **AI velocity has a shape**: ~2 fixes per feature, ~17% churn, and native
   mobile is where it hurts most. Budget for the rework tax instead of being
   surprised by it.
5. **Publish the warts.** The dashboards and the audit are public. That's not
   humility theater — public numbers are the only ones that stay honest.

Final line:

> "The app helps people find encouraging words. The repo, it turns out, needed
> a truth-teller. Ship with both."

CTA: links to the two dashboards, the audit report, and the repo tools.

---

## YouTube chapter plan (≈13–14 min)

| Time | Chapter |
|---|---|
| 0:00 | Cold open: the AI's verdict on its own app |
| 0:45 | What Vox Quieta is (30-second product demo) |
| 1:15 | 610 PRs in 166 days: the headline numbers |
| 2:15 | The Plan→Build→Verify agent relay |
| 4:30 | The dashboard that can't lie: fix:feat 1.88, 17% churn |
| 6:00 | The Android wall: 34 fixes in three weeks |
| 7:15 | Hotspots: the CI file touched 74 times |
| 8:00 | /risk-audit: hiring a cynical AI architect |
| 9:00 | The top 5 findings (with receipts) |
| 10:45 | What the audit praised |
| 11:20 | The count was wrong: auditing the auditor |
| 12:00 | Five things to steal |
| 13:30 | Where to find everything |

## Conference-talk adaptation (~20 min, slide skeleton)

1. Title: *"610 PRs, 47 Findings: An Honest Autopsy of AI-Assisted
   Development"*
2. The product in one slide (architecture diagram)
3. The constraint: one person, three platforms, six months
4. The relay: Plan (Opus) → Build (Sonnet) → Verify (Opus) — why the critic
   gets the strongest model
5. Headline velocity numbers
6. The other column: fix:feat, regressions, hotfix releases, churn
7. Case study: the Android fix chain
8. Case study: hotspot files (`azure-deploy.yml` ×74, seven `strings.xml`)
9. Enter the adversary: the /risk-audit persona + playbook
10. Top 5 findings (one slide each, file:line receipts) — 5 slides
11. Load-bearing strengths — what an adversarial audit still respects
12. Auditing the auditor: 36 → 47, machine-verified tallies, trend dashboard
13. The five takeaways
14. Links / Q&A

Talk-title alternatives:
- *"The AI Wrote It. The AI Audited It. I Published Both."*
- *"Velocity Has a Price List: Metrics From 6 Months of Agent-Driven Development"*

## Derived LinkedIn/blog post (skeleton)

- **Hook** (2 lines): "I let the AI that helped build my app write a brutal
  audit of it. Then I published the audit. Here's what six months of
  agent-driven development actually looks like in numbers."
- **The build**: 3 platforms, 166 days, 610 units of work, 67 releases —
  one person + a Plan→Build→Verify model relay.
- **The honest column**: fix:feat 1.88 · 158 regression fixes · 24 same-day
  hotfixes · 17% churn. "Velocity is real. So is the rework tax."
- **The audit**: 47 findings, 2 critical — triple-maintained parser,
  fail-open security, the 500-instead-of-503. One-line each.
- **The meta**: the tally is machine-verified because the hand count was
  wrong; dashboards regenerate monthly in CI.
- **3 takeaways** (condensed from the five) + links to both dashboards.
- Suggested hashtags: #AIEngineering #DevEx #SoftwareArchitecture
  #BuildInPublic #ClaudeCode

## Video title & thumbnail options

- "One Dev + AI Agents Built a 3-Platform App — Then the AI Audited It"
  (thumbnail: risk score **149** stamped over the app UI)
- "6 Months of AI-Driven Development: The Numbers Nobody Shows"
  (thumbnail: **fix:feat 1.88** big, split-screen velocity chart vs audit page)
- "My AI Code Auditor Found 47 Problems (2 Critical) — I Published Them All"
  (thumbnail: red CRITICAL banner over the audit heading)

## Fact sources (for on-screen citations)

| Claim | Source |
|---|---|
| 610 units, 166 days, 80% active, +126k/−21k LOC, 67 releases | `docs/metrics/report.md` (2026-07-03 snapshot) |
| fix:feat 1.88, 158 regressions, 24 hotfixes, 24 fix chains, churn 0.166 | same |
| Android chain of 34 fixes; scope bug table; hotspot files | same |
| 47 findings / 2C·15H·24M·6L / risk score 149 | `docs/audits/2026-07-adversarial-audit.md` + `docs/audits/metrics/report.md` (2026-07-05) |
| Top-5 risks, load-bearing strengths, persona & method | `docs/audits/2026-07-adversarial-audit.md` |
| Relay workflow & rationale | `AGENTS.md`, `.claude/commands/plan-build-verify.md` |
| Audit cadence & "never overwrite reports" | `docs/AUDIT_PLAYBOOK.md` |
| 36→47 correction, machine-verified tally | audit exec summary + `tools/audit-metrics/README.md` |
