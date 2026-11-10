# parity-graph

The guard and compiler for the cross-client parity registry
([`docs/parity/registry.yaml`](../../docs/parity/registry.yaml)) — BITB-260
stage 2 (BITB-262). The registry is the store of record: every user-facing
capability × every client (`api`, `web`, `android`, `ios` planned) with a
parity status and evidence an independent verifier can open.

Two scripts, following the `tools/repo-metrics/` convention (`analyze.py` +
`render.py` + tests, offline, no DB):

| Script | Reads | Writes |
|---|---|---|
| `analyze.py` | `docs/parity/registry.yaml`, its schema, the evidence paths it cites, the Android strings files + `.github/workflows/android-ci.yml` | `docs/parity/graph.json` (committed; BITB-263's Neo4j importer consumes it) |
| `render.py` | `docs/parity/registry.yaml` | `docs/parity/landscape.md` (committed; Mermaid container diagram + status matrix + drift watch) |

## Zero to running

Prerequisites: a Python 3.11+ environment with `jsonschema` and `PyYAML`
installed (`pip install jsonschema PyYAML`; CI pins
`jsonschema==4.26.0 PyYAML==6.0.3`). Nothing else — no database, no LLM keys,
no Node, no network.

```bash
# Validate the registry and (re)generate the derived artifacts:
python tools/parity-graph/analyze.py     # → docs/parity/graph.json
python tools/parity-graph/render.py     # → docs/parity/landscape.md

# Freshness gates (what CI runs; exit 1 with a diff when stale):
make parity-registry-check
# or directly:
python tools/parity-graph/analyze.py --check
python tools/parity-graph/render.py --check

# The drift watch as standalone markdown (CI appends this to the job summary —
# drifted rows are INFORMATIONAL, never failures):
python tools/parity-graph/render.py --summary

# Tests (offline):
python -m pytest tools/parity-graph/ -q
# or with bare python3 (no pytest needed):
python3 tools/parity-graph/test_analyze.py && python3 tools/parity-graph/test_render.py
```

## What analyze.py validates

Four layers, all fail-closed:

1. **Schema** — `registry.schema.json` (jsonschema): the
   `synced | drifted | partial | absent | obligated | n/a` vocabulary,
   evidence required for synced/drifted/partial, story required for
   obligated, all four clients present per capability, negative obligations
   as first-class rows.
2. **Cross-references** — unique ids; every capability's `contracts` exist.
3. **Evidence paths** — every evidence entry that starts with a repo root
   (`api/`, `frontend/`, `android/`, ...) must exist on disk (a `:LINE` or
   `:LINE-LINE` suffix is stripped first). A row citing a file that isn't
   there is exactly the plausible-but-wrong edge BITB-260 forbids.
4. **Strings cross-check** — the registry's locale claims and Android
   key-completeness are re-derived from the same files the Android CI
   `translation-validation` job validates, using the job's own extraction
   regex **read out of `.github/workflows/android-ci.yml` on every run**. If
   that job ever changes its pattern, `analyze.py` fails until it is updated
   to match — the two validators cannot silently disagree. A missing Android
   key fails here for the same reason it fails there.

## Status vocabulary

`synced` · `drifted` · `partial` · `absent` · `obligated` · `n/a`

Drifted/partial/absent rows are **the payload, not failures**: they render in
`docs/parity/landscape.md`'s drift watch and in the parity CI job summary, and
stay red until their story closes. Only invalid registries and stale
artifacts fail CI.

## Adding or updating rows

1. Read the code first — open every file you are about to cite (rows must be
   TRUE, not plausible; a stale plan is a source of leads, never of truth).
2. Edit `docs/parity/registry.yaml`. Cite concrete paths in `evidence:`
   (they are existence-checked), the tracking `story:` (BITB-NNN) and landed
   `pr:` numbers. Negative obligations ("iOS ships no verse regex") are rows
   with `kind: negative-obligation`.
3. Regenerate and commit both artifacts on the same PR:

   ```bash
   python tools/parity-graph/analyze.py && python tools/parity-graph/render.py
   ```

4. `make parity-registry-check` (and CI) verify everything is consistent.

## Determinism

`graph.json` sorts every key and list; `landscape.md` derives only from the
registry (including its `updated:` date, never `now()`). Two runs on the same
tree are byte-identical — a diff is meaningful, never churn. Never hand-edit
`graph.json` or `landscape.md`; regenerate them.

## CI

The `registry` job in [`.github/workflows/parity-ci.yml`](../../.github/workflows/parity-ci.yml)
runs the schema/strings validation, both freshness checks, this directory's
tests, and appends `render.py --summary` to the job summary. It triggers on
registry/tool/parity-doc changes **and** on the strings files the cross-check
reads (`android/app/src/main/res/**`, `frontend/messages/**`).
