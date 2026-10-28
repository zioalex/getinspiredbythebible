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
3. **Contact selection:** by **locale region + language**. Use the region subtag the client sends
   (e.g. `pt-BR`, `de-AT`, `es-MX`, `zh-TW`) when present, else a per-language default country.
   findahelpline.com is always included.
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

2. **Request:** add an optional `region` field (ISO 3166-1 alpha-2) to `ChatRequest`. Web sends it from
   the locale or `navigator.language`. Android sends it from `Locale.getDefault().country`. Older
   clients omit it and get the language default.
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
- [ ] Every registry entry has a source URL and verification date. A test enforces this, and the owner
      signs off on the numbers table.
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

## Open questions

1. **Arabic default country.** There is no pan-Arab crisis line. When there's no region, should it
   be international only, or a default country? Proposed: international only, plus regional entries
   when the region is known.
2. **Card on later turns.** Should it repeat on each crisis turn in a session, or only the first?
   Proposed: on every crisis turn, since repeats are cheap and safety-relevant.
