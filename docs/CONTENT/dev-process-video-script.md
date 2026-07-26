# Video Script — "The AI Wrote It. The AI Audited It. I Published Both."

<!-- markdownlint-disable MD036 -- **[VISUAL: ...]** lines are intentional edit-direction callouts, not headings -->

Word-for-word narration for the YouTube long-form video (~14–15 min at a
natural pace). **[VISUAL: …]** lines are edit directions, not narration.
Adapt freely — contractions and small ad-libs make it sound human.

---

## COLD OPEN (0:00–0:50)

**[VISUAL: black screen. The audit's executive summary types out line by
line, terminal-style. Low ambient music.]**

> "This project ships, works, and is visibly loved."

Sounds nice, right? Keep reading.

> "It is also a three-platform product held together by hand-synchronized
> copies of the same logic… running on a single small database exposed to
> the public internet… behind security controls that fail open by design…
> gated by CI tiers that are deliberately allowed to fail."

**[VISUAL: cut to presenter / voiceover continues over the audit page.]**

An AI wrote that paragraph. About an app that AI helped me build. I didn't
soften it, and I didn't hide it — I published it, on the project's own
website, next to a dashboard that recalculates my productivity metrics every
month whether I like the numbers or not.

This is the story of six months of AI-assisted development — the velocity
everyone shows you, the mess almost nobody shows you, and what happened when
I turned the AI on its own code.

**[VISUAL: title card — "The AI Wrote It. The AI Audited It. I Published Both."]**

---

## ACT 1 — THE BUILD (0:50–5:00)

### The product (0:50–1:30)

**[VISUAL: 20-second app demo — chat, verse links opening, language switch.]**

First, what we're talking about. The app is called Vox Quieta. You chat
about whatever you're going through, and it answers with grounded
encouragement — and every Bible reference in the answer becomes a link to
the actual text, in your language, in your preferred translation.

Under the hood that's a FastAPI backend with Postgres and pgvector for
semantic verse search, a Next.js web app, and a native Android app in
Kotlin and Jetpack Compose. Deployed on Azure with Terraform. Seven
interface languages. Multiple Bible translations.

**[VISUAL: architecture diagram from the README.]**

And here's the constraint that makes this interesting: one person. Nights
and weekends. No team.

### The numbers (1:30–2:30)

**[VISUAL: the productivity dashboard — headline cards animating in.]**

The repo has a dashboard that mines its own git history, so these aren't
vibes — they're computed. From January 18th to early July: **166 days**. I
committed on **132 of them** — that's 80% of all days, including Christmas
season, including workdays.

**610 units of work** landed on main — that's merged PRs, with release-bot
noise excluded. **67 releases**. About **126,000 lines of code added**,
21,000 deleted. Pre-launch velocity: **just over five PRs per active day**.

Five PRs a day, for months, from one person. That is not typing speed.
That's orchestration. So let me show you the org chart.

### The roster: which models actually did the work (2:30–4:00)

**[VISUAL: table of co-author trailers, counts animating up.]**

Every commit in this repo carries a co-author trailer, so we can literally
count who did what. About **two-thirds of all human-initiated commits have
an AI co-author on record** — and the early ones under-report, because I
wasn't adding trailers yet.

The roster, straight from git log: **Claude Opus 4.5** is the single
biggest named contributor — 168 commits — plus almost 300 more from Claude
Code sessions that didn't sign a version. **Claude Opus 4.6**, 56.
**Claude Sonnet**, about 20. **GitHub Copilot's coding agent** co-authored
nearly 50. There are 77 commits signed by an alias called "Android Dev" —
I'll come back to that one. And there is exactly **one commit from Moonshot's
Kimi K2.5**, preserved forever in the record like a fossil.

**[VISUAL: three logos/cards — Claude Code, opencode, GitHub Copilot.]**

Those models were driven by **three different harnesses**, and the git
history shows three distinct eras.

**Era one, January and February — Claude Code with Opus 4.5.** Backend,
frontend, first Azure deploy. The bootstrap phase.

**Era two, March — the opencode experiment.** This one's fun. I set up an
opencode configuration with a full org chart: an **orchestrator agent
running Claude Opus 4.6 through GitHub Copilot**, which plans, delegates,
and verifies — and, I quote from its own config, "can self-improve by
updating AGENTS.md and opencode.json." Its worker agents ran on
deliberately cheap models — **MiniMax M2.5 on a free tier, Qwen3-Coder via
OpenRouter, and local Qwen3 on Ollama**. That "Android Dev" alias with 77
commits? Those are opencode's subagents, building most of the Android app.
An expensive model managing free models. It worked — mostly. Hold that
thought for Act 2.

**Era three, April onward — the Claude Code relay.** This became the
default operating procedure, written down in AGENTS.md.

### The relay (4:00–5:00)

**[VISUAL: three-stage diagram: Plan (Opus) → Build (Sonnet) → Verify (Opus).]**

Every non-trivial task runs as a three-stage relay. **Plan** — the
strongest model, Opus, explores the codebase and writes an explicit
per-file plan, and files a backlog story. **Build** — a faster, cheaper
model, Sonnet, implements that plan: code, tests, migrations, translations.
**Verify** — and this is the part I'd tattoo on every AI workflow — a
**separate, fresh Opus agent with no memory of the build** independently
runs the test suites and reviews the diff against the acceptance criteria.

Why spend the expensive model on checking instead of writing? Because
verification is the hardest reasoning step. A cheap verifier rubber-stamps
exactly the bugs it should catch. And the independence doesn't come from
using a different brand of model — it comes from a fresh agent that
actually runs the tests.

So: 610 PRs, 67 releases, three platforms, six months. Sounds like the
demos, right? Okay. Now the part the demos don't show.

---

## ACT 2 — THE REALITY (5:00–9:30)

### The dashboard that can't lie (5:00–5:45)

**[VISUAL: scrolling the live dashboard at zioalex.github.io/getinspiredbythebible.]**

Every AI-coding video shows you the velocity column. Almost nobody shows
the other column. So I built a tool that computes it — plain Python, no
dependencies, reads nothing but git history and the changelog. It runs
monthly in CI and publishes to GitHub Pages automatically. Which means I
cannot quietly delete a bad month. The link is in the description; go check
my numbers while I read them to you.

### The uncomfortable numbers (5:45–7:00)

**[VISUAL: each stat lands as a full-screen card.]**

For every feature I shipped, I shipped **1.88 fixes**. **158 fixes** landed
within a week of a related feature — meaning "done" frequently wasn't done.
Of my 67 releases, **24 were same-day hotfixes** — a third of my releases
were chasing the release before them. And **17% of every line written was
later deleted or rewritten**. That's the churn tax: for every six lines the
AI and I wrote, one was rework.

Is that bad? Honestly — I don't think so. Two reverts in six months, and
the fix-to-feature ratio *improved* after launch, from 2.16 down to 1.5.
The system stabilized instead of rotting. But it's a price list, and nobody
shows you the price list.

### Where it hurt (7:00–8:30)

**[VISUAL: the fix-chains table, android row highlighted.]**

The dashboard also shows exactly *where* the pain concentrated, and there's
a lesson in it. The single worst stretch: **34 Android fixes in three
weeks**, right at launch. Remember the opencode experiment — the cheap
subagents that built most of the Android app at incredible speed? Android
is also the most bug-prone scope in the entire project: 107 units of work,
59 of them fixes. Native mobile is where AI velocity met device reality:
Play Store policies, page-size requirements, Gradle plugin upgrades. The
speed was real. So was the bill.

**[VISUAL: hotspot files bar chart.]**

And my favorite chart: the most-touched file in the repository is not
application code. It's the **Azure deploy workflow — modified 74 times**.
Your CI/CD pipeline is a codebase, whether you admit it or not. Second
place cluster: seven translation files, hand-synchronized across seven
locales, about 39 touches each. Every hand-synchronized copy showed up
later as a bug factory — remember that phrase for Act 3.

### What actually moved the needle (8:30–9:30)

**[VISUAL: timeline — process-change markers dropped onto the monthly
fix-to-feature curve: Jan 8.5 → Feb 2.17 → Mar 1.26 → Apr 7.4 → May 1.37.]**

Now, because every process change has a date in git, we can ask the real
question: which change actually helped, and which one hurt? Correlation,
not proof — but the curve is blunt.

The biggest single improvement in six months came from the cheapest thing
in the repo: **a markdown rules file, written on day three**. January,
before it settled in: eight and a half fixes per feature. February, first
full month with structured agent rules: 2.2. Nothing else in the entire
history — no model upgrade, no harness switch — moved the number that much.

The most expensive decision is also visible: **March's opencode experiment**
was the fastest month on record *and* generated the Android bug wall that
dominated April and May. The "Android Dev" commits vanish after March —
though, credit where due, the config was still being extended in late May.
The bill for cheap velocity arrived about four weeks later — which is
exactly why one good month proves nothing.

And here's a confession that I think matters: the Plan→Build→Verify relay —
the thing everyone asks me about — **shows no improvement in these charts**.
June was slightly worse than May. I still believe in it, because its wins
happen *before* merge, where a merged-history dashboard is blind by
construction. But I won't claim a win my own data doesn't show. That's the
whole point of building the dashboard.

---

## ACT 3 — THE AUDIT (9:30–13:15)

### Hiring a cynic (9:30–10:15)

**[VISUAL: the /risk-audit command file; the persona line highlighted.]**

Metrics tell you how much got rebuilt. They can't tell you what's quietly
rotting. So I gave the AI a different job description. There's a slash
command in this repo called `/risk-audit`, and its persona is, verbatim:
**"Cynical Principal Software Architect and Adversarial Project Risk
Auditor. Praise is rationed."**

It runs quarterly, by written playbook. Four auditor agents sweep the
backend, frontend, Android, and infrastructure in parallel — read-only —
and every critical finding must cite a file and line number that was
actually read. Old reports are never overwritten, because the diff between
audits is the point.

### The verdict (10:15–12:00)

**[VISUAL: "47 findings — 2 CRITICAL · 15 HIGH · 24 MEDIUM · 6 LOW — risk score 149" stamped across the screen.]**

July 2026 verdict: **47 findings. Two critical.** Let me give you the top
three, because each one is a lesson I paid for.

**One. The verse parser exists three times.** Kotlin, TypeScript, Python —
three implementations of the same logic, synchronized by hand and by
comments that say "mirrors the web version". The audit didn't speculate
that this would drift — it pointed at three merged PRs that were *already*
drift repairs. And the parity test only compares entry counts, so contents
can diverge silently. Every hand-synchronized copy becomes a bug factory.
Told you to remember that phrase.

**Two. The abuse-control stack failed open at every layer.** Bot
verification returned "allow" on any exception. The rate limiter lived
in-memory, per process — so it forgot everything on every restart and only
half-worked with two replicas. And the content-safety master switch
defaulted to *off*. For a pastoral-care app that screens self-harm content,
that finding hurt to read. It was also correct — and it's since been fixed,
with the fail-closed behavior now covered by tests.

**Three. The one scenario the resilience code was built for was the one it
misreported.** Total LLM outage should return a proper 503. Instead:
generic 500s — because the error handler matched a string the provider
never actually emits. The fallback chain worked; its failure reporting was
fiction.

**[VISUAL: "Load-bearing strengths" section of the audit.]**

And to be fair — the cynic also lists what it calls *load-bearing
strengths*, the things it says must not be broken while fixing the rest:
the hybrid search SQL, the embedding circuit-breaker layer, a genuinely
serious test corpus — there's a single test file for verse extraction
that's 2,370 lines long. An adversarial audit that still finds five things
to respect is more credible on both ends.

### Auditing the auditor (12:00–13:15)

**[VISUAL: audit exec summary: "Corrected from an initial hand-count of 36".]**

Now the meta-punchline, and my favorite fact in this whole project. The
audit's first executive summary said **36 findings**. The real count was
**47**. The AI auditor miscounted its own findings by eleven.

So now the counting is code too. A second tool parses every audit report,
fails CI if a finding is malformed, and tracks the weighted risk score,
the size of every flagged monolith file, and grep-based hygiene counters
on a public trend dashboard. Even the auditor gets audited.

**[VISUAL: quick cut, conspiratorial tone.]**

Oh — and one more confession, because it's too perfect. The dashboard
section that attributes commits to specific AI models? It was built, it was
reviewed, the PR says "merged"… into a stacked branch whose base had
already merged. It never reached main. The analysis of the AI's work was
lost to an AI-workflow mistake, and the numbers survived only because the
PR description wrote them down. If you've ever mis-merged a stacked PR:
you're in good company. The machines are too.

---

## CLOSE — WHAT TO STEAL (13:15–14:45)

**[VISUAL: five cards, one per point.]**

If you take five things from these six months, take these.

**One — make your strongest model the critic, not the author.** Fresh
context, real test runs. Checking is harder than writing.

**Two — instrument honesty.** One afternoon of plain Python plus a monthly
CI job removes your ability to lie to yourself. Both tools are in the repo;
steal them.

**Three — schedule an adversary.** A friendly review would never have
written "praise is rationed" findings. Keep every old report; the trend is
the product.

**Four — budget the rework tax.** Two fixes per feature, 17% churn, and
native mobile pain — that's roughly the shape of AI velocity. Plan for it
and it's fine. Be surprised by it and it looks like failure.

**Five — publish the warts.** These dashboards are public not because I'm
brave, but because public numbers are the only numbers that stay honest.

**[VISUAL: app on one side, audit page on the other.]**

The app exists to give people encouraging words backed by an honest source.
Turns out the repo needed the same thing. Ship with both.

Links to the dashboards, the full audit, and every tool are in the
description. If you've run your own adversarial audit — or been personally
victimized by a stacked PR — tell me in the comments. See you in the next
one.

**[VISUAL: end card — dashboard URL + repo URL.]**

---

## Description-box copy (paste-ready)

One developer + a relay of AI agents (Claude Code, opencode, GitHub
Copilot) built a three-platform AI app in six months — then an AI
adversarial audit tore it apart, and every number was published.

📊 Productivity dashboard: <https://zioalex.github.io/getinspiredbythebible/>
🔍 Audit trend dashboard: <https://zioalex.github.io/getinspiredbythebible/audit>
📁 Repo (tools in tools/repo-metrics & tools/audit-metrics):
<https://github.com/zioalex/getinspiredbythebible>

Chapters:
0:00 The AI's verdict on its own app
0:50 What Vox Quieta is
1:30 610 PRs in 166 days
2:30 The roster: Opus, Sonnet, Copilot, MiniMax, Qwen, one Kimi commit
4:00 Plan → Build → Verify: why the strongest model verifies
5:00 The dashboard that can't lie
5:45 fix:feat 1.88, 17% churn, 24 same-day hotfixes
7:00 The Android wall & the CI file touched 74 times
8:30 What moved the needle: the day-3 rules file vs the harness switch
9:30 Hiring a cynical AI auditor
10:15 47 findings, 2 critical: the top three
12:00 The auditor miscounted — auditing the auditor
13:15 Five things to steal
