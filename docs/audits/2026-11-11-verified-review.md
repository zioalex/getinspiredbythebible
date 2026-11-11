# Verified Project Review — 2026-11-11

Evidence register behind the [2026-11-11 improvement plan](2026-11-11-improvement-plan.md).
Every row states **how** it was verified. Nothing here is carried over from an earlier
report without a re-check on `main` at `f058cad` (2026-11-10).

This file is a narrative review, not an adversarial-audit report: `tools/audit-metrics/`
only parses `*-adversarial-audit.md`, so the trend numbers are unaffected.

## How to read the "Verified" column

| Label | Meaning |
|---|---|
| **LIVE** | Observed against production (`voxquieta.org`, `api.voxquieta.org`) on 2026-11-11 |
| **RUN** | Reproduced by executing the repo's code locally (commands below) |
| **CODE** | Read at the cited line on `f058cad` |
| **EXT** | Confirmed from an external source (cited) |
| **OWNER** | Cannot be verified from the repo or the public site; an owner step is listed |

## 1. Security and cost exposure

| ID | Finding | Verified | Evidence | Story |
|---|---|---|---|---|
| R1 | A forged `X-Forwarded-For` passes the "local only" gate in production | **LIVE**, RUN, CODE | `GET https://api.voxquieta.org/health` → `403`; same request with `X-Forwarded-For: 127.0.0.1` → `200` with the full component report (DB, LLM, embedding provider, memory). `api/utils/local_only.py:48-53` takes the first XFF entry; `:87` also admits the literal string `testclient` | BITB-297 |
| R2 | Every rate limit keys on that same client-chosen value | RUN, CODE | `get_client_ip` returns `1.2.3.4` for `X-Forwarded-For: 1.2.3.4, <real>` (`api/utils/security.py:183-186`; duplicate logic in `api/utils/turnstile.py:182-192`). The live result in R1 proves the client-supplied leftmost entry survives Cloudflare and the Container Apps ingress | BITB-297 |
| R3 | Each bypassed `/health` call makes a paid LLM call and a paid embedding call | LIVE, CODE | Live body showed `llm.latency_ms 358.8`, `embedding.latency_ms 407.4`; `api/routes/health.py:91-180` | BITB-297 |
| R4 | Chat history accepts `role: "system"`, any number of entries and any content size | **RUN**, CODE | `ChatRequest` accepted 5,002 history entries with a 1,000,000-character entry; `_build_messages` forwarded roles `['system', 'system', 'assistant', 'user']` to the LLM. `api/chat/service.py:129` (`role: str`), `:130` (no `max_length`), `:141` (no list cap), `:2267` (role passed through) | BITB-296 |
| R5 | Neither safety layer looks at history | CODE | `check_content_filter` reads only `body["message"]` (`api/utils/security.py:316`); `_check_content_safety` is called with `request.message` only (`api/chat/service.py:611`, `:1815`) | BITB-296 |
| R6 | No request-body size limit anywhere in the backend | CODE | No hit for a body/content-length limit in `api/` outside tests; uvicorn is started without one (`api/Dockerfile:60`) | BITB-296 |
| R7 | Scripture search, stats and verse endpoints have no abuse guard | **RUN** | Route table dumped from the running app (see §6): `GET /scripture/search`, `/search/text`, `/stats`, `/verse/…`, `/chapter/…`, `/range/…` and `GET /chat/verse/…` have **no** `require_*` dependency. `/search` embeds the query on every call (`api/routes/scripture.py:282-290`); `q` has `min_length=2` and no maximum | BITB-298 |
| R8 | The web app does not call `/scripture/search` | CODE | `searchScripture` (`frontend/src/lib/api.ts:862`) has zero non-test callers; no Android caller either. Guarding it breaks no shipped client | BITB-298 |
| R9 | Feedback, contact and church-finder routes have Turnstile only, no rate limit | RUN | Route table: `POST /feedback`, `/feedback/contact`, `/church/search` → `['require_turnstile']` | BITB-298 |
| R10 | Feedback and contact text fields are unbounded | RUN, CODE | `FeedbackRequest` accepted three 1,000,000-character fields and `ContactRequest` a 1,000,000-character message (`api/feedback/models.py:29-57`) | BITB-298 |
| R11 | Turnstile **is** enabled in production | CODE | `deployment/terraform.tfvars:158` `turnstile_enabled = true`. The code default is still `False` (`api/config.py:269`, `deployment/variables.tf:541`) | — (resolved doubt) |
| R12 | The Azure budget alert **is** configured | CODE | `deployment/terraform.tfvars:136-137` `create_budget_alert = true`, `monthly_budget = 100`. Whether the alert resource exists in Azure: OWNER | BITB-305 |
| R13 | Church finder calls a third-party site with a forged browser identity | CODE | `api/routes/church.py:75-82` sends a Chrome `User-Agent` plus `Origin`/`Referer` of `disciplestoday.org` | BITB-298 |
| R14 | `/config` is public and names the provider and model | LIVE, CODE | `GET https://api.voxquieta.org/config` → `200`; `api/main.py:413-457` | BITB-307 |
| R15 | A client-chosen `session_id` is used as a metric label | CODE | `api/routes/chat.py:82` and `:136` — unbounded label cardinality in Application Insights | BITB-307 |
| R16 | The 503 handler returns the upstream exception text | CODE | `api/main.py:686-696` | BITB-307 |
| R17 | Production Postgres is reachable from every Azure tenant; backups are 7 days, single region | CODE | `deployment/main.tf:425-426`, `:433`, `:455-460`. Already tracked as **BITB-005** (🎯 Todo, `docs/BACKLOG.md:2164`) | BITB-005, BITB-305 |
| R18 | CORS allows credentials with `*` methods/headers and localhost origins in production | CODE | `api/main.py:338-350`, `:371-377` (July finding O4, still open) | BITB-307 |

## 2. Runtime and dependency drift

| ID | Finding | Verified | Evidence | Story |
|---|---|---|---|---|
| D1 | Production runs Python 3.14; CI tests, mypy, black and ruff all target 3.12 | CODE | `api/Dockerfile:8,29` (`python:3.14-slim`); `.github/workflows/test_update.yml:106,208,632`; `api/pyproject.toml:11,30,40`. No workflow mentions 3.14 | BITB-304 |
| D2 | Neither version is near end of life | EXT | endoflife.date on 2026-11-11: Python 3.12 EOL 2028-10-31, 3.14 EOL 2030-10-31; Node 22 EOL 2027-04-30, Node 26 LTS since 2026-10-28 (EOL 2029-04-30); PostgreSQL 16 EOL 2028-11-09 | — |
| D3 | The documented Claude model is retired | EXT, CODE | `claude-sonnet-4-20250514` (`api/providers/claude.py:29`, `api/.env.example:13`) was retired 2026-06-15 per Anthropic's deprecations page (via web search; re-check the page before acting) | BITB-304 |
| D4 | `LLM_PROVIDER=claude` without `LLM_MODEL` sends an Ollama model name to Anthropic | CODE | `api/providers/factory.py:50` passes `config.llm_model`, whose default is `"llama3:8b"` (`api/config.py:24`); the `ClaudeProvider` default is never used | BITB-304 |
| D5 | `llm_provider` accepts `"openai"`, which the factory cannot build | CODE | `api/config.py:23` (July finding A5, still open) | BITB-304 |
| D6 | Dependabot ignores every major version bump | CODE | `.github/dependabot.yml:18-21,69-72`. Current gaps: `openai==1.109.1` vs 3.49.0 on PyPI; `anthropic==0.125.0` vs 2.8.0 | BITB-304 |
| D7 | The retirement date of the Azure embedding model is unknown | OWNER | Search returned 2027-04-15 for Azure Government only; no authoritative commercial-cloud date found. A forced move means re-embedding 403,856 verses (live `/scripture/stats`) | BITB-305 |
| D8 | No expiry date or owner is recorded for any token | CODE | `docs/RELEASE_PROCESS.md:382-400` describes PAT expiry as a failure mode and states the 1-year maximum; no inventory exists | BITB-305 |

## 3. SEO and discoverability (live site)

| ID | Finding | Verified | Evidence | Story |
|---|---|---|---|---|
| S1 | The Arabic share image is broken in production | **LIVE**, **RUN** | `GET https://voxquieta.org/ar/opengraph-image` → `503` three times in a row (all other ten locales → `200`). Reproduced on `next dev`: `Error: failed to pipe response … lookupType: 5 - substFormat: 3 is not yet supported` — the image renderer cannot shape the fallback Arabic font | BITB-299 |
| S2 | The Hindi share image renders with broken letter shaping | LIVE | Downloaded image shows split conjuncts and a misplaced vowel sign in the tagline. Chinese renders correctly, so the earlier "empty boxes" hypothesis was wrong | BITB-299 |
| S3 | The site has 66 indexable URLs and no scripture in HTML | LIVE, CODE | Live sitemap: 66 `<loc>` entries. No verse, chapter, book or topic route under `frontend/src/app/` | BITB-301, BITB-302 |
| S4 | The homepage **is** server-rendered now | LIVE | `/en` HTML: 212 words, `x-nextjs-prerender: 1`. BITB-136 had recorded 0 words | — (resolved doubt) |
| S5 | The homepage has two `<h1>`, both the brand name; the descriptive heading is an `<h2>` | LIVE, CODE | Live `/en`: `h1 = ['Vox Quieta', 'Vox Quieta']`, `h2 = ['Welcome']`. `ChatIsland.tsx:1098`, `SplashScreen.tsx:296`, `[locale]/page.tsx:15` | BITB-300 |
| S6 | Title and meta description say the same thing | LIVE | Title `Vox Quieta — Get inspired daily by God's Word`; description `Get inspired daily by God's Word` | BITB-300 |
| S7 | `/tester` is indexable | LIVE | `/en/tester` → `200` with no `robots` meta | BITB-300 |
| S8 | The 404 page is English-only and has no `<html lang>` | LIVE, CODE | `/ar/__x404` → title `404: This page could not be found.`, `h1 404`, `noindex` present, no `<html>` tag attributes. `frontend/src/app/[locale]/not-found.tsx` | BITB-300 |
| S9 | Every sitemap entry carries the same build timestamp | LIVE, CODE | 66 × `<lastmod>2026-11-10T11:11:33.382Z`; `frontend/src/app/sitemap.ts:11` | BITB-300 |
| S10 | `og:locale` is a bare language code | LIVE | `og:locale = en`; `frontend/src/lib/seo.ts:65` | BITB-300 |
| S11 | The structured-data logo is an SVG | CODE | `frontend/src/lib/seo.ts:98` | BITB-300 |
| S12 | Un-prefixed paths redirect correctly | LIVE | `/privacy` → `307` → `/en/privacy`; `/about` likewise. No 4XX risk | — (resolved doubt) |
| S13 | Legal Markdown files are not served as duplicates | LIVE | `/legal/privacy.md` and `/legal/privacy-en.md` → `404` | — (resolved doubt) |
| S14 | Canonical, hreflang (11 + `x-default`), Open Graph, Twitter card and JSON-LD are present | LIVE | `/en` headers and `<head>` | — |
| S15 | Cloudflare's managed `robots.txt` blocks AI crawlers | LIVE | `ClaudeBot`, `GPTBot`, `Google-Extended`, `CCBot` and others `Disallow: /`; `Content-Signal: search=yes,ai-train=no,use=reference`. This is a Cloudflare dashboard setting, not repo code | BITB-300 (owner decision) |
| S16 | 27 physical Tailwind direction classes will not mirror in Arabic | CODE | `grep -rnoE "\b(ml\|mr\|pl\|pr)-[0-9]+\b\|\btext-(left\|right)\b\|\b(left\|right)-[0-9]+\b" frontend/src --include=*.tsx` (tests excluded) | BITB-300 |

## 4. Process and operations

| ID | Finding | Verified | Evidence | Story |
|---|---|---|---|---|
| P1 | The roadmap is nine months stale | CODE | `docs/ROADMAP.md:5` "Last Updated: 2026-02-23"; "Now" is still February's stability milestone | BITB-306 |
| P2 | The backlog file is 7,623 lines | CODE | `wc -l docs/BACKLOG.md`; 76 files in `docs/DONE/`, 228 in `docs/BACKLOG_STORIES/` | BITB-306 |
| P3 | The audit trend has not moved since July although the workflow succeeds | CODE, LIVE | `docs/audits/metrics/report.md:4` latest snapshot 2026-07-05; the `Audit Metrics` workflow ran successfully on 2026-11-02 (run 41474382470). Why no snapshot was committed was not determined (job log not read) | BITB-306 |
| P4 | The deploy workflow is 2,162 lines; three production crons run every 5, 15 and 60 minutes | CODE | `.github/workflows/azure-deploy.yml`; `prod-monitor.yml:55`, `prod-deploy-drift.yml:39`, `prod-browser-smoke.yml:33` | — (noted, not planned) |
| P5 | The container `HEALTHCHECK` calls the paid `/health` endpoint | CODE | `api/Dockerfile:57` | BITB-297 |

CI flakiness was **not** measured and no claim about it is made in the plan.

## 5. Status of the July 2026 adversarial audit

Re-checked on `f058cad`. "Changed" means the cited code no longer matches the finding;
"Present" means the cited artifact is still there.

| Finding | Status | Evidence |
|---|---|---|
| A1 triple verse parser | Present, in progress | BITB-059 🚧 |
| A2 `ChatIsland.tsx` monolith | **Worse** | 1,357 → 1,704 lines |
| A3 `ChatViewModel.kt` god-object | **Worse** | 1,214 → 1,644 lines |
| A4 duplicated request plumbing in `api.ts` | Present | 947 → 1,076 lines; no shared `apiFetch` |
| A5 cosmetic DI, `openai` literal | Present | `factory.py:143,149`; `config.py:23` |
| A6 circuit breaker side-effecting read | Present | `circuit_breaker.py:60`; no probe-acquire method |
| A7 circular import | Present | `verseExtraction.ts:13` |
| A8 magic-number contracts on Android | Partly fixed | limits now seeded from `/config`; compiled fallbacks remain (`ChatViewModel.kt:218`) |
| A9 commit on every GET | Present | `scripture/database.py:207` |
| A10 dead code | Partly fixed | `AGENTS*.old` gone; `scripts/load_bible.py.backup` and five unused `api.ts` exports remain |
| E1 unreachable 503 | **Fixed** | typed `AllModelsExhaustedError` (`routes/chat.py:90,157`) |
| E2 Turnstile fail-open | **Fixed** | breaker, fails closed after 5 failures |
| E3 verse click digits | **Fixed** | `ChatMessage.tsx:109-110` uses `normalizeDigits` |
| E4 Room without migrations | Changed | `version = 2`; migration objects not inspected |
| E5 retry against same session | Not re-checked | — |
| E6 streamed chats untracked | **Fixed** | `track_session` on both routes (`routes/chat.py:87,155`) |
| E7 boot without DB | **Fixed** | BITB-090 |
| E8 unguarded `localStorage` | **Fixed** | no direct `localStorage` use left in `ChatIsland.tsx` |
| E9 English-only guardrail string | Present | `chat/service.py:785` |
| E10 Android language store race | Not re-checked | — |
| E11 migration checksums never compared | Present | `run_migrations.py:226`; duplicate `003_` prefix remains |
| E12 mutable closure in state updater | Present | `ChatIsland.tsx:540-593` |
| E13 large nested-quantifier regex | Not re-checked | — |
| S1 sync HTTP in async code | **Fixed** | no sync client left on the request path |
| S2 full-scan public search | Not re-checked | still reachable unguarded — see R7 |
| S3 in-memory rate limiter | **Fixed** | Postgres-backed store |
| S4 unmemoized chat list | Present | no `memo` in `ChatMessage.tsx` |
| S5 single small database | Present | `B_Standard_B2s` |
| S6 `runBlocking` on Android | Present | `TurnstileInterceptor.kt:91,103`, `ChatViewModel.kt:258` |
| S7 extra round-trips | Not re-checked | — |
| S8 Ollama 300 s timeout | Present | `providers/ollama.py:55` |
| D1 stale deployment doc | **Fixed** | `DEPLOYMENT.md` now describes Azure |
| D2 one e2e spec | Improved | five specs; `webServer` configured |
| D3 Android gate non-blocking | Present | `android-compose-tests.yml:42` |
| D4 untested load-bearing modules | Improved | `test_rate_limiter*.py` exist; others not re-checked |
| D5 tests excluded from `tsc` | Present | `frontend/tsconfig.json:32-36` |
| D6 `.env.example` vs config | Partly fixed | mode now matches; `DEBUG=true` remains (`api/.env.example:88`) |
| D7 doc rot | Partly fixed | see A10 |
| O1 dev compose with default password | Present | `docker-compose.yml:113-116` |
| O2 content safety off by default | **Fixed** | default on, `ml_only` |
| O3 public DB, thin DR | Present | R17 |
| O4 CORS | Present | R18 |
| O5 open telemetry endpoint | Partly fixed | now rate-limited, but keyed on a spoofable IP (R2) |
| O6 deploy workflow size | **Worse** | 2,162 lines |
| O7 supply-chain seams | Present | Bandit still skips B608; JitPack still used; frontend now on Node 26 LTS |
| O8 Android release engineering | Not re-checked | — |
| O9 monitoring hard-codes | Not re-checked | — |

## 6. Reproduction

Live checks (read-only `GET`s; the header test touches only the health endpoint):

```bash
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
curl -s -A "$UA" -o /dev/null -w "%{http_code}\n" https://api.voxquieta.org/health                                  # 403
curl -s -A "$UA" -o /dev/null -w "%{http_code}\n" -H "X-Forwarded-For: 127.0.0.1" https://api.voxquieta.org/health  # 200 today, must become 403
for l in en it de es fr pt ar ru zh hi ko; do
  curl -s -A "$UA" -o /dev/null -w "%{http_code} $l\n" "https://voxquieta.org/$l/opengraph-image"                   # ar is 503 today
done
bash scripts/seo-live-check.sh
```

Local proofs (Python 3.12 venv with `api/requirements.txt` + `api/requirements-dev.txt`,
run from `api/` with any syntactically valid `DATABASE_URL`):

```python
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from chat.service import ChatRequest, ChatService, ConversationMessage
from feedback.models import ContactRequest, FeedbackRequest
from utils.local_only import require_local_access

big = "A" * 1_000_000
ChatRequest(message="hi", conversation_history=[{"role": "system", "content": big}] * 5000)  # accepted
svc = ChatService.__new__(ChatService)
print([m.role for m in svc._build_messages("hi", [ConversationMessage(role="system", content="x")])])
# ['system', 'system', 'user']

FeedbackRequest(message_id="m", rating="positive", comment=big, user_message=big, assistant_response=big)
ContactRequest(email="a@example.com", subject="other", message=big)  # both accepted

app = FastAPI()

@app.get("/gated", dependencies=[Depends(require_local_access)])
async def gated():
    return {"ok": True}

c = TestClient(app, client=("203.0.113.9", 5555))
print(c.get("/gated").status_code)                                              # 403
print(c.get("/gated", headers={"X-Forwarded-For": "127.0.0.1"}).status_code)    # 200
print(c.get("/gated", headers={"X-Forwarded-For": "testclient"}).status_code)   # 200
```

Route guard table (dumped from `main.app`, 2026-11-11):

```text
POST  /chat                                   check_content_filter, require_rate_limit, require_turnstile
POST  /chat/stream                            check_content_filter, require_rate_limit, require_turnstile
GET   /chat/verse/{book}/{chapter}/{verse}    (none)
POST  /church/search                          require_turnstile
POST  /crisis-resources                       require_rate_limit
POST  /feedback                               require_turnstile
POST  /feedback/contact                       require_turnstile
GET   /health                                 require_local_access
GET   /health/live, /health/ready             (none)
GET   /scripture/translations, /book-names, /books                    (none)
GET   /scripture/verse/…, /chapter/…, /range/…                        (none)
GET   /scripture/search, /scripture/search/text, /scripture/stats     (none)
POST  /admin/weekly-report, GET /admin/translation-coverage           probe secret checked in the handler
GET   /, /config                              (none)
POST  /api/v1/client-errors, /client-events   require_rate_limit
GET   /debug/embeddings                       require_local_access
```

Arabic share image: `cd frontend && npm ci && npx next dev -p 3111`, then
`curl -i http://localhost:3111/ar/opengraph-image` → `500` with the shaping error in the
server log.

## 7. What could not be verified, and who can

| Item | Why | Owner step |
|---|---|---|
| Azure budget alert resource exists | No Azure access | `terraform state list \| grep budget` |
| Commercial-cloud retirement date of `text-embedding-3-small` | No authoritative source reachable | Read the Azure OpenAI model-retirements page; record the date in BITB-305 |
| Expiry dates of `RELEASE_PLEASE_TOKEN`, `AUTO_UPDATE_PR_TOKEN`, the Azure service principal, the Play key | Secrets are not readable | Fill the inventory in BITB-305 |
| Whether a database restore has ever succeeded | No Azure access | Run the drill in BITB-305 |
| Search Console indexed-page count | No account access | Record it in BITB-300 before and after the SEO work |
| Cloudflare AI-crawler setting | Dashboard only | Decision recorded in BITB-300 |

Sources for the external facts: [endoflife.date](https://endoflife.date/),
[Anthropic model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations),
[Azure OpenAI model retirements](https://learn.microsoft.com/azure/ai-services/openai/concepts/model-retirements),
[Azure Container Apps ingress](https://learn.microsoft.com/azure/container-apps/ingress-overview).
