# KubeOpenCode Agent Model Table (BITB-123)

Agent definitions live in `.opencode/agents/*.md` and are auto-loaded into
KubeOpenCode containers. This file documents the model tiering mirrored in
`spec.config.agent` in `agent.yaml` (primary model + `fallbackModels`).

| Agent | Primary model | Fallback | Notes |
|---|---|---|---|
| orchestrator | `github-copilot/claude-opus-4.6` (paid) | `opencode/muse-spark-1.3-contributor-free` | Primary planner; fallback required in spec |
| android-expert | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | Kotlin/Compose builder |
| fullstack-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | FastAPI/Next.js/PG builder |
| infra-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | Azure/Terraform/CI builder |
| android-gemini | `openrouter/qwen/qwen3-coder` | `opencode/muse-spark-1.3-contributor-free` | Paid-tier coder (BITB-023); needs `OPENROUTER_API_KEY` |
| data-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | pgvector/Alembic/embeddings |
| verse-parity-keeper | `opencode/mimo-v2.5-free` | `opencode/muse-spark-1.3-contributor-free` | 3 parsers in sync, 11 languages |
| i18n-qa | `opencode/mimo-v2.5-free` | `opencode/muse-spark-1.3-contributor-free` | Locales/translations QA |
| verifier | `opencode/nemotron-3.5-lightning-free` | `opencode/muse-spark-1.3-contributor-free` | Read-only test runner (`edit: deny`) |
| risk-auditor | `opencode/nemotron-3.5-lightning-free` | `opencode/muse-spark-1.3-contributor-free` | Read-only audit |
| failure-forecaster | `opencode/nemotron-3.5-lightning-free` | `opencode/muse-spark-1.3-contributor-free` | Read-only 12-month forecast |
| seo-auditor | `opencode/nemotron-3.5-lightning-free` | `opencode/muse-spark-1.3-contributor-free` | Read-only SEO audit |

Fallbacks are served by the `opencode-runtime-fallback@0.2.4` plugin (retry on
`[429, 500, 502, 503, 504]`, 1 attempt, 120 s cooldown, 45 s timeout, notify on
fallback). Project is open source, so NVIDIA trial-model data logging on the
`nemotron` models is acceptable.
