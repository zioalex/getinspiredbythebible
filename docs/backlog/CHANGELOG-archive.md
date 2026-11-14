# Backlog Changelog (frozen archive)

This is the verbatim `## Changelog` section of the old hand-edited `docs/BACKLOG.md`, frozen
on 2026-11-13 (BITB-313). It is **not** appended to any more: the changelog is now derived from
git history, so there is nothing to hand-write and nothing to conflict on. Run
`make backlog-changelog` (or `python3 scripts/backlog.py changelog --since 2026-11-13`) for the
current entries.

The convention block below ("add your entry directly below this blockquote") is **obsolete**:
do not add entries to this file.

---

> **Convention (enforced since 2026-10-22): one entry per line, newest first, append-only.**
>
> `- YYYY-MM-DD: BITB-NNN <status> — <one-line summary> (#PR)`
>
> - Add your entry **directly below this blockquote**, at the top of the list.
> - **Never edit, reword, or reorder existing entries** — a status change gets a
>   *new* line (e.g. "BITB-NNN done — PR #123 merged").
> - Rationale: the previous format was a single giant narrative line that every
>   PR rewrote, so nearly every PR conflicted on this file. One entry per line
>   means only same-day same-position additions can collide, and those conflicts
>   are two trivial lines instead of a 2000-character paragraph.
>   - History before 2026-09-22 is preserved in git history (this section was
>   condensed once, at the 2026-10-22 restructuring).

- 2026-11-14: BITB-315 opened — probe the ML content-safety path in more than one language (CJK, RTL, Devanagari), BITB-291 follow-up
- 2026-11-14: BITB-314 opened — exclude synthetic ml-safety-path probe checks from the BITB-290 fallback-share SLO, BITB-291 follow-up
- 2026-11-11: BITB-294 opened — provision Azure Content Safety in prod + enable the openai_moderation,azure chain (BITB-292 follow-up)
- 2026-11-11: BITB-292 🔍 In Review — ml_only failover chain (CONTENT_SAFETY_ML_FAILOVER_CHAIN, e.g. openai_moderation,azure): Azure Content Safety tried after OpenAI Moderation, keyword fallback only when every configured classifier failed, per-hop failover_total labels
- 2026-11-11: BITB-290 🔍 In Review — keyword-fallback share SLO (content_safety.checks_total denominator), workbook tiles, multi-window burn-rate alerts replace the any-fallback alert
- 2026-11-13: BITB-313 opened — conflict-free, agent-friendly backlog: story-file front matter is the single source of truth, BACKLOG.md becomes a stub, `make backlog` query + changelog derived from git; supersedes BITB-287 req. 1 (merge driver ignored by GitHub)
- 2026-11-11: BITB-293 opened — 11-language safety golden set runner for a single moderation classifier (OpenAI Moderation first), follow-up of BITB-288 AC 2 (#1280)
- 2026-11-11: BITB-288 🔍 In Review — OPENAI_API_KEY wired into the backend Container App out-of-band (BITB-067 pattern), failover enabled in prod once the owner adds the secret (#1280)
- 2026-11-11: BITB-309 ✅ Done — privacy policy OpenAI disclosure merged before BITB-288; story moved to docs/DONE (#1287)
- 2026-11-11: BITB-309 🔍 In Review — privacy policy (11 languages) discloses OpenAI Moderation as the safety-check fallback and states OpenAI's 30-day abuse-monitoring retention; must merge before BITB-288 (#1280)
- 2026-11-11: BITB-238 ✅ Done — status drift fixed: help-seeking/theological exemption shipped in #1249 (merged 2026-11-08) but the entry still read Todo (#1278)
- 2026-11-11: BITB-239 ✅ Done — status drift fixed: it/fr/pt directed-harm recall shipped in #1261 (merged 2026-11-10); follow-up BITB-281 stays open (#1278)
- 2026-11-11: BITB-289 🚧 In Progress — Llama Guard breaker admits a single half-open probe with exponential cooldown backoff (10s→60s), safety check capped at an 8s total budget with jittered secondary retry; production benchmark remains an owner step (#1278)
- 2026-11-11: BITB-297 in review — one trusted-proxy client-IP resolver replaces three left-most-header copies; local-only gate rejects proxied requests; probe-gated request-chain endpoint; BITB-308 created (origin lock-down) (#1286)
- 2026-11-11: BITB-296..307 created — verified project review (live + executed evidence) and improvement plan: chat-history validation, trusted client IP, endpoint rate limits, Arabic/Hindi share image, SEO fixes, topic pages, Bible chapter pages, verse of the day, runtime/model alignment, secrets inventory + restore drill, roadmap refresh, API hygiene (`docs/audits/2026-11-11-improvement-plan.md`) (#1284)
- 2026-11-09: BITB-287 in progress — process & cost tooling: BACKLOG.md union merge driver for auto-resolving changelog append conflicts, registry cost telemetry (per-dispatch tokens/cost in child registry lines), budget guardrail (make check-llm-budget with OpenRouter credits check) (#1275)
- 2026-11-09: BITB-286 in progress — 2026-11-07→09 session cost retrospective: $20.27/80 sessions ledger, $13 durable infra vs $4.5 waste (verifier tool allowlist, misdiagnosis, reconciliation tax, free-lane routing); fixes in this PR: verifier tool allowlist, falsification-first rule, free-lane routing, session-per-incident, resume-over-rebrief, autoupdate labels, risk-tiered verification (+BITB-287 tooling PR) (#1275)
- 2026-11-09: BITB-239 🔍 In Review — it/fr/pt directed-harm recall restored ("adesso muori!", "Crève charogne", "morra seu idiota", "que tu vas crever"); "die to sin" wording (muoia in Cristo / morra para o pecado) unblocked (#1261)
- 2026-11-09: BITB-281 opened — pt "morra para o pecado, seu idiota" regression follow-up from BITB-239 (#1261)
- 2026-11-08: BITB-262 🚧 In Progress — capability×client parity registry seeded (35 capabilities × 8 contracts, re-verified against code: all WIP-plan GAPs shipped on Android, BITB-042 drift closed by #685, live red row is BITB-267 api) + graph/landscape renderer + CI freshness gates (#1258)
- 2026-11-10: BITB-272 slice 1 done (🚧 In Progress) — ml_only fails over to OpenAI Moderation before the keyword fallback, failure_class metrics, startup config warning, Llama Guard key fix; follow-ups BITB-288..292 opened
- 2026-11-08: BITB-278 opened — Android follow-up chips round: flip the default-off `CHAT_FOLLOW_UPS_ENABLED` BuildConfig gate on and restyle the stock SuggestionChip to match the web chip colors (light: white / #E6D0B8 border / #374151 label); user-reported "colors a bit off" when side-loading a flag-on build (BITB-080/149/254 follow-up)
- 2026-11-08: BITB-261 ✅ Done — stage 1 of the parity KG merged: OpenAPI artifact + stale-artifact CI gate + oasdiff-action (#1253); env-stripping determinism + audit regen adopted from #1251; follow-ups BITB-274/275/276/277 filed
- 2026-11-09: BITB-285 in progress — implemented: runbooks migrated into k8s/kubeopencode/README.md (sync/lockstep, pre-merge checklist, copilot, fallback, persistence; agents.md moved as sibling), deployment folder stubbed with anchor redirects (agent.yaml removed after zero-drift twin-check), ~30 live refs repointed (live-gate AGENT_YAML + both modes re-run green in-pod), AGENTS.md Repository Layout gains k8s/ (root-cause fix), stub-only-folder guard test; desktop manifest promoted from the owner-exported verified live spec with the agentImage pin as desired state (wake-or-delete = owner decision) (#1273)
- 2026-11-09: BITB-285 opened — owner ruling: k8s/kubeopencode/ is THE canonical KubeOpenCode manifest/docs home, deployment/kubeopencode/ obsolete; story covers runbook migration, manifest twin reconciliation, deprecation stub, AGENTS.md Repository Layout fix + stale ~L300 pointer, and the 30-hit live reference repoint (reproducible grep in the story); implementation deferred to a follow-up PR (#1272)
- 2026-11-09: BITB-282 opened — 2026-11-09 outage root cause: hardcoded ~62s startup-probe budget races worst-case cold boots (~100-115s kills observed); probe fields not Agent-spec-expressible — upstream kubeopencode issue drafted (BITB-271 pattern), filing is an owner step (#1272)
- 2026-11-09: BITB-283 corrected per the owner ruling — deployment/kubeopencode/ is obsolete (k8s/ is canonical): the deployment-folder agent-wf3.yaml addition is removed, parity tests retargeted to the k8s wf2/wf3 twins (whole-spec), rollback anchors moved to the k8s README; the k8s wf3 manifest verified field-for-field against the 2026-11-09 live export; desktop sketch still unverified (export/diff/pin owner steps; its init runs unpinned agent-opencode:latest) (#1272)
- 2026-11-09: BITB-284 opened — controller reconcile re-renders Deployment templates and reverts hand-patches (observed 2026-11-09 + verified in upstream source v0.1.9): trigger set, configRef-not-watched nuance, and "express it in the Agent spec" guidance documented in README "What the controller owns" (#1272)
- 2026-11-09: BITB-270 in progress — stream-stall watchdog implemented: message.part.delta heartbeat + tool-in-flight guard, STREAM_IDLE_SECONDS (180) stalled-stream registry line + best-effort abort; abort proven lossy on 1.18.31 (session.abort errors mid-generation), native chunkTimeout honored for custom providers only — plugin is the fix; 37/37 tests, hanging-mock e2e + clean control run
- 2026-11-08: BITB-280 in progress — pre-merge live-config load gate: CI boots a scratch opencode 1.18.31 on the committed opencode.json (zero plugin-load failures, roster/question-deny checks, self-test catches the injected 18:51 bug, env-gated subagent dispatch)
- 2026-11-08: BITB-279 in progress — generator constants (small_model, builtin fallbacks, dead MIMO/Zen IDs) moved to verified openrouter/:free models; test suite + agents.md now assert the free-tier tier-1 invariant (cross-provider rule retired) (#1259)
- 2026-11-08: BITB-279 in progress — fallback chains broken: opencode/* Zen models never served (no pod credentials) and paid tier-2 can't rescue an exhausted key; all tier-1 fallbacks + mechanical-lane primaries moved to verified openrouter/:free models (#1259)
- 2026-11-08: BITB-269 addendum — plugin load failed live (`Plugin export is not a function`): loader contract pinned (single default export; helpers split into task-reliability-helpers.ts; nested `properties.info.parentID` read), tests wired into CI + pod pre-flight, `make sync-opencode-configmap` now also fast-forwards the pod checkout so config and plugin code stay in lockstep (#1254)
- 2026-11-08: BITB-271 created — upstream opencode issue: subagent `question` call parks forever (no default deny/timeout/parent routing); paste-ready draft in the story, filing is an owner step (#1254)
- 2026-11-08: BITB-270 created — LLM stream-stall watchdog: error-driven fallback misses silently-stalled streams; stream-idle detection + abort/registry line with a tight threshold (#1254)
- 2026-11-08: BITB-269 in progress — subagent `question`-tool deadlock hung the orchestrator 9h34m (2026-11-07): question denied for all 11 subagents + dispatch hygiene rules; task-reliability plugin wiring + stuck-child watchdog in the same PR
- 2026-11-05: BITB-267 todo — backend verse parser misses a citation after `**`, `—` or `¿` (boundary gap vs web/Android) (BITB-189 follow-up)
- 2026-11-05: BITB-189 done — backend parses a citation directly after a closing bracket/quote (「…」约翰福音3:16) across 11 languages; shared-corpus parity cases added (#1250)
- 2026-11-04: BITB-266 renumbered from BITB-264 (264/265 claimed by PR #1248) — directed-harm taunt gaps found verifying BITB-238 (#1249)
- 2026-11-04: BITB-266 opened — directed-harm taunt gaps ("killing yourself", "you should") found verifying BITB-238
- 2026-11-04: BITB-238 🔍 In Review — exempt help-seeking/theological English phrases from Stage 1 directed harm
- 2026-11-08: BITB-257 🔍 In review — narrative exemption now requires a curated Bible killing event (killer→victim pair) after name-list anchors leaked modern given names (#1241)
- 2026-11-08: BITB-272 renumbered from BITB-267 — ID was already claimed by open PR #1250 (earlier claimant keeps 267); story file and references updated (#1241)
- 2026-11-08: BITB-257 🔍 In review — redesigned narrative exemption as a strict whole-message allowlist (mirrors BITB-238/#1249) after verification found denylist bypasses (#1241)
- 2026-11-04: BITB-257 🔍 In review — fail-safe narrative guard (option A): exemption needs a Bible anchor and no first-person marker; ar bare قتل restored; recall regressions re-blocked (#1241)
- 2026-11-04: BITB-272 created — make ML content-safety classification reliable (cross-provider failover, fallback-share SLO) so the BITB-257 fail-safe keyword fallback is rare (#1241)
- 2026-11-02: BITB-257 🔍 In review — keyword fallback no longer blocks third-person Bible narrative (en do-support/commandment guard, ar intent-only patterns, fr/it/es/pt/de past-tense guards); first-person threats still blocked with the card
- 2026-11-08: BITB-273 in progress — parity-ci oasdiff job failed on every api PR since #1253: pass workspace-relative spec paths to the oasdiff docker action (host github.workspace paths don't exist inside the container) (#1255)
- 2026-11-07: BITB-261 in progress — committed OpenAPI contract artifact (docs/parity/openapi.json) + offline export script, parity-ci.yml stale-artifact gate & oasdiff breaking-change report (PR #1253)
- 2026-11-03: BITB-258 in review — Llama Guard S11 combined with S1/S6/S10 now blocks with the self-harm reply + crisis card (`violated_categories` exposed on safety outcome); chat() + chat_stream() tests in 11 languages (#1248)
- 2026-11-03: BITB-265 in review — info/warning logs carry lengths only (no message or expansion text), sentinel tests on chat()/chat_stream() in 11 languages (#1248)
- 2026-11-03: BITB-256 verification fixes — allow-list-only sanitizer, hourly purge + 1..90 day retention, bounded writes, wider signature, psycopg2 exporter URL
- 2026-11-03: BITB-264/265 opened — follow-ups from BITB-256 verification (ru/zh/hi/ko topic detection coverage; query-expansion logging of user text)
- 2026-11-03: BITB-256 in progress — retrieval_miss_samples (r0009), fixed 90-day TTL + daily purge, provisional per-model thresholds pending search-eval p10
- 2026-11-07: BITB-260 ✅ Done — decision record + stage stories merged (#1237); implementation continues in BITB-261/262/263
- 2026-11-01: BITB-258 in review — Llama Guard S11 combined with other categories now blocks with the self-harm reason (crisis card + self-harm reply) (#1239)
- 2026-10-30: BITB-260 created — cross-client parity knowledge-graph decision record: per-layer OSS adopt/defer matrix (OpenAPI+oasdiff, registry, Mermaid, Neo4j CE lens), git artifact as store of record; stages filed as BITB-261/262/263
- 2026-10-30: BITB-261 created — Stage 1: committed OpenAPI contract artifact + stale-artifact CI check + oasdiff breaking-change PR report
- 2026-10-30: BITB-262 created — Stage 2: capability×client parity registry, living successor of docs/WIP/android-feature-parity-plan.md; first red row expected: BITB-042; gated on BITB-261
- 2026-10-30: BITB-263 created — Stage 3: on-demand local Neo4j lens for the development laptop (owner-requested; disposable view over the git artifact, no CI dependency); gated on BITB-262
- 2026-10-29: BITB-255 in review — crisis card on web + Android, Cloudflare country, self-curated registry; passed independent verify after 2 fix rounds
- 2026-10-29: BITB-257/258 opened — follow-ups from BITB-255 verification (keyword-fallback Bible-narrative card; Llama Guard S11 combos get no card)
- 2026-10-29: BITB-255 in progress — plan approved (crisis overrides profanity filter, directed_harm excluded, unverified numbers shown + flagged, Android Room migration)
- 2026-10-29: BITB-255 spec revised — country from Cloudflare IP geolocation, self-curated hotline registry with source + staleness checks (ThroughLine evaluated); BITB-256 threshold/retention confirmed
- 2026-10-28: BITB-256 spec — privacy-safe RAG retrieval-miss logging (derived signals only, no prompt text)
- 2026-10-28: BITB-255 spec — emergency critical path: deterministic hotline card first for threats to self or others
- 2026-10-29: BITB-259 created — spike: decision model (Clef-flash, Jev if access) for intent routing + topic detection, offline 11-language eval + shadow mode
- 2026-10-28: BITB-254 in progress — follow-up chips stop after a few turns: clients echo chips back so the model keeps seeing the trailer; history-aware verse filter; suppressed-chips counter (PR pending)
- 2026-10-29: BITB-224 in progress — root cause: azurerm standard web test enabled defaults to false and main.tf never set it; pin enabled=true + scheduled webtests-enabled guard in prod-deploy-drift.yml (PR pending)
- 2026-10-28: BITB-086 ✅ Done — both deferred client-side ACs (web reference consumer + corrupt-span degradation) completed via BITB-109 (PR #1055); backend contract shipped in PR #985; story moved to docs/DONE/ (this PR)
- 2026-10-28: BITB-253 created — Integration Tests intermittently fail at "Load CI test data"; follow-up to BITB-250
- 2026-10-28: BITB-252 created — Android read aloud stays on Pause when the TTS engine never starts; follow-up to BITB-247
- 2026-10-28: BITB-251 created — read-aloud fallback voice (Azure Speech or Piper), decided from BITB-247 data; follow-up to BITB-247/248
- 2026-10-28: BITB-250 done — cross-browser read-aloud e2e green on Chromium, Firefox, WebKit and Mobile Safari (#1226)
- 2026-10-28: BITB-249 done — iPhone reads the whole answer: chunks spoken one at a time from onend (#1226)
- 2026-10-28: BITB-248 done — Snap Firefox shows the "didn't respond" notice instead of a stuck Pause (#1226)
- 2026-10-28: BITB-247 done — read-aloud telemetry funnel on web and Android, weekly report and workbook (#1226)
- 2026-10-28: BITB-250 in progress — cross-browser read-aloud Playwright tests (Chromium, Firefox, WebKit) with browser-quirk speech engine profiles (PR #1226)
- 2026-10-27: BITB-247 in progress — widened to full read-aloud telemetry funnel (web + Android) with browser/OS family, daily aggregate, weekly report and workbook (PR #1226)
- 2026-10-27: BITB-249 in progress — read aloud stops after the first chunk on iPhone: speak chunks one at a time from onend (PR #1226)
- 2026-10-27: BITB-248 in progress — web read aloud still stuck on Pause on Snap Firefox: start watchdog no longer trusts speechSynthesis.speaking; follow-up to BITB-241 (PR #1226)
- 2026-10-27: BITB-246 created — visually check the read-aloud start-failure notice beside the action rail; follow-up to BITB-241 (renumbered from 244, taken on main by PR #1225)
- 2026-10-27: BITB-247 created — count read-aloud start failures (web telemetry); follow-up to BITB-241 (renumbered from 245, taken on main by PR #1225)
- 2026-10-27: BITB-241 done — web read aloud no longer hangs on Pause on Linux Firefox (PR #1203)
- 2026-10-27: BITB-223 fix — first apply failed: `verse_grounding_paraphrase_brackets` look-back 72h > Azure's 48h cap; gate moved to 2+ hot hourly bins/day (1-of-1 periods) + look-back regression test (PR pending)
- 2026-10-27: BITB-245 in review — pin the chat composer to the bottom on mobile; footer links and Get in Touch move to the main menu (#1224, PR #1225)
- 2026-10-27: BITB-244 in review — Bible version and language selects no longer overflow the mobile menu (#1223, PR #1225)
- 2026-10-27: BITB-243 renumbered from BITB-241 — that ID was claimed two days earlier by open PR #1203 (web read-aloud, Linux Firefox); content unchanged (PR #1215)
- 2026-10-27: BITB-235 in review — story-ID duplicate-claim CI check added (PR #1221)
- 2026-10-27: BITB-235 in progress — ID-allocation rule codified in AGENTS.md (origin/main + every open PR's story files, claim = open PR, first-claimant keeps on collision); BITB-241 double-claim resolved: #1203 keeps 241, #1215 renumbered to 243; CI duplicate-ID check still open (PR #1220)
- 2026-10-26: BITB-242 created — platform-selective feature flags: server-driven per-platform (web/android) flag registry on GET /config, explicit per-flag fail policies, parity fixture, follow-ups pilot (PR #1220)
- 2026-10-26: BITB-223 in progress — alert-rule rationalization: 4 redundant rules removed, 7 demoted (PT1H/P1D/PT15M), 2 noisy rules recalibrated with sustained-window gating; matrix finalized for all 32 rules (PR pending)
- 2026-10-26: BITB-243 opened — fast pre-commit commit stage (slow hooks moved to pre-push) (PR #1215)
- 2026-10-25: BITB-182 done — KubeOpenCode controller RBAC missing (leader election + CRD access); agents not starting (PR #1204)
- 2026-10-24: BITB-241 renumbered from 238 — that ID was taken on main by PR #1199 (stage-1 English "kill yourself" patterns); content unchanged (PR #1203)
- 2026-10-24: BITB-241 in progress — web read aloud stuck on Pause with no audio on Linux Firefox: no idle cancel, start watchdog with retry and notice (PR #1203)
- 2026-10-24: BITB-239/240 renumbered from 236/237 — those IDs were taken on main by PR #1202 (opencode model matrix + free-fleet expansion); content unchanged (PR #1199)
- 2026-10-24: BITB-237 created — free-fleet expansion: pre-gate verifier (Nemotron), family-matched tier-1 hops, usage-rank comment fix; follow-up to BITB-236 (PR #1202)
- 2026-10-24: BITB-236 done — agent model matrix 2.0: paid GLM-5.3/DeepSeek-V3.2-Exp primaries, gpt-oss-120b retired (PR #1202)
- 2026-10-24: BITB-236 in progress — agent model matrix 2.0: paid GLM-5.3/DeepSeek-V3.2-Exp primaries, gpt-oss-120b retired, nemotron free kept as tier-1 rescue hop
- 2026-10-24: BITB-235 opened — story IDs collide between concurrent PRs; header story renumbered 206 → 219, #1195 merged with stale BITB-214 (PR #1197)
- 2026-10-24: BITB-222 opened — header layout below 320px is unguarded (PR #1197)
- 2026-10-24: BITB-221 opened — header brand title truncates to "V…" at 320px (PR #1197)
- 2026-10-23: BITB-212 done — orchestrator delegation discipline enforced (PR #1193)
- 2026-10-23: BITB-219 done — hide header language switcher on mobile (PR #1191)
- 2026-10-24: BITB-193 in review — Stage-1 directed harm checked in every language (PR #1199)
- 2026-10-24: BITB-240 opened — native ar/ru/zh/hi/ko directed-harm patterns (PR #1199)
- 2026-10-24: BITB-238 opened — English "kill yourself" in help-seeking/theological questions blocked under every code (PR #1199)
- 2026-10-24: BITB-239 opened — recall lost by directed-harm tightening (PR #1199)
- 2026-10-23: BITB-142 done — first-run feature spotlight coach-marks with RTL support (PR #1192)
- 2026-10-23: BITB-220 done — audit all 128 Makefile targets, fix 13 defects, add regression tests (PR #1196)
- 2026-10-23: release v1.58.0 — release-please (#1167)
- 2026-10-23: BITB-234 created — second-tenant ($50 credit) rehearsal environment for the migration chain; production split and reservation-in-new-tenant declined with reasoning
- 2026-10-23: BITB-227 cancelled — reserved capacity not purchasable in current billing setup (owner-confirmed); BITB-231 inherits the compute lever
- 2026-10-23: BITB-223..233 renumbered from 212..222 — those IDs were taken on main by parallel sessions (BITB-212 delegation discipline, BITB-213..218 read-aloud epic + next bump); content unchanged (PR #1189)
- 2026-10-23: BITB-218 done — bump Next.js to 16.4.2 for critical RCE advisories (PR #1195)
- 2026-10-23: BITB-210 done + BITB-211 done — read-aloud voice availability, hidden verse list; follow-ups BITB-213/214/215/216/217 opened (PR #1190, #1194)
- 2026-10-23: BITB-150 collector metrics fixed — 90-day Postgres CPU/memory/storage evidence is now three contiguous 30-day Azure Monitor requests per metric (Azure truncated one 90-day request to ~31 days), merged and validated; any failed/truncated chunk fails the file and the run (PR #1189)
- 2026-10-23: BITB-150 collector throttling and alerts pagination fixed — bounded 429/503 retry with backoff in `run_cli`; Alerts `nextLink` (live shape `https://management.azure.com:443/...&ctoken=`) now validated by strict normalization instead of exact-host match; offline tests added (PR #1189)
- 2026-10-23: BITB-150 firewall helpers fixed — `az-pg-add-ip`/`list-rules`/`remove-ip` use `--server-name` for the server and `--name` for the rule; offline Makefile tests added (PR #1189)
- 2026-10-22: BITB-150 collectors repaired — native `az rest` Logs/Alerts queries (no auto-installing extension), Postgres/workspace discovery instead of a hard-coded server, runtime-only DATABASE_URL via PG* env, failures recorded in MANIFEST + non-zero exit, Bash entry point is a thin python3 wrapper, expanded offline regression tests in the PR gate (PR #1189)
- 2026-10-22: BITB-150 collector output fixed — timestamped evidence stays inside the cost-evidence/ Docker bind mount; Bash/workflow paths aligned and offline regression coverage added
- 2026-10-23: BITB-150 Phase 0 analysis COMPLETE — 25/50 estimate confirmed (monitoring 27.2%, DB 50.6%, 92.73 CHF/mo avg); 11 follow-up stories filed: BITB-223/213/214/215/216/217/218/219/220/221/222 (alert rationalization, disabled web tests, LA cap, sampling audit, reservation, dead indexes, disk shrink, halfvec, B1ms, auto-grow warning, log hygiene) (PR #1189)
- 2026-10-22: BITB-150 collector image fixed again — base image moved to python:3.12-slim (the azure-cli image is Azure Linux, no apt-get); new cost-collector-build.yml CI gate builds + smoke-tests the image on every PR touching it (PR #1189)
- 2026-10-22: BITB-150 collector fixed — zero-extension commands (`az rest` for the non-existent `az costmanagement query`), `--metrics` flag, dynamic 3-month windows; fixes the docker-image build failure (PR #1189)
- 2026-10-22: next 16.4.0 → 16.4.2 — fixes critical RCE (GHSA-2464-fhr4-w9xw) + high DoS (GHSA-p3m5-59mp-jv5r); unblocks npm-audit gate for all PRs (PR #1189)
- 2026-10-22: BITB-150 in progress — phase 0 started: cost-evidence collection scripts, SPN creator, weekly workflow (PR #1189)
- 2026-10-22: BITB-211 in progress — read aloud no longer reads the hidden VERSES marker, web + Android
- 2026-10-22: BITB-210 in progress — web Listen hidden silently without an offline voice; menu explanation + per-device online-voice opt-in
- 2026-10-22: BITB-205 done — PR #1188 merged; restored deploy workflows' real Azure resource names; BITB-206/207/208/209 opened as follow-ups
- 2026-10-21: BITB-196 in review — murder-suicide / elliptical third-party phrasing routes to the ambiguous safety branch, 11 languages; BITB-201/202/203 opened; BITB-186 closed — PR #1169
- 2026-10-19: BITB-198 in review — native ru/zh/hi/ko violence patterns, Bible-narrative-aware; BITB-204 filed
- 2026-10-14: BITB-186 in review — missed zh/ko/ru/hi crisis phrasings + a ru negation guard
- 2026-10-13: BITB-185 in review, PR #1166 — v2 hardened; hard-violence terms always block, nonce-delimited classifier prompt; BITB-196/197/198/199 opened as follow-ups
- 2026-10-13: BITB-185 v2 — second-opinion LLM classifier for ambiguous self-harm + violence; crisis message in all 11 languages; BITB-195 cancelled, decided by it
- 2026-10-13: BITB-185 in review — keyword fallback is script-agnostic, self-harm wins over plain violence; BITB-193/194/195 opened as follow-ups
- 2026-10-12: BITB-179 done — PR #1163 merged; BITB-189/190/191/192 opened as follow-ups (bracket citation, spaced-range parity, Android range fallback, CJK link label)
- 2026-10-11: BITB-183 done — PR #1148; BITB-186 opened as follow-up; BITB-185 opened; BITB-182 in progress — PR #1147; BITB-183/184 opened; BITB-178 done — PR #1145; BITB-179/180/181 opened; BITB-163 done — PR #1140; BITB-177 npm-audit gate fix; BITB-157 in progress; BITB-168 in progress — PR #1133; BITB-119 in review — PR #1132; BITB-175/176 opened — localized What's New, background read-aloud
- 2026-10-11: BITB-182 done — PR #1147 merged; BITB-187/188 opened as follow-ups
- 2026-10-04: BITB-174 done — Android tablet chat bubbles adaptive, PR #1129
- 2026-10-04: BITB-173 done — runtime fallback chain rebuilt with valid model IDs, PR #1128
- 2026-10-03: BITB-172 done — repo-vs-live drift fixed, PR #1126; BITB-171 done — agent-default-wf2 self-contained, PR #1125; BITB-170 done — kubeopencode README, PR #1124
- 2026-09-30: BITB-169 in progress — task-reliability plugin L0+L1, PR #1123; BITB-169 created; Ko-fi page confirmed live, $80/month infra-cost goal; BITB-168 created — Support-Us discoverability
- 2026-09-29: BITB-149 done — Android follow-up-question chips, PR #1109; BITB-165 created — auto-update opted-in PR branches; BITB-164 done — VersesPanel Cited-tab parser on shared grammar, PR #1117
- 2026-09-27: backlog-vs-main audit — 10 stale stories marked done (BITB-125/152/122/067/057/126/123/129/138/042); BITB-121/128/046 corrected in place
- 2026-09-26: BITB-113 done — verse-parser grammar unification, PR #1105; BITB-164 created — VersesPanel.kt fourth grammar copy
- 2026-09-25: BITB-158 v2 rewrite — corrected base image + pre-commit cache design; BITB-163 filed as follow-up
- 2026-09-24: BITB-156 in progress — PR #1103 open, Android Part A
- 2026-09-22: BITB-074 done — Support Us funding entry points, PR #1084; BITB-158 created; BITB-094 in progress; BITB-127 created; BITB-161 created; BITB-084 Part C done via BITB-102; BITB-155 created — OpenRouter paid Llama primary + Gemma 4 31B fallback
- 2026-09-18: BITB-152 done — KubeOpenCode strict-tier sandbox hardening, PR #1045

**Verification Note (2026-04-20):** PR status reconciliation pass completed against GitHub.
Confirmed merged PRs: #68, #171, #182, #191, #193, #194, #195, #196, #197, #208, #225, #226,
\#227. Confirmed closed-unmerged: #309.
