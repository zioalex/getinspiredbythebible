# Testing Suggested Follow-Up Chips (BITB-178)

The follow-up chips (BITB-080 backend + web, BITB-149 Android) ship **dark**:
`CHAT_FOLLOW_UPS_ENABLED` defaults to `false`. This guide shows how to switch them on
locally, measure them with the curated golden set, and see them on an Android debug build.

## 1. Enable the flag locally

Put the variable in the env file your stack uses (every compose file passes it through,
default `false`):

```bash
echo 'CHAT_FOLLOW_UPS_ENABLED=true' >> .env.local        # then: make docker-up
echo 'CHAT_FOLLOW_UPS_ENABLED=true' >> .env.dev          # then: make docker-up-dev (API on :8001)
echo 'CHAT_FOLLOW_UPS_ENABLED=true' >> .env.production   # then: make docker-up-local-prod
```

Restart the stack with the matching command so the container picks the variable up.

Production is unaffected: Terraform's `chat_follow_ups_enabled` also defaults to `false`.

> A small local Ollama model may not emit the `<!-- FOLLOWUPS: ... -->` trailer reliably.
> If chips are missing or flaky locally, retry with a cloud model (`LLM_PROVIDER=openrouter`)
> before concluding the feature is broken.

## 2. Run the golden set against a live backend

The set lives in `api/golden_set/test_cases/follow_ups.yaml` (73 cases: 11 languages x
expected x2, verse-citing, suppressed x2, multi-turn, plus a keyword-crisis case for the 7
languages that have one).

```bash
make follow-up-eval                                   # everything, http://localhost:8000
make follow-up-eval ARGS="--language it,de"           # a subset
make follow-up-eval ARGS="--scenario suppressed --base-url http://localhost:8001"
python scripts/run_follow_up_eval.py --mode json --out results.json
```

Flags: `--base-url`, `--mode stream|json` (stream is what the apps use), `--language`,
`--scenario`, `--case`, `--delay` (seconds between cases, default 3), `--timeout`, `--json`,
`--out PATH`. Exit codes: `0` all pass, `1` any failure, `2` backend unreachable.

Each case uses a fresh `session_id`; HTTP 429/503 are retried (honouring `Retry-After`).

### Scenarios

- **expected**: a normal study or prayer question must yield 2-3 chips.
- **verse-citing**: as above, and any verse reference inside a chip must also be cited in the
  answer (no fabricated references).
- **suppressed**: a crisis / help-seeking message or an off-topic message must yield **no** chips.
  Crisis cases come in two kinds. `crisis-ml` cases (`fu-<lang>-04`) are indirect wording that
  needs a content-safety ML classifier to be recognised. `crisis-keyword` cases (`fu-<lang>-07`)
  use wording that the built-in keyword self-harm fallback matches, so they work on a local
  stack with no classifier. The fallback only has patterns for en, it, de, es, fr, pt and ar;
  **ru, zh, hi and ko have none**, so those languages only get the `crisis-ml` case and rely on
  the configured classifier.
- **multi-turn**: the runner taps the first chip and sends it as turn 2 with history; turn 2
  must also yield valid chips, must not repeat the tapped question, and must not repeat turn 1's
  chip set.

### Reading the report

The report lists each case (with failed checks), then totals per language and per scenario.
Checks: chip count, length (<= 120), no markup, no duplicates, chip language matches, no
`FOLLOWUPS` trailer in the answer, no fabricated references. The `<!-- VERSES: ... -->`
comment the model appends to scripture answers is expected and is not treated as a leak;
only a `FOLLOWUPS` trailer is.

- If every `expected` case returns zero chips the report prints
  `CHAT_FOLLOW_UPS_ENABLED is probably off on this backend`.
- Crisis cases depend on the configured **content-safety provider**. A crisis case that shows
  chips usually points at the safety configuration, not at the chips feature.

## 3. Manual checklist for on-device testing

```bash
make follow-up-checklist ARGS="--language it"
```

Prints a markdown checklist (one line per case, grouped by language, with the expected
behaviour) to tick off while using the app. No network needed.

## 4. See the chips on an Android debug build

Debug builds default to the emulator's host loopback (`http://10.0.2.2:8000/`).

- **Emulator:** `make android-build`, install the APK, done.
- **USB device:** forward the port and point the build at it:

  ```bash
  adb reverse tcp:8000 tcp:8000
  cd android && ./gradlew assembleDebug -PbaseUrl=http://localhost:8000/
  ```

- **Same Wi-Fi (LAN IP):** `./gradlew assembleDebug -PbaseUrl=http://<your-LAN-IP>:8000/`
  (the compose stack binds `0.0.0.0:8000`).

Make sure the backend was started with `CHAT_FOLLOW_UPS_ENABLED=true`, then ask a normal
question in the app: 2-3 chips should appear under the answer. Crisis and off-topic messages
should show none.
