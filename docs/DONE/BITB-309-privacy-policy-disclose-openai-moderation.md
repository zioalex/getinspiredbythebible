---
id: BITB-309
status: done
priority: P1
size: S
rank: 130
created: 2026-11-11
prs: [1287]
---

# BITB-309: Privacy Policy — Disclose OpenAI Moderation and State Provider Retention Honestly

**Migration note (2026-11-13, status):** PR #1287, merged 2026-11-11
**Migration note (2026-11-13, priority):** (blocks merging BITB-288 / PR #1280)
**Prompted by:** BITB-288 owner step "confirm OpenAI's data retention is acceptable".

## Problem

BITB-272 slice 1 made `ml_only` content safety fail over to the OpenAI Moderation API
(`omni-moderation-latest`, `api/providers/openai_moderation.py`) whenever Llama Guard is
unavailable. BITB-288 (PR #1280) wires `OPENAI_API_KEY` into production; the owner has
added the repo secret, so the failover goes live as soon as #1280 merges and deploys.
From then on, user message text can reach **OpenAI** (OpenAI, L.L.C. — not Azure OpenAI,
which is Microsoft's service under a different contract).

The privacy policy (`frontend/public/legal/privacy-policy*.md`, 11 languages) does not
match that:

1. **OpenAI is not listed** as a processor — neither in *How Your Messages Are Processed
   by AI* nor in the *Third-Party Services* table. Only OpenRouter and Azure OpenAI
   (Microsoft) are named.
2. **The retention claim is wrong for OpenAI.** The policy says message text "is not
   retained by the provider beyond what is needed to service the request". OpenAI keeps
   abuse-monitoring logs of all API traffic for **up to 30 days** by default (Zero Data
   Retention needs prior OpenAI approval, which we don't have). OpenAI does not train on
   API data by default, so the "not used for training" claim stays true.

## User story

As a user of Vox Quieta, I want the privacy policy to name every company that receives my
message text and say truthfully how long they may keep it, so I can decide whether to use
the app.

## Decisions (owner, 2026-11-11)

- **Sequencing:** a separate PR, merged before (or together with) #1280, so the notice is
  live before any data reaches OpenAI.
- **Wording:** per-provider and honest. Keep "no training, no advertising, never sold" for
  all providers; state that OpenAI may keep message text it receives for up to 30 days for
  abuse monitoring and then deletes it; for the other providers, refer to their own
  (linked) policies instead of claiming no retention.

## Functional requirements

In **all 11** policy files (en base + it, de, es, fr, pt, ar, ru, zh, hi, ko):

1. *How Your Messages Are Processed by AI*: add an **OpenAI** bullet — receives message
   text only when the primary safety check (Llama Guard) is temporarily unavailable, to
   screen it for safety (OpenAI Moderation).
2. Replace the "not retained by the provider beyond what is needed" clause with
   per-provider retention: OpenAI may keep it up to 30 days for abuse monitoring, then it
   is deleted unless the law requires longer; other providers per their own policies.
3. Add OpenAI's privacy link (`https://openai.com/enterprise-privacy/` — the page covering
   API data) next to the OpenRouter and Microsoft links, in the *Third-Party Services*
   table, and in the *Your Rights* sentence that points to the AI providers' policies.
4. Bump the `lastUpdated` frontmatter and the visible "Last updated" date to 2026-11-11 in
   every language (localized date format kept as each file already has it).
5. Update `docs/android/play-console-compliance.md` so the processor list includes OpenAI.

## Non-functional requirements

- Translations are faithful and natural in each language; RTL (ar) and Devanagari (hi)
  render as before; Markdown tables stay well-formed.
- No code or runtime change; Android loads the web policy, so no app release is needed.

## Acceptance criteria

- [x] All 11 files name OpenAI with the fallback-only purpose and link its privacy page.
- [x] No file still claims providers keep nothing beyond the request; each states OpenAI's
      30-day abuse-monitoring retention.
- [x] `lastUpdated: 2026-11-11` in every file.
- [x] Vitest test in `frontend/src/test/legal-pages.test.tsx`, parametrized over all 11
      locales, asserts the above.
- [x] Owner: merge this before PR #1280 (#1287 merged 2026-11-11).
- [ ] Owner: in Play Console → Data safety, confirm the form still matches (data shared
      with AI processors for app functionality / safety); no new data type is collected.

## Out of scope

- Azure Content Safety as a second failover hop (BITB-292, PR #1282) — it needs its own
  disclosure when it is enabled in production (BITB-294).
- Applying for OpenAI Zero Data Retention.
- Terms of Service changes.

## Follow-ups

None. The Play Console Data safety re-check is an owner-only step and stays above as an
unticked acceptance criterion.
