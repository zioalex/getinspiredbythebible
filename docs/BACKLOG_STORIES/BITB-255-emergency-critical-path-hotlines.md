# BITB-255: Emergency Critical Path — Deterministic Hotline Card for Threats to Self or Others

**Status:** 🔍 In Review — verified (3 verify rounds) 2026-10-29
**Priority:** P0
**Size:** L
**Created:** 2026-10-28
**Prompted by:** owner request 2026-10-28: "Add a critical path evaluation to directly pass emergency
hotlines and contact." Supersedes the never-filed "BITB-019 Crisis Response Flow" idea from
`docs/WIP/SESSION-2026-02-24-content-safety-and-query-improvements.md`. That ID was later reused for
an unrelated story.

## User story

**As** someone who writes to Vox Quieta while threatening to hurt themselves or someone else,
**I want** the right emergency and crisis numbers for where I am, shown immediately and in a form I can
tap to call,
**so that** a real person can reach me before I read any AI-generated text, and without depending on
the model to remember to mention them.

## Problem (verified in code, 2026-10-28)

`ChatService._check_content_safety` (`api/chat/service.py`) produces three relevant outcomes:

| Outcome | What the user gets today | Hotlines? |
|---------|--------------------------|-----------|
| Allowed + `compassionate=True` (help-seeking self-harm) | LLM reply with `COMPASSIONATE_RESPONSE_ADDENDUM` (`api/chat/prompts.py`) | **Only if the LLM obeys the prompt**, and the prompt names only US 988 + findahelpline.com |
| Blocked, self-harm category | Pre-written `_BLOCKED_RESPONSE_TEMPLATES["self_harm_blocked"][lang]` | Yes, in the text. ar/ru/zh/hi/ko show only US 988 or the international link |
| Blocked, `violence_or_threat` | Pre-written refusal | **None.** A threat against someone else gets no emergency or crisis contact at all |

Problems:

- The numbers are plain markdown inside the message. Nothing can be tapped, they aren't structured,
  and they depend on the language, not the user's country.
- On the compassionate path they arrive only after retrieval and full LLM latency, if they arrive at
  all.

## Decisions (owner, 2026-10-28)

1. **Trigger:** all three outcomes above. That is, anyone threatening **themselves or someone else**.
2. **Order:** the hotline card is sent **first**: as the first stream event, before retrieval or the LLM
   runs. On the compassionate path, the LLM's compassionate reply then follows underneath. Blocked
   paths still make no LLM call: their pre-written text follows the card.
3. **Contact selection** (revised 2026-10-29): by **where the user is**, then locale. Emergency
   numbers only work in the country the caller is in, so the order of precedence is:
   1. the `CF-IPCountry` header. Cloudflare already proxies `api.voxquieta.org`: the API reads
      `CF-Connecting-IP`. This is the free IP Geolocation setting. There is no geo-IP database and
      nothing is stored.
   2. the client locale region (e.g. `pt-BR`, `de-AT`).
   3. a per-language default country.
   4. international only.

   findahelpline.com is always included, and `XX`/`T1` (unknown, Tor) skip step 1. The card shows the
   country it used, with a "Not in <country>?" picker, so a VPN user or traveller can correct it.
4. **UI:** a **dedicated crisis card** (structured `crisis_resources` field) on web and Android, with
   `tel:`/`sms:` links, pinned above the reply.
5. **Threat to others:** **same card** as self-harm (local emergency number + crisis line).

## Functional requirements

1. **Hotline registry** in a new backend module, `api/safety/crisis_resources.py` (single source of
   truth, like `translation_registry.py`):
   - Keyed by ISO country. Each entry has the emergency number plus one or more crisis lines:
     `label` (localized), `phone`, optional `sms`, `hours`, and optional `url`.
   - Has a per-language default country and a region-alias map.
   - Falls back in this order: exact region → language default → international (findahelpline.com
     plus "your local emergency number").
   - Covers every region below. **Each number must be verified against an official source before
     merge, with the source URL and verification date recorded in a code comment per entry.**
     Starting candidates, all to be verified:

     | Lang | Default | Crisis line | Emergency | Other regions to include |
     |------|---------|-------------|-----------|--------------------------|
     | en | US | 988 (call/text) | 911 | GB Samaritans 116 123 / 999; IE 116 123 / 112; CA 988 / 911; AU Lifeline 13 11 14 / 000 |
     | it | IT | Telefono Amico 02 2327 2327 | 112 | CH 143 / 112 |
     | de | DE | TelefonSeelsorge 0800 111 0 111 | 112 | AT 142 / 112; CH 143 / 112 |
     | es | ES | 024 | 112 | MX Línea de la Vida 800 911 2000 / 911; AR 135 / 911 |
     | fr | FR | 3114 | 112 | BE 0800 32 123 / 112; CH 143; CA 988 |
     | pt | BR | CVV 188 | 190 / 192 | PT SOS Voz Amiga 213 544 545 / 112 |
     | ar | — (open question) | findahelpline.com | local | EG, SA, AE, LB, MA, JO: verify each |
     | ru | RU | 8-800-2000-122 | 112 | — |
     | zh | CN | 12356 (national mental-health line, verify) | 110 / 120 | TW 1925 / 110; HK Samaritans 2389 2222 / 999 |
     | hi | IN | Tele-MANAS 14416 | 112 | — |
     | ko | KR | 109 | 112 / 119 | — |

2. **Request:** read `CF-IPCountry` server-side (owner step: enable IP Geolocation in Cloudflare →
   Network). Add an optional `region` field (ISO 3166-1 alpha-2) to `ChatRequest` for the locale
   fallback and the picker override: web sends it from the locale or `navigator.language`, and
   Android sends it from `Locale.getDefault().country`. The country is used only to pick contacts,
   never stored. A user-picked override is kept only on the device.
3. **Backend critical path,** in both `chat()` and `chat_stream()`:
   - It runs right after `_check_content_safety`, so its only latency cost is the safety check.
   - On any of the three trigger outcomes:
     - `chat_stream()` yields `{"type": "crisis_resources", "resources": {...}}` as the **first**
       event, before `metadata`, retrieval and the LLM.
     - `chat()` returns `crisis_resources` on `ChatResponse`.
   - Payload: `kind` (`self_harm` | `threat_to_others`), `country`, `country_source`, `emergency`,
     `lines[]` (localized `label`, `phone`, `sms`, `hours`, `url`), `international_url`, and a
     localized `heading`.
   - The card must still be sent if retrieval or the LLM fails afterwards.
4. **Prompts and templates:**
   - `COMPASSIONATE_RESPONSE_ADDENDUM` no longer lists numbers. It tells the LLM that a resources
     card is already shown, so it should refer to it gently and not invent numbers.
   - The `self_harm_blocked` and `violence_or_threat` templates no longer hard-code numbers.
   - Old clients that don't render the card would lose the numbers. To prevent that, the backend
     **also** keeps the registry-rendered numbers as a markdown fallback in the blocked text. A new
     client that renders the card suppresses the duplicate, gated by a request capability flag such
     as `supports_crisis_card`.
5. **Web:** a `CrisisResourcesCard` component, shown above the assistant message:
   - Tap-to-call (`tel:`) and tap-to-text (`sms:`) links, an emergency number that stands out, and
     the findahelpline.com link.
   - RTL-correct for Arabic. The card stays attached to the saved turn in local history.
6. **Android:** the equivalent Compose card, with `Intent.ACTION_DIAL` and `ACTION_SENDTO`. It never
   uses `ACTION_CALL`, so no permission is needed. Strings go in all 11 `values-*` locales.
7. **Telemetry:** an OTel counter `chat_crisis_card_shown{kind, language, country_source, path}`. No
   message text is logged; the existing `text_hash` is kept.

## Non-functional requirements

- **Languages:** all 11 (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) for heading, labels and fallback
  text, on backend, web and Android.
- **Latency:** the card event arrives within the safety-check latency. There is no retrieval or LLM
  before it.
- **Accessibility:**
  - The card has `role="alert"` on web and a live region on Android.
  - Links have descriptive accessible names ("Call 988 Suicide & Crisis Lifeline").
  - Tap targets are at least 44×44 px or 48 dp. Contrast meets WCAG AA in light and dark.
- **Privacy:** no new storage. The region is used only to pick contacts and is not logged beyond
  `country_source` (never the country itself) in the counter.
- **Correctness:** a wrong number in a crisis is worse than none. Every entry carries a source and a
  verification date, and a test fails if any entry is missing its source.

## Acceptance criteria

- [ ] All three trigger outcomes produce `crisis_resources`, in both `chat()` and `chat_stream()`.
      For the stream, it is the first event. Asserted by a test for each outcome.
- [ ] The card still arrives when retrieval raises or the LLM raises after it (stream test).
- [ ] Threat-to-others (`violence_or_threat`) now shows the same card. Previously it showed no
      contacts.
- [ ] Region resolution is tested for the exact region, the language default, an unknown region and
      a missing region, and is parametrized across all 11 languages.
- [ ] Every registry entry has an official `source_url`, `verified_on` and `verified_by`. A CI test
      enforces this, and the owner signs off on the numbers table.
- [ ] The weekly staleness workflow fails on an entry older than 180 days or a dead source URL.
- [ ] The country comes from `CF-IPCountry`, then the locale region, then the language default, then
      international. `XX`/`T1` are ignored. Tested, including the "Not in <country>?" override.
- [ ] Non-crisis turns never get the card: a regression test covers a Bible-narrative "kill" phrasing
      across the 11 languages.
- [ ] The compassionate addendum no longer hard-codes numbers. Blocked templates render numbers from
      the registry, and the markdown fallback is suppressed when `supports_crisis_card` is set.
- [ ] Web: Vitest component tests cover rendering, `tel:`/`sms:` hrefs, RTL, and that the card stays
      in history.
- [ ] Android: a JVM unit test covers payload parsing, and a ComposeTest covers the card's dial
      intent. Translation validation passes for all locales.
- [ ] The privacy policy needs no change, because nothing new is stored. Verify this.

## Out of scope

- IP geolocation, and asking the user for their country.
- Live chat or text-line integrations (e.g. Crisis Text Line API), or escalation to a human
  moderator.
- Changing *which* messages the safety pipeline flags. Detection recall stays in BITB-200–204.

## Resolved questions (owner, 2026-10-29)

1. **Arabic / no-region default.** Resolved by IP country (FR 3): the country is normally known, so
   the language default only applies when Cloudflare reports `XX`. For Arabic it is then
   international only.
2. **Card on later turns.** It shows **on every crisis turn.**

## Hotline data source — decision (owner, 2026-10-29)

**Self-curated registry**, not ThroughLine. The research is below. The registry is maintained like
this:

1. **One data file**, `api/safety/crisis_resources.json`, loaded by `api/safety/crisis_resources.py`.
   Each crisis-line and emergency entry has `source_url`, which must be the operator's own site or a
   national regulator or health ministry (never an aggregator), plus `verified_on` (ISO date) and
   `verified_by`.
2. **A CI test** fails if any entry lacks a source, has a non-official source host, or has a
   malformed E.164-style number.
3. **A staleness check**: a weekly scheduled workflow (not the PR gate, so PRs never go red just
   because time passed) fails when any `verified_on` is more than 180 days old, or when a
   `source_url` no longer resolves. Re-verifying means: open the source, confirm the number and
   hours, and bump `verified_on` in a PR.
4. **A provider interface** (`CrisisResourceProvider`) with a single `StaticRegistryProvider`
   implementation, so a licensed feed such as ThroughLine can be swapped in later without touching
   the chat path.
5. **The first verification pass** is done during Build. The owner signs off on the final table in
   the PR.

## Data source research (2026-10-29)

| Source | Verified? | Machine-readable | Licence / cost | Fit |
|--------|-----------|------------------|----------------|-----|
| **ThroughLine API** (the organisation behind findahelpline.com, an IASP partner) | Yes. More than 1,300 services, verified by direct contact with the helplines and maintained daily. Phone/SMS/URL validation and audits | Yes. OAuth 2.0 REST: `/countries`, `/helplines?country=<ISO-2>`, topic filter | Developer account enabled by their team. Free sandbox covers US + NZ only; full coverage (170+ countries) is paid, price on request. 1,000 calls/day by default | Best: the same data we already link to, kept current by people whose job it is |
| findahelpline.com website / widget | Yes (same data) | No | Terms: **personal use only. Commercial use, scraping and AI extraction are prohibited** without permission | Link only, as today. Never scrape it |
| IASP / Befrienders Worldwide directories | Partly | No public API | Ask the organisations | No |
| Wikipedia "List of suicide crisis lines" / emergency numbers | Not verified | Wiki tables | CC BY-SA | Fallback cross-check only |
| esrot.com emergency-numbers dataset | Partly, by its own disclaimer | Yes | Third party | Emergency numbers only, as a cross-check |

**Emergency numbers** (police/ambulance) are national, change very rarely and have no verified API. A
small static table in the repo is fine for them, with the national-regulator source URL per entry.
112 also works on every GSM network, and the ITU recognises 112 and 911.

### Recommended architecture (if ThroughLine is chosen)

- **Never call ThroughLine on the crisis path.** A daily job syncs `/helplines` for every country,
  for the topics *suicidal thoughts* and *abuse/violence*, into a local cache table. That is about
  200 calls/day, within quota. The crisis path reads only the cache.
- **Bundled fallback.** A static JSON shipped in the repo, regenerated from the last good sync and
  committed by a scheduled PR, so an owner can review the diff. It covers the 11 default countries
  plus the emergency table, so a brand-new deploy or a ThroughLine outage still shows numbers.
- **Staleness.** An alert fires if the sync hasn't succeeded for 7 days. Cached rows keep their
  ThroughLine `id` and `last_verified` date.
- **Owner steps:** apply for a ThroughLine developer account; store credentials as
  `THROUGHLINE_CLIENT_ID` / `THROUGHLINE_CLIENT_SECRET` in Key Vault; accept their data-use terms
  (attribution, display rules).

Sources: [ThroughLine developer docs](https://developer.throughlinecare.com/general),
[ThroughLine for Trust & Safety](https://www.throughlinecare.com/who-we-serve/trust-safety-teams),
[ThroughLine pricing / limits](https://developer.throughlinecare.com/limits-policy),
[Find A Helpline terms](https://findahelpline.com/terms),
[IASP crisis centres](https://www.iasp.info/crisis-centres/),
[Cloudflare IP geolocation](https://developers.cloudflare.com/network/ip-geolocation),
[Wikipedia emergency numbers](https://en.wikipedia.org/wiki/List_of_emergency_telephone_numbers).

## Implementation plan (Plan stage, 2026-10-29)

### Findings from the code read that change the design

1. **A route-level filter can pre-empt the card.** `check_content_filter` (`api/utils/security.py`)
   runs as a route dependency *before* `ChatService`, and returns HTTP 400 `content_blocked` on
   profanity or repeated characters. So "f*** this, I want to kill myself" or "nooooo I want to
   die" never reaches the safety pipeline. The user gets the generic blocked toast and **no
   numbers**. Fix it here.
2. **Classifying by reason string.** Blocked reasons come from four stages with different strings:
   - keyword: `keyword_violation:<type>`, plus `self_harm_with_violence (fallback)`
   - Llama Guard: `violence_or_threat_detected` (S1/S2/S9), plus `possible_help_seeking` (S11,
     allowed)
   - OpenAI moderation: `violence_or_threat_detected`, plus `self_harm_instructions_detected`
   - Azure: `harmful_intent_detected` with severity `categories`, plus `help_seeking_detected`

   `_map_reason_to_category` (`api/chat/prompts.py`) already normalises these, and the
   classification reuses it.
3. **`chat()` has five return paths after the safety check:** blocked, off-topic, clarification,
   scripture-unavailable and normal. `chat_stream()` has the same five as yield paths.
4. **Android local DB.** It is `version = 1` with `fallbackToDestructiveMigration()`. Adding a column
   without an explicit `Migration(1, 2)` would **wipe every user's saved conversations**.
5. **Verification can't happen here.** The sandbox cannot reach any official helpline site (988lifeline.org,
   samaritans.org, telefonoamico.it and others all fail), so the first verification pass cannot
   happen during Build. GitHub Actions can reach them.

### Backend

| File | Change |
|------|--------|
| `api/utils/crisis_resources.json` (new) | Registry data. `emergency` table per country, `lines` per country (`label` per language with an `en` fallback, `phone`, `sms`, `hours`, `url`), `language_defaults` (`ar` → none), `international_url`. Every entry has `source_url`, `verified_on` (ISO date or `null`) and `verified_by`. Seeded with the countries in the table above; entries not yet verified carry `verified_on: null` |
| `api/utils/crisis_resources.py` (new) | `CrisisKind` enum (`self_harm`, `threat_to_others`). `classify_crisis(outcome) -> CrisisKind \| None`. `resolve_country(cf_country, client_region, language)`, which treats `XX`/`T1`/invalid as absent. `CrisisResourceProvider` protocol with `StaticRegistryProvider` loading the JSON once (`lru_cache`). `build_crisis_payload(kind, country, language) -> dict`. `render_markdown_fallback(payload, language) -> str` |
| `api/chat/service.py` | Add `is_help_seeking` to `_SafetyOutcome`. `chat()`/`chat_stream()` gain a keyword-only `client_country: str \| None = None`. Right after `_check_content_safety`, compute `crisis = self._crisis_payload(...)`. **Stream:** if `crisis`, `yield {"type": "crisis_resources", "resources": crisis}` before anything else, then continue unchanged. **Blocking:** every return path goes through `_with_crisis(response, crisis)`, which sets `ChatResponse.crisis_resources`. Increment the counter `chat_crisis_card_shown{kind, language, country_source, path}` |
| `api/chat/service.py` `ChatRequest` | Add `region: str \| None` (pattern `^[A-Za-z]{2}$`, upper-cased) and `supports_crisis_card: bool = False` |
| `api/chat/prompts.py` | `COMPASSIONATE_RESPONSE_ADDENDUM`: remove the numbers, and say instead that a crisis card with local numbers is already shown above the reply, so the model should point to it gently and never write phone numbers itself. `self_harm_blocked` templates: remove the bullet list of numbers. `get_blocked_response(reason, lang, crisis_markdown="")` appends the registry-rendered fallback when the client did **not** declare `supports_crisis_card`. `violence_or_threat` keeps its text, and the card or fallback now follows it |
| `api/routes/chat.py` | Read `http_request.headers.get("CF-IPCountry")` and pass it as `client_country` on both routes |
| `api/utils/security.py` `check_content_filter` | If the violation is `PROFANITY` or `REPEATED_CHARS` and `MultiLanguageContentFilter` finds a self-harm span, violence or murder-suicide match on the normalised text, **don't 400**: log it and let the request reach the service so the crisis path runs. URL and spam blocking are unchanged |
| `api/metrics` (existing module that holds the chat counters) | New counter |
| `api/tests/` | `test_crisis_resources_registry.py`: schema, E.164-ish numbers, an official non-aggregator `source_url` host on every entry, every one of the 11 languages has `label`s. `test_crisis_resources_resolution.py`: country precedence, parametrized across 11 languages. `test_chat_crisis_path.py`: integration tests through `chat()`/`chat_stream()` for each trigger outcome × each return path. It asserts the stream's first event is `crisis_resources`, and that the card still arrives when a mocked `search_service` or LLM raises afterwards. It also checks a non-crisis Bible-narrative "kill" phrasing across 11 languages, and markdown-fallback on/off. Route test for the `CF-IPCountry` passthrough and the profanity + crisis bypass. Update the existing tests that assert numbers in `self_harm_blocked` |

**Classification table (`classify_crisis`):**

| Outcome | Kind |
|---------|------|
| allowed + compassionate (keyword, Llama Guard S11, Azure help-seeking) | `self_harm` |
| blocked, `self_harm_blocked` category (including the ambiguous murder-suicide reason and OpenAI self-harm instructions) | `self_harm` |
| blocked, `violence_or_threat` category | `threat_to_others` |
| blocked Azure `harmful_intent_detected` with `self_harm` ≥ threshold / `violence` ≥ threshold | `self_harm` / `threat_to_others` |
| `directed_harm` (abuse aimed at the bot, e.g. "go kill yourself"), `hate_speech`, `sexual_content`, generic | none |

### Web (`frontend/`)

- `src/lib/api.ts`:
  - `StreamChunk.type` gets `"crisis_resources"` and `resources?: CrisisResources`, and the type is
    exported.
  - `ChatResponse.crisis_resources?`.
  - The request body sends `region` (from `navigator.language`'s region subtag, else the locale's)
    and `supports_crisis_card: true`.
- `src/components/CrisisResourcesCard.tsx` (new):
  - `role="alert"`; the emergency number rendered prominently; `tel:`/`sms:` links with accessible
    names; findahelpline.com link; RTL via `dir`.
  - A "Not in {country}?" button opens a small country picker built from the payload's
    `available_countries`. The choice is saved to localStorage (try/catch) and sent as `region` on
    later requests. Because `CF-IPCountry` otherwise wins, the backend gives a client
    **`region_override: true`** precedence. Add that flag to the request too.
- `src/app/[locale]/ChatIsland.tsx`: handle the `crisis_resources` chunk by setting
  `crisisResources` on the placeholder assistant message, and render the card above the bubble.
- `src/lib/conversationStore.ts`: optional `crisisResources` on `StoredMessage`, persisted and
  restored. Older stored rows simply lack it.
- `messages/*.json` (all 11): `Crisis.heading`, `call`, `text`, `emergency`, `international`,
  `notInCountry`, `chooseCountry`.
- Tests (Vitest): card rendering, hrefs, RTL, the picker storing the override, ChatIsland putting
  the card above the reply when the first chunk is `crisis_resources`, and history round-trip.

### Android (`android/`)

- DTOs:
  - `ChatRequestDto` gets `region`, `region_override` and `supports_crisis_card`.
  - `EventSourceParser` handles `"crisis_resources"` and produces a `StreamChunk` with
    `crisisResources`.
  - Domain model `CrisisResources`.
- `ChatViewModel`: attach it to the in-flight assistant message.
- `presentation/components/CrisisResourcesCard.kt` (new):
  - Dial and SMS use `ACTION_DIAL` / `ACTION_SENDTO`; there is no `CALL_PHONE` permission.
  - Live region via `semantics { liveRegion = Polite }`; 48 dp targets.
  - A country-override picker stored in DataStore/SharedPreferences.
- Room:
  - `MessageEntity.crisisJson: String?`.
  - Database `version = 2` with an explicit `MIGRATION_1_2` (`ALTER TABLE messages ADD COLUMN
    crisisJson TEXT`), registered in `DatabaseModule` before the destructive fallback.
- Strings in `values/` plus all 10 `values-*`.
- Tests:
  - JVM tests for `EventSourceParser` (crisis event, malformed payload ignored) and the
    entity-mapper round-trip.
  - A Robolectric `MigrationTestHelper` test for 1 → 2.
  - `CrisisResourcesCardComposeTest` asserting the dial intent and labels.

### Ops, docs and CI

- `.github/workflows/crisis-resources-staleness.yml` (new, weekly, not a PR gate): fails if any
  `verified_on` is `null` or older than 180 days, or any `source_url` doesn't return 2xx/3xx.
- `docs/HOW-TO-VERIFY-CRISIS-RESOURCES.md` (new): the re-verification procedure.
- `deployment/README.md` Cloudflare checklist: add "Network → IP Geolocation: On", and a note that
  without it the card falls back to locale.
- Privacy policy (11 files): one line saying the country is inferred from the connection only to
  show local emergency numbers, and is not stored. Bump the date.

### Plan decisions (owner, 2026-10-29)

1. **Unverified entries are shown**, with `verified_on: null` (today's production status quo). The
   weekly check stays red until each one is verified.
2. **Crisis wording overrides the profanity / repeated-characters route filter.**
3. **No card for `directed_harm` only.** Every `violence_or_threat` outcome, Llama Guard S2
   included, gets the card.
4. **Android persists the card** via an explicit, tested Room `MIGRATION_1_2`.

### Verification

- `cd api && python -m pytest tests/ -x -q`; Ruff, Black, MyPy.
- `cd frontend && npx vitest run && npm run lint && npx tsc --noEmit && npm run build`.
- Android `testDebugUnitTest`, the ComposeTest tier and lint. If Gradle can't run in the sandbox,
  say so, and PR CI becomes the gate.
- Fresh Opus verifier against the acceptance criteria above.

## Fix round (verifier findings, 2026-10-29)

- Old clients (no `supports_crisis_card`): the compassionate addendum has a no-card variant and the
  registry-rendered markdown is appended after the LLM text on every allowed path (stream: extra
  `content` chunk, also re-appended to `corrected_message`).
- Crisis bypass of profanity / repeated-chars now re-runs the remaining content-filter checks
  (`ContentFilter.check(skip=...)`), so a URL hidden behind profanity still blocks.
- `POST /api/v1/crisis-resources` with JSON body `{country, language, kind}`. It is POST so the
  picked country never appears in a URL or in request telemetry (verify round 2). It is rate-limited, no Turnstile, counts only). Web and Android re-render the card in place after the
  country pick and save the new card with the conversation.
- Cards with no `emergency` show a localized "call your local emergency number (112 ...)" line with
  112 as a dial target.
- Real keyword-fallback test for Bible-narrative phrasings: en and ar misfire (xfail strict,
  BITB-257; safety keyword tables unchanged).
