# BITB-242: Platform-Selective Feature Flags — Server-Driven Per-Platform (Web/Android) Flag Registry

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (cross-cutting: api + frontend + android + deployment)
**Created:** 2026-10-26
**Driver:** BITB-080 follow-up chips rollout (PR #1216 contract: "Android renders behind its
own default-off flag"); generalizes the BITB-119 `features.tts_enabled` pattern.

## Problem

There is no way to enable a client-facing feature on Web but not Android (or vice versa).
Every flag mechanism in the repo is either global or build-time, and the three mechanisms
that do exist diverge:

| Mechanism | Where | Flip cost | Platform dimension |
| ---------- | ----- | --------- | ------------------- |
| Backend global env flags | `api/config.py` (Pydantic Settings) → Terraform var (`deployment/variables.tf`) → Azure env | Terraform apply → new revision | none — applies to ALL clients |
| Web build-time flags | `frontend/src/lib/featureFlags.ts` reading `NEXT_PUBLIC_*` (Docker build-arg) | full image rebuild + redeploy | web-only by construction |
| Android | `BuildConfig` compile-time fields (`FIREBASE_ENABLED`, `DONATE_URL`) + one runtime server flag (`features.tts_enabled`, BITB-119, fail-open via `ConfigResponseDto`) | Play release for build flags; server flag is runtime | none |

The live case is BITB-080 (follow-up question chips, PR #1214 eval → latency-GO): PR #1216
ships them web-only via `NEXT_PUBLIC_FOLLOW_UPS_ENABLED`, and its contract parks Android
behind "its own default-off flag" — a flag that does not exist yet and would be a fourth,
Android-only ad-hoc mechanism. Consequences:

- **Web enablement needs a rebuild** (build-arg → image → redeploy) even though the value
  only gates client rendering; the backend can be flipped at runtime, the web cannot.
- **Android enablement needs a Play release** (days, review) for what is a rendering switch.
- **Fail policy is folklore**, not stated anywhere: `tts_enabled` fails OPEN (absent ⇒ on),
  web follow-ups fail CLOSED (default off), Android follow-ups have no defined policy at all.
- **Every new flag touches 6+ places ad hoc** (config.py, variables.tf, env-manifest.yaml,
  /config route dict, web hook, Android DTO) with nothing keeping the three clients in sync —
  the same "three parsers diverge subtly" trap the verse grammar has a fixture and parity
  tests for.

## User Story

**As** the product owner,
**I want** to enable or kill a client-facing feature on Web or Android independently, at
runtime, from the same place,
**so that** a feature validated on web can light up Android (or stay web-only) without a
frontend rebuild or a Play release, and a regression on one platform never forces the
feature off on the other.

## Options Considered

1. **Server-driven flag registry on `GET /config` with per-platform maps** *(chosen)* —
   generalizes the already-proven pattern (`features.tts_enabled` BITB-119,
   `chat.session_max_requests` BITB-075/BITB-156): both clients already fetch `/config` at
   startup (web `ServerConfigProvider`, Android `fetchConfigWithRetry`) with compiled-in
   fallbacks. Flip = Terraform apply → new revision → next client fetch. Zero new
   infrastructure, zero cost, offline-safe, matches the established ops flow.
2. **Build-time per-platform flags** (`NEXT_PUBLIC_*` web + `BuildConfig`/flavors Android) —
   rejected: every flip needs a web rebuild and/or a Play release; two mental models for the
   same need; this is the exact pain PR #1216 just hit.
3. **Third-party flag service** (LaunchDarkly/PostHog/Unleash) — rejected: the app is
   deliberately anonymous (no accounts, no stable user id), so per-user/percentage targeting
   is either impossible or would require inventing tracking that conflicts with the
   no-tracking posture; adds cost (Ko-fi $80/mo infra budget), an external dependency and
   failure surface (see BITB-150 cost evidence culture), and ZDR/egress review burden.
4. **DB-backed flags + admin endpoint** — rejected for now: hot-toggle without Terraform is
   nice, but adds a table, an authenticated admin surface, and drift risk against the
   Terraform-managed env values. Revisit as a follow-up only if flag flips become frequent
   enough that `terraform apply` hurts.

## Chosen Design

**Backend registry (single source of truth).** A declarative registry of *client-facing*
flags — one entry per flag with: key, description, per-platform default
(`web`/`android`), and explicit **fail policy** (`open`: absent/unreachable ⇒ on;
`closed`: absent/unreachable ⇒ off). Values resolve from new Pydantic settings
(e.g. `follow_ups_enabled_web`, `follow_ups_enabled_android` — names indicative), one per
flag × platform, same style as the existing flat flags. `GET /config` builds its
`features` block by **iterating the registry** — no hand-maintained dict:

```json
"features": {
  "tts_enabled": true,                  // legacy flat key — UNCHANGED (read by shipped APKs)
  "web":     { "follow_ups": true  },
  "android": { "follow_ups": false }
}
```

**`GET /config` is an additive-only public contract.** Shipped Android APKs fetch it for
months; keys are never renamed, retyped, or given new meanings. The legacy flat
`features.tts_enabled` keeps working exactly as today (a "both platforms, one switch" flag;
it may later also appear per-platform, but the flat key stays). Clients must tolerate
unknown keys and absent keys (web: field access with `=== false`-style checks — already the
pattern; Android: nullable DTO + `ignoreUnknownKeys = true` — already set).

**Parity fixture, like the verse grammar.** A shared fixture (e.g.
`api/tests/fixtures/client_feature_flags.json`) listing every flag: key, description,
per-platform defaults, fail policy — consumed three ways on the verse-grammar model
(`verseGrammar.generated.ts` + `VerseCorpusParityTest`): a generated TS artifact for the
web resolver, an Android parity test, and an api test asserting `/config` exposes every
registry key. A flag added server-side without its client legs fails CI — not production.

**Web resolver.** `frontend/src/lib/featureFlags.ts` (or the `useServerConfig` hook —
Plan decides; both are already flag plumbing) gains a `featureEnabled(key)` that resolves
`features.web[key]` over the compiled default; `NEXT_PUBLIC_FOLLOW_UPS_ENABLED` is demoted
from *the* switch to the compiled-in **fallback** (fail policy for follow-ups is CLOSED, so
the fallback value is `false`). Server map is authoritative when present; build flag only
survives a failed/absent `/config` fetch.

**Android holder.** A small `FeatureFlags` holder resolved from `ConfigResponseDto`
(map-style, tolerant), consumed as `isFeatureEnabled(key)` against compiled defaults
(`follow_ups` default `false`, fail CLOSED). Works offline (compiled defaults), refreshes on
the existing `/config` fetch-with-retry. No `BuildConfig` changes for feature flags.

**Two gates, stated once.** Follow-ups will have exactly two switches and the story names
them so nobody rediscovers it in a year: `chat_follow_ups_enabled` (server behavior — does
the API *generate* suggestions; global, stays flat in `config.py`) and the per-platform
rendering flags above (client UI). Chips render ⇔ both are on for that platform. New
client-facing features inherit the same shape: generation (backend, flat) × rendering
(per-platform).

**Terraform/env.** Per flag × platform: `variables.tf` var + `main.tf` env entry +
`scripts/env-manifest.yaml` row (explicit typed vars — matches the audited pattern; a single
JSON-in-env var was considered and rejected as stringly-typed and undocumented by
convention).

**Flag lifecycle (written down, per flag).** `experimental` (default off) → per-platform
rollout → `graduated` (default flips to on **in code**, server value remains a kill switch) →
`retired` (fixture entry removed once every supported client version tolerates absence —
old clients fall back to their compiled defaults, which by then are on).

## Acceptance Criteria

- [ ] Registry module in `api/` (single source of truth) + `GET /config` emits
      `features.web` / `features.android` maps **generated from the registry**; legacy
      `features.tts_enabled` bit-identical to today (contract test asserts the exact legacy
      response shape)
- [ ] Every registry flag declares an explicit fail policy; policies surfaced in the fixture
- [ ] Shared parity fixture (`client_feature_flags.json`) + generated web artifact +
      Android parity test + api fixture test, on the `verse_grammar` model
- [ ] Web `featureEnabled(key)`: server map authoritative, build-time flag demoted to
      compiled fallback, fail-CLOSED default for `follow_ups`; `featureFlags.test.ts` covers
      present/absent/server-unreachable
- [ ] Android `FeatureFlags` holder from `ConfigResponseDto`: compiled defaults, offline-safe,
      `follow_ups` fail-CLOSED; JVM tests; unknown/missing keys tolerated (fixture payload
      with extra keys parses)
- [ ] **Pilot:** follow-up chips (BITB-080) resolve per-platform through the registry — web
      behavior unchanged post-`NEXT_PUBLIC_FOLLOW_UPS_ENABLED`; Android controllable at
      runtime with no APK release; PR #1216's ad-hoc "Android renders behind its own flag"
      contract superseded
- [ ] Old-client tolerance proven: an old-shaped `/config` (no `features.web`/`features.android`)
      and a future-shaped one (extra unknown flags) both parse on all three clients
- [ ] Terraform vars + `env-manifest.yaml` rows for every flag × platform; no flag secrets —
      flags are public booleans only
- [ ] Backend tests (`pytest`), frontend (`vitest` + `tsc` + `lint`), Android JVM tests green;
      story file + BACKLOG.md updated per Backlog Hygiene

## Out of Scope

- Per-user or percentage targeting (anonymous app — would need a stable id = tracking)
- Language targeting per flag (cultural tone is already language-scoped by its own registry)
- Migrating `tts_enabled` or `citation_spans` to the registry (flat key must survive for old
  APKs anyway; `citation_spans` is web build-time and harmless — each can move later if ever
  needed)
- DB-backed/admin-UI hot toggling; client-side experimentation infra
- Server-internal flags (`query_expansion_enabled`, `chat_cultural_tone_enabled`,
  `content_safety_*`, …) — those are backend behavior, stay flat Pydantic settings

## References

- PR #1216 (`feature/web-follow-ups-flag`) — the driver; its "Contract for the other legs"
- BITB-119 read-aloud (`features.tts_enabled` — the runtime-server-flag precedent, both clients)
- BITB-075/BITB-156 (`GET /config` → web `useServerConfig` / Android `fetchConfigWithRetry`)
- `api/tests/fixtures/verse_grammar.json` + `frontend/src/lib/verseGrammar.generated.ts` +
  `VerseCorpusParityTest` — the parity-fixture model to replicate
- BITB-235 — story-ID collision practice

## ID Note

BITB-241 is double-claimed by open PRs #1203 (web read-aloud Firefox) and #1215 (pre-commit
stages). Whichever renumbers will very likely take 242; if so, this story renumbers to the
next free ID before merge (BITB-235 practice) and the changelog line records it.
