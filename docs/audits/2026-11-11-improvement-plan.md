# Improvement Plan — 2026-11-11

**Goal:** stop the cheapest ways this project can be abused or silently break, then spend
the effort on what makes it findable and useful to people looking for scripture.

**Evidence:** every problem statement below is backed by a row in
[2026-11-11-verified-review.md](2026-11-11-verified-review.md) (IDs `R…`, `D…`, `S…`,
`P…`). If a row and a story disagree, the review wins — fix the story.

**Audience:** any model or person picking up one story with no memory of the session that
wrote this. Each story file is a self-contained brief.

## 1. What was found, in one paragraph

Two production defects are live today: a forged `X-Forwarded-For` header passes the
"local only" gate on `api.voxquieta.org/health` (and with it every per-IP rate limit is
client-controlled), and the Arabic share image returns `503`. The chat endpoint accepts
forged `system` turns and megabyte-sized history. Search and email endpoints have no rate
limit. Production runs a Python version CI never tests. On the product side the site
exposes 66 URLs to search engines and no scripture at all, so people searching for
"Bible verses about anxiety" in any of the 11 languages cannot find it.

## 2. Stories and order

| Wave | Story | Title | Pri | Size | Depends on | Touches |
|---|---|---|---|---|---|---|
| 1 | [BITB-296](../BACKLOG_STORIES/BITB-296-chat-history-validation.md) | Validate and bound client-supplied chat history | P0 | S | — | `api/chat/service.py`, `api/main.py` |
| 1 | [BITB-297](../BACKLOG_STORIES/BITB-297-trusted-client-ip.md) | Trusted client IP; close the local-only bypass | P0 | M | — | `api/utils/` |
| 1 | [BITB-298](../BACKLOG_STORIES/BITB-298-guard-cost-endpoints.md) | Rate-limit search, feedback and church endpoints; bound their inputs | P0 | S | 297 (merge order) | `api/routes/`, `api/feedback/models.py` |
| 2 | [BITB-299](../BACKLOG_STORIES/BITB-299-share-image-arabic-hindi.md) | Share image: Arabic 503 and Hindi shaping | P1 | S | — | `frontend/src/app/[locale]/opengraph-image.tsx` |
| 2 | [BITB-300](../BACKLOG_STORIES/BITB-300-seo-on-page-fixes.md) | SEO on-page fixes | P1 | S | — | `frontend/src/lib/seo.ts`, pages, `messages/` |
| 2 | [BITB-304](../BACKLOG_STORIES/BITB-304-runtime-and-model-alignment.md) | Align Python runtime; fix Claude model config; model-existence probe | P1 | S | — | `api/Dockerfile`, CI, `api/providers/` |
| 3 | [BITB-301](../BACKLOG_STORIES/BITB-301-topic-landing-pages.md) | Topic landing pages in 11 languages | P1 | L | 300 | `frontend/` (no API change) |
| 3 | [BITB-302](../BACKLOG_STORIES/BITB-302-bible-chapter-pages.md) | Server-rendered Bible chapter pages (verses by anchor) | P1 | L | 300; ships KJV-only until licences are recorded | `frontend/` |
| 4 | [BITB-303](../BACKLOG_STORIES/BITB-303-verse-of-the-day.md) | Verse of the Day page, archive and feed | P2 | M | 301 | `frontend/` |
| any | [BITB-305](../BACKLOG_STORIES/BITB-305-secrets-inventory-and-restore-drill.md) | Secrets-expiry inventory, restore drill, retirement dates | P1 | M | owner access | `docs/`, one workflow |
| any | [BITB-306](../BACKLOG_STORIES/BITB-306-roadmap-refresh-and-backlog-archive.md) | Refresh the roadmap; archive done backlog entries | P2 | S | — | `docs/` |
| any | [BITB-307](../BACKLOG_STORIES/BITB-307-info-disclosure-and-telemetry-hygiene.md) | Trim `/config`, error text, metric labels, CORS | P2 | S | — | `api/main.py`, `api/routes/chat.py` |

Already tracked elsewhere and **not** duplicated here: private database networking
(BITB-005), the single verse grammar (BITB-059), Android session limit from `/config`
(BITB-156, which also carries the trusted-proxy acceptance criterion that BITB-297 now
satisfies).

### Merge order and conflicts

- **297 before 298.** Both edit `api/utils/security.py`; 298's limits are only meaningful
  once the client IP is trustworthy.
- **296 is independent** of 297/298 and can be built in parallel.
- **300 before 301 and 302.** The page stories reuse the metadata helper and the heading
  conventions that 300 settles.
- **299, 304, 305, 306, 307** conflict with nothing above.
- Every story adds one line to the `docs/BACKLOG.md` changelog. That file conflicts
  easily: rebase on `origin/main` immediately before opening the PR.

## 3. How to pick up a story

1. `git fetch origin && git worktree add "${WORKSPACE_DIR:-/tmp}/worktrees/bitb-NNN" -b claude/bitb-NNN-<slug> origin/main`
2. Check nobody is already building it: list open PRs and search their titles for `BITB-NNN`.
3. Read, in this order: the story file, the review rows it cites, `AGENTS.md`
   (*Standard Workflow*, *Testing*, *Git Conventions*, *Backlog Hygiene*).
4. **Re-verify the evidence before changing anything.** Line numbers were correct on
   `f058cad`; code moves. If the cited code no longer shows the problem, stop and report
   that in the PR instead of building.
5. Follow the repo relay: the story file is the spec; write the plan against the current
   code; Sonnet builds; a fresh Opus verifier runs the suites.
6. Each story lists **Decisions already made**. Do not reopen them and do not stop to ask:
   build the stated default. Anything listed under **Owner steps** is not yours to do —
   leave the checkbox unticked.
7. Ship tests with the change (the story lists the minimum set). For anything touching
   verse references or scripture text, the 11-language rule in `AGENTS.md` applies.
8. Commit type: `fix:` or `feat:` for anything a user can see; see the story's
   **Commit** line.
9. Open the PR, set the story status to `🔍 In Review` with the PR number, add one
   changelog line. When it merges, set `✅ Done`, move the story file to `docs/DONE/`,
   and file follow-up stories for anything the PR deliberately left out.

### Commands every story uses

```bash
# backend
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r api/requirements.txt -r api/requirements-dev.txt
cd api && ../.venv/bin/python -m pytest tests/ -x -q
# frontend
cd frontend && npm ci && npx vitest run && npm run lint && npx tsc --noEmit && npm run build
# before pushing
make format && pre-commit run --all-files
```

DB-backed backend tests need a PostgreSQL 16 + pgvector `DATABASE_URL`; without one, say
so in the PR and let CI be the gate.

## 4. Definition of done for the plan as a whole

- [ ] The two live reproductions in the review §6 return `403` (health with forged
      header) and `200` (Arabic share image).
- [ ] The local proofs in the review §6 raise validation errors instead of succeeding.
- [ ] Search Console shows indexed pages growing beyond the current 66 URLs
      (baseline recorded in BITB-300).
- [ ] `docs/ROADMAP.md` describes the product work in waves 3–4 as the current focus.
- [ ] A dated follow-up review re-runs every LIVE and RUN check in the review file.

## 5. Deliberately not planned

- Splitting `azure-deploy.yml`, `ChatIsland.tsx` and `ChatViewModel.kt` (July findings O6,
  A2, A3 — all larger than in July). Worth doing, but they do not block anything above and
  each needs its own design.
- Reducing the 5/15/60-minute production crons. No evidence of cost or noise was
  collected; measure before changing.
- CI flakiness. Not measured.
- Server-side or signed conversation history. BITB-296 bounds the damage of forged
  history; removing the trust entirely is a product-level change recorded there as a
  follow-up decision.
