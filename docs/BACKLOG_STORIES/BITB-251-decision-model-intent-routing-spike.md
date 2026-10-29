# BITB-251: Spike — Decision Model (Clef / Jev) for Intent Routing and Topic Detection

**Status:** 🎯 Todo (spec confirmed 2026-10-29)
**Priority:** P2
**Size:** M
**Created:** 2026-10-29
**Type:** Spike (offline evaluation + shadow mode; no routing change)

## User story

As the maintainer, I want to know whether a *decision model* (Cloudflare **Clef-flash**, or TypeSafe
**Jev**) can replace the LLM call that routes every chat message. Today that call is a full
generative round trip on the critical path, so the switch would only make sense if it is at least as
accurate in all 11 languages, faster, and gives calibrated confidence. I want that answered with
numbers before we change any routing.

## Background

Decision models do not generate text. You send an input and typed questions (yes/no,
multiple-choice, ranking); they return a probability for every allowed answer. Up to 64 questions
fit in one call.

| | Clef-flash (Cloudflare) | Jev (TypeSafe AI) |
|---|---|---|
| Availability | Workers AI, GA since 2026-10-01 | Early access (waitlist) |
| Weights | Open, Apache 2.0 (9B), self-hostable | Closed |
| API | Same API as Jev (endpoint + model name differ) | — |
| Price (vendor/third-party) | ~$0.038 per 1M input tokens; hosted context 24K | Not public |
| Multilingual evidence | **None found** | **None found** |

All performance claims (latency, accuracy, calibration) are vendor-reported. Establishing them for
*our* traffic and *our* 11 languages is the point of this spike.

## Today

- **Intent routing:** `ChatService._detect_intent` (`api/chat/service.py:186`, timed as the
  `intent` stage).
  - Runs on every chat and stream request when `content_filter_intent_detection` is on (default
    `True`), after content safety and before scripture search.
  - Sends the prompt `detect_intent_prompt` (`api/chat/prompts.py:768`) to the main chat LLM
    (`temperature=0.0`, `max_tokens=20`, per-language `model_override`).
  - Takes the first word of the reply as one of `COMFORT, GUIDANCE, CURIOSITY, VERSE_LOOKUP,
    NEEDS_CLARIFICATION, OFF_TOPIC, GENERAL`. Anything else, or any error, becomes `GENERAL` (fail-open).
  - The asymmetric "when in doubt, choose the other category" rules for `OFF_TOPIC` and
    `NEEDS_CLARIFICATION` live only in the prompt text, so they cannot be tuned or tested in code.
- **What intent drives:** the off-topic short-circuit (`_handle_off_topic`), the BITB-078
  clarifying-question gate (`_wants_clarification`), and the BITB-151 cultural-tone gate
  (`_wants_cultural_tone`).
- **Topic detection:** `detect_topics()` (`api/chat/topics.py:1043`) is a substring scan over 13
  topics' keywords. It is used only for search boosting, behind `topic_boosting_enabled` (default
  `False`).

## Functional requirements

1. **Labelled evaluation set:** `api/decision_eval/data/intent_cases.yaml` (or similar).
   - **Size:** at least 30 messages per language for all 11 (en, it, de, es, fr, pt, ar, ru, zh, hi, ko).
   - **Labels:** each message has a gold intent label and gold topic labels (multi-label, the 13
     canonical topics from `canonical_topics()`).
   - **Coverage:** every intent label in every language, deliberately including the hard boundaries:
     - OFF_TOPIC vs GENERAL;
     - NEEDS_CLARIFICATION vs a vague-but-answerable message;
     - VERSE_LOOKUP written in each language's citation forms (CJK no-space, German comma, Arabic,
       Devanagari digits).
   - **Sources:** seed from `api/golden_set/test_cases/*.yaml` and existing intent tests. Never from
     real user messages.
2. **Decision provider:** add a `DecisionProvider` interface in `api/providers/base.py`.
   - **Clients:** one HTTP client in `api/providers/` serving both Clef and Jev (shared API), plus a
     factory entry in `factory.py` following the LLM/embedding `match/case` pattern.
   - **Config:** in `api/config.py` and `scripts/env-manifest.yaml`: `DECISION_PROVIDER`
     (`none`|`clef`|`jev`), endpoint, model, API key, timeout.
   - **Intent question:** one multiple-choice question over the 7 labels. The label descriptions
     come from the same source as `detect_intent_prompt`, so the two never drift.
   - **Topic questions:** 13 yes/no questions, one per canonical topic, sent **in the same call**.
   - **Untrusted input:** the user message is wrapped as untrusted data, the same way
     `safety_second_opinion.py` does it.
3. **Offline harness:** a runner (CLI, like `api/search_eval/runner.py`) that scores on the labelled
   set:
   - (a) the current LLM classifier, with the production provider and per-language overrides;
   - (b) Clef-flash;
   - (c) Jev, only if early access exists by the time the spike runs.

   It reports, per language and overall:
   - **Accuracy:** intent accuracy, macro-F1, and a confusion matrix. Report OFF_TOPIC false
     positives separately, because a wrong OFF_TOPIC means a real question gets no scripture.
   - **Topics:** micro/macro-F1 against the gold topic labels, compared with `detect_topics()`.
   - **Calibration (decision models):** a reliability table (10 bins) plus expected calibration
     error (ECE).
   - **Thresholds:** a threshold sweep for OFF_TOPIC and NEEDS_CLARIFICATION, giving the
     probability at which each beats the LLM's false-positive rate.
   - **Latency:** p50 and p95.
   - **Cost:** estimated cost per 1,000 requests.

   The report goes in a dated file under `api/reports/` (or `docs/audits/`), reproducible from the
   runner per *Reproducible Repo Analyses*.
4. **Shadow mode in production**, behind `decision_shadow_enabled` (default `False`), plus an
   optional sample rate.
   - **What it does:** when on, `_detect_intent` also calls the decision provider concurrently and
     records, for each request:
     - the LLM label;
     - the decision model's top label and its probability;
     - topics above 0.5;
     - decision-model latency;
     - whether the two labels agree.
   - **What it never does:** the shadow result never changes routing. A slow or failing shadow call
     must not delay the response: give it a hard timeout, cancel it, and count the error.
   - **Where it goes:** OpenTelemetry attributes or counters (an agreement rate per language and
     label, and a latency histogram), using the existing metric names and patterns in
     `api/utils/metrics.py`. The message text is never logged.
5. **Write-up:** a Findings section in this story with a go/no-go recommendation per language and
   per use. If the result is go, the recommendation includes proposed thresholds and a rollout plan.

## Non-functional requirements

- **All 11 languages** are evaluated individually. A model that wins overall but loses in ar, hi,
  zh or ko is a **no-go** for those languages. Per-language routing (as with
  `language_model_overrides`) is a legitimate outcome.
- **Fail-open stays.** Production routing behaviour is unchanged, byte for byte, with the shadow flag
  off. With the flag on, user-visible behaviour is still unchanged.
- **Latency:** with shadow on, the p95 of the `intent` stage rises by no more than 50 ms. The shadow
  runs in parallel with the LLM call, capped by its own timeout.
- **Privacy:** before shadow mode is enabled in production, the privacy policy
  (`frontend/src/app/[locale]/privacy`, all 11 locales) lists the decision-model provider as a
  processor. Spike data uses only synthetic or golden-set messages.
- **Secrets:** API keys come from env or Key Vault, never committed. Add a Terraform variable or
  secret only if shadow is enabled in Azure.

## Acceptance criteria

- [ ] **Labelled set:** at least 30 cases per language × 11 languages, every intent label present in
      every language. A loader test validates the schema and the coverage.
- [ ] **Decision provider:** `DecisionProvider` + Clef client + factory + config, with unit tests on
      a mocked HTTP transport. The tests cover the request shape, probability parsing, timeout,
      non-200 status, malformed body, and rejection of labels outside the allowed set.
- [ ] **Offline runner:** produces the per-language report (accuracy, macro-F1, confusion matrix,
      ECE, threshold sweep, p50/p95, cost) for the LLM baseline and Clef-flash. The runner is tested
      on a tiny fixture with a fake provider.
- [ ] **Parametrized cross-language test** (all 11 languages): the shadow path builds the same
      question payload, and never changes the routed intent, whatever the shadow returns or raises.
- [ ] **Shadow-path tests:**
  - flag off → no decision call;
  - flag on → the result is recorded, routing is unchanged, a slow or failing provider does not delay
    the response, and no message text reaches logs or metrics;
  - integration tests through both `chat()` and `chat_stream()`.
- [ ] **Topics:** decision-model topic F1 is reported next to `detect_topics()` on the same set.
- [ ] **Findings:** the go/no-go per language, with the report attached, is written into this story.
- [ ] **Jev:** compared if early access is available; otherwise recorded as "not evaluated — no access".
- [ ] *(Owner)* Shadow mode runs in production for 7 days, and the agreement and latency numbers
      are added to Findings.

## Out of scope

- Switching production routing to the decision model. That is a follow-up story, gated on the
  Findings.
- The safety second opinion (`api/utils/safety_second_opinion.py`), verse reranking after hybrid
  search, BITB-053 paraphrase detection, and golden-set LLM-as-judge checks. Each gets its own
  follow-up story if this spike is a go.
- Self-hosting Clef weights (on Azure or Ollama). Note it as an option in Findings only.
- Fine-tuning (Cloudflare RL fine-tuning service).
- Android and frontend: intent is backend-only, so no client change.

## Open questions

1. Does Clef-flash's hosted context (24K) and question limit change if the intent and topic
   questions grow? Not expected: the payload is far below both.
2. Workers AI auth from Azure Container Apps: use an account-scoped API token. Confirm rate limits
   for shadow traffic at the expected sample rate.
3. If calibration is poor (high ECE), are probabilities still useful after per-language threshold
   tuning, or does that cancel the main advantage over the LLM?
4. Should a go decision drop the LLM intent call entirely, or keep it as the fallback when the
   decision provider is down? The fail-open default to `GENERAL` exists either way.

## References

- Evaluation discussion: 2026-10-29 session; candidates ranked intent > safety second opinion >
  reranking > paraphrase > golden-set judges.
- [Cloudflare releases open-weight Clef decision models](https://letsdatascience.com/news/cloudflare-releases-open-weight-clef-decision-models-c52886d6)
- [Cloudflare Clef pricing explained](https://www.eesel.ai/blog/cloudflare-clef-pricing)
- [Clef-flash price cut, 24K hosted context](https://latenode.com/news/cloudflare-cuts-clef-flash-price-trims-hosted-context-to-24k)
- [Introducing Jev](https://yourstory.com/ai-story/what-is-jev-typesafe-ai-decision-model)
- [Jev decision models — what you need to know](https://www.thoughtworks.com/insights/blog/generative-ai/jev-decision-models-what-need-know-why)
