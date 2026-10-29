# BITB-251: Emergency Critical Path — Deterministic Hotline Card for Threats to Self or Others

**Status:** 🎯 Todo — spec awaiting owner confirmation (2026-10-28)
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
   - Payload: `kind` (`self_harm` | `threat_to_others`), `region_used`, `emergency`,
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
7. **Telemetry:** an OTel counter `chat_crisis_card_shown{kind, language, region_used, path}`. No
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
  `region_used` in the counter.
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
