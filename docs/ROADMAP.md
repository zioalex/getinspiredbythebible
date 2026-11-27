# Product Roadmap

What Vox Quieta ships next, as product releases. Each release is a GitHub milestone titled
`R<n>: <outcome>` that states what changes for users and how we know it is done
(docs/RELEASE_PROCESS.md, "Product releases (milestones)"). The stories behind it carry
`milestone: R<n>` in their front matter (docs/backlog/LEGEND.md).

**Last updated:** 2026-11-27 (BITB-367; replaces the February 2026 M1–M6 plan).

---

## Vision

Vox Quieta helps people find spiritual encouragement and relevant
scripture based on their life situations through:

- **Natural conversation**: Ask questions in your own words, get biblically-grounded responses
- **Semantic scripture search**: Find verses by meaning, not just keywords
- **Multi-platform access**: Web app (live), Android app (in development)
- **Privacy-first**: No user tracking, minimal data collection, open source

---

## Now — R1: Safe and secure chat

**Outcome:** a person in distress gets a safe answer in all 11 languages even when a moderation
provider fails, and the public API does not leak data or let others spend what they should not.

**Done when:**

- Llama Guard returns content again instead of failing over on every call (BITB-321, fix)
- The OpenAI moderation failover is live in production (BITB-288, nfr)
- Azure Content Safety is provisioned as the next hop (BITB-294, nfr)
- The keyword fallback catches the missing suicidal phrasings (BITB-203, BITB-204, fix)
- Telemetry endpoints have their own rate limit (BITB-310, nfr) and `/health/ready` stops
  echoing database errors (BITB-317, nfr)
- The safety golden sets pass in all 11 languages (BITB-293, BITB-322: the evidence)

Live list: `make backlog ARGS="list --milestone R1"` · draft notes: `make release-notes ARGS="--milestone R1"`.

## Next — R2: Smoother chat on web and Android

**Outcome:** switching language, reading aloud and search landing pages behave the way users
expect.

- Changing the UI language starts a new chat on web and Android (BITB-331, BITB-334, fix)
- Android read aloud no longer stays paused when the speech engine never starts (BITB-252, fix)
- Headings, descriptions, the localized 404 and sitemap dates are right (BITB-300, fix)

## Later

Not yet in a release. Candidates are picked into the next milestone when R1 ships; query them by
kind instead of keeping a second list here:

- `make backlog ARGS="list --kind feature"`: e.g. topic landing pages (BITB-301), chapter pages
  (BITB-302), verse of the day (BITB-303), ask by voice (BITB-120), iOS (BITB-085/087/088)
- `make backlog ARGS="list --kind nfr --priority P0,P1"`: security, privacy and reliability work
- `make backlog ARGS="list --priority icebox"`: ideas with no timeline

---

## Success Metrics (Product-Level)

### User Engagement

- **Target:** 1000+ weekly active users by end of Q2 2026
- **Target:** 70%+ user retention (return within 7 days)
- **Target:** Average 3+ messages per session

### Quality

- **Target:** 99.9% uptime (web app)
- **Target:** <1% error rate on API endpoints
- **Target:** <5% crash rate (Android app)

### Performance

- **Target:** <2s time to first response
- **Target:** <500ms p95 API latency

### User Satisfaction

- **Target:** 4+ star rating on Play Store
- **Target:** <10% bounce rate on web app
- **Target:** Positive user feedback (qualitative)

---

## How This Roadmap Is Maintained

1. When a release ships, its milestone closes automatically (release-please.yml, product-notes
   job). Move **Next** to **Now**, pick the following milestone, and update this file in the same PR
   that creates the new milestone.
2. Stories (`docs/BACKLOG_STORIES/`, `make backlog`) are the source of truth for scope; this file
   only names the outcome and the stories that prove it.
3. A story joins a release by setting `milestone: R<n>`; the PR that implements it then gets the
   GitHub milestone automatically (pr-kind.yml, BITB-366).
