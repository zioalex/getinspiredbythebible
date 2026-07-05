# How to Roll Out Paraphrase Grounding (BITB-053)

Pass 2 of verse grounding detects when the LLM presents a Bible verse as
**unquoted prose** — e.g. Italian *"In Isaia 41:10 Dio ci dice di non temere
perché Lui ci rende forti"* — which pass 1 (quoted-span grounding) can never
see. In `append` mode it fixes this by appending the canonical verse text in
quotes right after the reference.

The append is **additive**: it injects verse text into the user-facing reply on
every response where the classifier fires, so a false positive is far more
visible than a pass-1 quote correction. For that reason the feature does not
ship enabled. It ships in **detect** mode — the classifier runs on all traffic
and counts what it *would* do, without ever editing text — and this document is
the path from that data to a deliberate enable (or a deliberate removal).

See also: [`api/chat/verse_grounding.py`](../api/chat/verse_grounding.py)
(`_apply_paraphrase_grounding`, `ParaphraseMode`),
[`api/config.py`](../api/config.py) (`grounding_paraphrases_mode`), and the
nested-parens observation alert in
[`deployment/monitoring.tf`](../deployment/monitoring.tf)
(`verse_grounding_paraphrase_brackets`).

## The three modes

`grounding_paraphrases_mode` (env var `GROUNDING_PARAPHRASES_MODE`, no deploy
needed — it's a container-app setting):

| Mode     | Classifier runs | Text edited | Metric emitted                  |
| -------- | --------------- | ----------- | ------------------------------- |
| `off`    | no              | no          | —                               |
| `detect` | yes             | **no**      | `paraphrase_detections`, `applied=false` |
| `append` | yes             | yes         | `paraphrase_detections`, `applied=true`  |

Default: `detect`.

Every detection also logs a structured line — `Scripture paraphrase detected
(not corrected)` at info level in detect mode, `Scripture fidelity issue
corrected` at warning level in append mode — carrying the reference, the
sentence that triggered the classifier (`original_quote`), and the canonical
text that would be (or was) appended.

## Phase 0 — ships automatically with this feature

Nothing to do. `detect` is the default, so once deployed the
`chat.verse_grounding.paraphrase_detections` counter starts accumulating with
`applied=false`. There is zero user-visible change.

## Phase 1 — measure (~2 weeks of traffic)

Run these in Application Insights (Logs) after enough traffic has accrued.

Detection volume and language breakdown:

```kusto
customMetrics
| where timestamp > ago(14d)
| where name == "chat.verse_grounding.paraphrase_detections"
| extend language = tostring(customDimensions["language"]),
         bracketed = tostring(customDimensions["bracketed"])
| summarize detections = sum(valueSum) by language, bracketed
| order by detections desc
```

Detection rate relative to chat volume (uses the grounding duration histogram's
count as the per-response denominator):

```kusto
let detections = customMetrics
    | where timestamp > ago(14d)
    | where name == "chat.verse_grounding.paraphrase_detections"
    | summarize d = sum(valueSum);
let responses = customMetrics
    | where timestamp > ago(14d)
    | where name == "chat.verse_grounding.duration_ms"
    | summarize r = sum(valueCount);
print detection_rate = toscalar(detections) * 100.0 / toscalar(responses)
```

Sample the actual detections for a manual precision check (this is the
important one — read the sentences, don't just count them):

```kusto
traces
| where timestamp > ago(14d)
| where message == "Scripture paraphrase detected (not corrected)"
| extend ref = tostring(customDimensions["reference"]),
         sentence = tostring(customDimensions["original_quote"]),
         canonical = tostring(customDimensions["canonical_quote"]),
         language = tostring(customDimensions["language"])
| sample 25
```

For each sampled row ask: **is this sentence actually restating the verse**, or
is it ordinary commentary *about* the verse ("John 3:16 is about God's love")
that the token-overlap classifier caught by accident? Commentary wrongly
flagged is precisely the failure mode that would, in `append` mode, bolt a
verse quotation onto a sentence that didn't need one.

## Phase 2 — decide

Enable `append` only if **both** hold:

1. **The problem is material.** Guideline: detections on ≳1% of chat responses,
   or a sustained daily count that you'd care about as a scripture-fidelity
   issue. If detections are near zero, the prompt rules (BITB-038) are already
   holding — set the mode to `off`, drop the pass in a cleanup PR, and close
   BITB-053 as not-needed-in-practice. Carrying dead code needs a reason too.
2. **Precision is high.** In the 25-row sample, false positives ≈ 0 (a single
   ambiguous case is worth discussing; several commentary hits mean the
   threshold — `PARAPHRASE_SIMILARITY_THRESHOLD` in
   `api/chat/verse_grounding.py` — needs recalibration before any enable).

Also glance at the `bracketed` split from Phase 1: those detections sit inside
a parenthetical reference like `(Isaia 41:10)`, where the append nests as
`(Isaia 41:10 ("Non temere…"))`. Cosmetic, but if the bracketed share is large
you may want to fix the insertion point before enabling rather than after.

## Phase 3 — enable

1. Set `GROUNDING_PARAPHRASES_MODE=append` on the backend container app.
2. Watch for the first days:
   - `applied=true` counts in `paraphrase_detections` (should track the
     detect-mode baseline — a jump means something else changed);
   - the `verse-grounding-paraphrase-brackets` alert in monitoring.tf, which is
     dormant in detect mode and becomes live now (>5 bracketed appends per
     15-min bin, 2 of 3 evaluations);
   - user feedback channels for complaints about odd quotations in replies.

## Rollback

Set `GROUNDING_PARAPHRASES_MODE=detect` (keeps measuring, stops editing) —
this is the safe first move on any doubt. Use `off` only if the classifier
itself is misbehaving badly enough that you don't even want the logging.
