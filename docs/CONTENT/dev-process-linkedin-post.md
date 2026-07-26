# LinkedIn Post — full text

Paste-ready. ~2,600 characters, well under LinkedIn's 3,000 limit.
Suggested media: side-by-side screenshot of the two dashboards, or a
short screen-capture clip scrolling them.

---

I let the AI that helped build my app write a brutal audit of it.
Then I published the audit.

Over six months of nights and weekends I built Vox Quieta — a
conversational Bible-encouragement app with a FastAPI backend, a Next.js
web app, and a native Android app. One person, three platforms.

Except "one person" isn't accurate. The git history keeps receipts:
~65% of commits carry an AI co-author trailer. Claude Opus 4.5 alone
signed 168 commits. An opencode orchestrator (Claude Opus 4.6 via GitHub
Copilot) delegated the Android app to subagents running MiniMax M2.5 and
Qwen3-Coder — 77 commits under the alias "Android Dev". GitHub Copilot's
coding agent co-authored ~50 more. There is exactly one commit from
Moonshot's Kimi K2.5, preserved like a fossil.

The default workflow, written down in AGENTS.md: Plan (Opus) → Build
(Sonnet) → Verify (a *fresh* Opus agent that actually runs the tests).
The strongest model is the critic, not the author — a cheap verifier
rubber-stamps exactly the bugs it should catch.

The velocity was real:
• 610 units of work on main in 166 days (active on 80% of them)
• 67 releases, +126k lines of code

But I also built a dashboard that recomputes the honest column from git
history every month, in CI, published publicly — so I can't hide a bad
month:
• 1.88 fixes per feature
• 158 regression fixes within a week of the related feature
• 24 of 67 releases were same-day hotfixes
• 17% of all code written was later deleted or rewritten

Then I gave the AI a different job: a quarterly adversarial audit with
the persona "Cynical Principal Software Architect. Praise is rationed."

Verdict: 47 findings, 2 critical. The verse parser existed three times
(Kotlin, TypeScript, Python), drifting exactly as predicted. The
abuse-control stack failed open at every layer. The one outage scenario
the fallback chain was built for was the one it misreported.

The kicker: the audit's first hand-count said 36 findings. It was 47.
So now the counting is code too — a parser validates every audit report
in CI and publishes the risk-score trend. Even the auditor gets audited.

What I'd tell you to steal:

1. Strongest model verifies; fresh context; real test runs.
2. Instrument honesty — an afternoon of Python ends self-deception.
3. Schedule an adversary. Keep every old report; the trend is the product.
4. Budget the rework tax (~2 fixes/feature, ~17% churn). Native mobile
   hurts most.
5. Publish the warts. Public numbers are the only honest numbers.

Both dashboards and the full audit are public — links in the comments.

\#AIEngineering #DevEx #BuildInPublic #SoftwareArchitecture #ClaudeCode

---

**First comment (post immediately after publishing):**

📊 Productivity dashboard: <https://zioalex.github.io/getinspiredbythebible/>
🔍 Audit trends: <https://zioalex.github.io/getinspiredbythebible/audit>
📁 Repo & tools: <https://github.com/zioalex/getinspiredbythebible>
🎥 Full video: [add YouTube link]
