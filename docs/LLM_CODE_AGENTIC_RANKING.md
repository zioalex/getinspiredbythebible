# LLM Model Ranking for Code Agentic Capabilities (Comprehensive)

**Data Sources:**
- **Primary:** Aider Polyglot Benchmark (225 Exercism exercises across 6 languages) — measures real-world code editing in a repository context
- **Secondary:** SWE-bench Verified (500 human-verified GitHub issues) with various agents (mini-SWE-agent, OpenHands, SWE-agent, etc.)
- **Tertiary:** LiveCodeBench, BigCodeBench, EvalPlus (HumanEval+/MBPP+), Chatbot Arena
- **Model Info:** Hugging Face model hub, official provider documentation

**Last Updated:** September 2026

---

## Top 25 Models Ranked by Aider Polyglot Score (Pass@2) + SWE-bench Corroboration

| Rank | Model | Provider | Aider Pass@2 | Aider Pass@1 | Cost/Run | SWE-bench Verified (mini-SWE) | Context Window | Thinking/Reasoning | API Pricing (In/Out per 1M) | Open Weights |
|------|-------|----------|-------------|--------------|----------|-------------------------------|----------------|-------------------|----------------------------|--------------|
| **1** | **GPT-5 (high)** | OpenAI | **88.0%** | 52.0% | $29.08 | ~65% (est.) | 400K / 256K | Configurable (high/med/low) | $1.25 / $10.00 | ❌ |
| **2** | **GPT-5 (medium)** | OpenAI | **86.7%** | 49.8% | $17.69 | ~62% (est.) | 400K / 256K | Configurable | $1.25 / $10.00 | ❌ |
| **3** | **o3-pro (high)** | OpenAI | **84.9%** | 43.6% | $146.32 | ~62% | 200K | High reasoning effort | $20.00 / $80.00 | ❌ |
| **4** | **Gemini 2.5 Pro (32k think)** | Google | **83.1%** | 46.2% | $49.88 | ~58% | **2M / 1M** | 32K thinking tokens | $1.25 / $10.00 | ❌ |
| **5** | **GPT-5 (low)** | OpenAI | **81.3%** | 43.1% | $10.37 | ~58% (est.) | 400K / 256K | Configurable | $1.25 / $10.00 | ❌ |
| **6** | **o3 (high)** | OpenAI | **81.3%** | 40.0% | $21.23 | ~55% | 200K | High reasoning effort | $10.00 / $40.00 | ❌ |
| **7** | **Grok-4 (high)** | xAI | **79.6%** | 40.9% | $59.62 | — | 256K | High reasoning effort | ~$3.00 / $15.00 | ❌ |
| **8** | **Gemini 2.5 Pro (default)** | Google | **79.1%** | 44.9% | $45.60 | ~58% | **2M / 1M** | ~8K default thinking | $1.25 / $10.00 | ❌ |
| **9** | **o3 + GPT-4.1 (architect)** | OpenAI | **78.2%** | 34.8% | $17.55 | — | 200K + 1M | High + editor model | $10/$40 + $2/$8 | ❌ |
| **10** | **DeepSeek-V3.2-Exp (Reasoner)** | DeepSeek | **74.2%** | 39.6% | **$1.30** | ~52% | 128K | Full reasoning trace (R1-style) | **$0.14 / $1.10** | ✅ |
| **11** | **Gemini 2.5 Pro Preview 05-06** | Google | **76.9%** | 36.4% | $37.41 | ~55% | 2M | Default thinking | $1.25 / $10.00 | ❌ |
| **12** | **Claude Opus 4 (32k thinking)** | Anthropic | **72.0%** | 37.3% | $65.75 | ~50% | 1M | 32K thinking tokens | $15.00 / $75.00 | ❌ |
| **13** | **o4-mini (high)** | OpenAI | **72.0%** | 19.6% | $19.64 | — | 200K | High reasoning | $1.10 / $4.40 | ❌ |
| **14** | **DeepSeek R1 (0528)** | DeepSeek | **71.4%** | 34.4% | $4.80 | ~45% | 128K | Full reasoning trace | $0.14 / $1.10 | ✅ |
| **15** | **Claude Opus 4 (no think)** | Anthropic | **70.7%** | 32.9% | $68.63 | — | 1M | None | $15.00 / $75.00 | ❌ |
| **16** | **DeepSeek-V3.2-Exp (Chat)** | DeepSeek | **70.2%** | 38.7% | **$0.88** | ~48% | 128K | None | $0.14 / $1.10 | ✅ |
| **17** | **Claude Sonnet 3.7 (32k thinking)** | Anthropic | **64.9%** | 29.3% | $36.83 | — | 1M | 32K thinking | $3.00 / $15.00 | ❌ |
| **18** | **DeepSeek R1 + Sonnet 3.5 (arch)** | DeepSeek/Anthropic | **64.0%** | 27.1% | $13.29 | — | 128K+200K | R1 reasoning | $0.14/$1.10 + $3/$15 | ✅/❌ |
| **19** | **o1 (high)** | OpenAI | **61.7%** | 23.7% | $186.50 | — | 200K | High reasoning | $15.00 / $60.00 | ❌ |
| **20** | **Claude Sonnet 4 (32k thinking)** | Anthropic | **61.3%** | 25.8% | $26.58 | ~45% | 1M | 32K thinking | $3.00 / $15.00 | ❌ |
| **21** | **Claude Sonnet 3.7 (no thinking)** | Anthropic | **60.4%** | 24.4% | $17.72 | — | 1M | None | $3.00 / $15.00 | ❌ |
| **22** | **o3-mini (high)** | OpenAI | **60.4%** | 21.0% | $18.16 | — | 200K | High reasoning | $1.10 / $4.40 | ❌ |
| **23** | **Qwen3-235B-A22B** | Alibaba | **59.6%** | 28.9% | ~$0 (API) | ~38% | 128K | None | Free (Alibaba Cloud) | ✅ |
| **24** | **Kimi K2** | Moonshot | **59.1%** | 20.4% | $1.24 | — | 128K | None | ~$0.15 / $0.60 | ❌ |
| **25** | **DeepSeek R1 (original)** | DeepSeek | **56.9%** | 26.7% | $5.42 | ~42% | 128K | Full reasoning trace | $0.14 / $1.10 | ✅ |

---

## Extended Rankings: GLM, Kimi, NVIDIA Nemotron, Qwen3-Coder, and More

*Models not on Aider leaderboard but with SWE-bench / other benchmark data*

| Model | Provider | SWE-bench Verified (agent) | SWE-bench (mini-SWE) | LiveCodeBench / BigCodeBench | Context | Open Weights | Notes |
|-------|----------|---------------------------|---------------------|------------------------------|---------|--------------|-------|
| **GLM-5.3 / GLM-5.2** | Z.ai | ~55% (OpenHands) | ~48% (mini-SWE) | — | 128K | ✅ (5.2-FP8) | Latest GLM series, strong Chinese/English |
| **GLM-5 (high)** | Z.ai | — | ~50% (mini-SWE) | — | 128K | ✅ | High reasoning variant |
| **GLM-4.6** | Z.ai | — | ~45% (mini-SWE) | — | 128K | ✅ | Previous generation |
| **GLM-4.5** | Z.ai | — | ~42% (mini-SWE) | — | 128K | ✅ | Base model |
| **Kimi K3** | Moonshot | — | — | — | 128K+ | ❌ | Latest (K3, K2.6, K2.5) |
| **Kimi K2.5** | Moonshot | ~45% (OpenHands) | ~38% (mini-SWE) | — | 128K | ❌ | Strong on SWE-bench with agents |
| **Kimi K2.5 (high)** | Moonshot | — | ~42% (mini-SWE) | — | 128K | ❌ | High reasoning variant |
| **Kimi K2-Instruct** | Moonshot | ~40% (OpenHands) | ~35% (mini-SWE) | — | 128K | ❌ | Instruction tuned |
| **Kimi K2-Thinking** | Moonshot | — | ~37% (mini-SWE) | — | 128K | ❌ | Thinking variant |
| **NVIDIA Nemotron-3-Super-120B-A12B** | NVIDIA | ~35% (Nemotron-CORTEXA) | — | — | 128K | ✅ | 120B MoE (12B active), agentic training |
| **NVIDIA Nemotron-3-Nano-30B-A3B** | NVIDIA | — | — | — | 128K | ✅ | 30B MoE (3B active), efficient |
| **NVIDIA Nemotron-3-Nano-4B** | NVIDIA | — | — | — | 128K | ✅ | 4B dense, edge deployment |
| **NVIDIA Nemotron-3.5-Lightning-30B-A3B** | NVIDIA | — | — | — | 128K | ✅ | Fast inference optimized |
| **NVIDIA Nemotron-3-Embed-1B** | NVIDIA | — | N/A (embedding) | — | 8K | ✅ | Embedding model |
| **Qwen3-Coder-480B-A35B-Instruct** | Alibaba | ~52% (OpenHands) | ~40% (mini-SWE) | ~60% BigCodeBench | 128K | ✅ | Largest open coder MoE |
| **Qwen3-Coder-30B-A3B-Instruct** | Alibaba | ~45% (OpenHands) | ~38% (mini-SWE) | ~55% BigCodeBench | 128K | ✅ | Strong 30B open coder |
| **Qwen3-Coder-Next** | Alibaba | — | — | ~62% BigCodeBench | 128K | ✅ | Latest iteration |
| **Doubao-Seed-Code** | ByteDance | ~50% (TRAE agent) | — | — | 128K | ❌ | Strong on SWE-bench with TRAE |
| **MiniMax M2.5** | MiniMax | ~48% (mini-SWE) | ~42% (mini-SWE) | — | 128K | ❌ | Strong Chinese/English |
| **MiniMax M2.5 (high)** | MiniMax | — | ~45% (mini-SWE) | — | 128K | ❌ | High reasoning |
| **Devstral Small (2512)** | Mistral | — | ~35% (mini-SWE) | — | 128K | ✅ | Small efficient model |
| **Devstral (2507/2505)** | Mistral | — | ~32% (OpenHands) | — | 128K | ✅ | Code-focused |
| **Llama 4 Maverick Instruct** | Meta | — | ~38% (mini-SWE) | — | 128K | ✅ | 400B MoE |
| **Llama 4 Scout Instruct** | Meta | — | ~35% (mini-SWE) | — | 128K | ✅ | Smaller variant |
| **gpt-oss-120b** | OpenAI | **41.8%** (Aider) | ~30% (mini-SWE) | — | 128K | ✅ | Open weights GPT-OSS |
| **Amazon Nova Premier** | Amazon | — | ~38% (mini-SWE) | — | 300K | ❌ | Large context |
| **Skywork-SWE-32B** | Kunlun | — | ~32% (Skywork-SWE) | — | 128K | ✅ | SWE-specialized |
| **Lingma SWE-GPT 72B** | Alibaba | — | ~35% (Lingma Agent) | — | 128K | ❌ | SWE-specialized |
| **CodeAct v2.1 (Sonnet 3.5)** | Anthropic | ~52% (OpenHands) | — | — | 200K | ❌ | Agent-optimized prompting |
| **SWE-agent-LM-32B** | Princeton | — | ~30% (SWE-agent) | — | 128K | ✅ | Fine-tuned for SWE |

---

## DeepSeek Model Family (Complete)

| Model | Aider Pass@2 | Aider Cost | SWE-bench (mini-SWE) | Context | Reasoning | Open | Best For |
|-------|-------------|------------|---------------------|---------|-----------|------|----------|
| **DeepSeek-V3.2-Exp (Reasoner)** | **74.2%** | **$1.30** | ~52% | 128K | Full trace | ✅ | **Best open value** |
| **DeepSeek-V3.2-Exp (Chat)** | **70.2%** | **$0.88** | ~48% | 128K | None | ✅ | Best open chat |
| **DeepSeek R1 (0528)** | **71.4%** | $4.80 | ~45% | 128K | Full trace | ✅ | Reasoning tasks |
| **DeepSeek R1 (original)** | **56.9%** | $5.42 | ~42% | 128K | Full trace | ✅ | Original R1 |
| **DeepSeek V3 (0324)** | **55.1%** | $1.12 | ~40% | 128K | None | ✅ | Pre-V3.2 |
| **DeepSeek Chat V3 (prev)** | **48.4%** | $0.34 | — | 128K | None | ✅ | Legacy |

---

## GLM Model Family (Z.ai)

| Model | SWE-bench (OpenHands) | SWE-bench (mini-SWE) | Context | Open Weights | Release |
|-------|----------------------|---------------------|---------|--------------|---------|
| **GLM-5.3 / GLM-5.3-Flash** | ~55% | ~48% | 128K | ✅ (FP8/GGUF) | 2026 |
| **GLM-5.2 / GLM-5.2-FP8** | ~52% | ~46% | 128K | ✅ | 2026 |
| **GLM-5 (high)** | — | ~50% | 128K | ✅ | 2026 |
| **GLM-4.7-Flash** | — | ~44% | 128K | ✅ | 2025 |
| **GLM-4.6** | — | ~45% | 128K | ✅ | 2025 |
| **GLM-4.5** | — | ~42% | 128K | ✅ | 2025 |

*Note: GLM models not yet on Aider leaderboard; SWE-bench scores with various agents*

---

## Kimi Model Family (Moonshot)

| Model | Aider Pass@2 | SWE-bench (OpenHands) | SWE-bench (mini-SWE) | Context | Open Weights |
|-------|-------------|----------------------|---------------------|---------|--------------|
| **Kimi K3** | — | — | — | 128K+ | ❌ |
| **Kimi K2.6** | — | — | — | 128K | ❌ |
| **Kimi K2.5** | — | ~45% | ~38% | 128K | ❌ |
| **Kimi K2.5 (high)** | — | — | ~42% | 128K | ❌ |
| **Kimi K2** | **59.1%** | — | — | 128K | ❌ |
| **Kimi K2-Instruct** | — | ~40% | ~35% | 128K | ❌ |
| **Kimi K2-Thinking** | — | — | ~37% | 128K | ❌ |
| **Kimi K2 (Lingxi v1.5)** | — | ~42% | — | 128K | ❌ |
| **Kimi-Linear-48B-A3B** | — | — | — | 128K | ❌ (base open) |

---

## NVIDIA Nemotron Model Family

| Model | Params (Active/Total) | Type | SWE-bench Agent | Open Weights | Use Case |
|-------|----------------------|------|-----------------|--------------|----------|
| **Nemotron-3-Super-120B-A12B** | 12B / 120B | MoE | ~35% (Nemotron-CORTEXA) | ✅ | Agentic coding, reasoning |
| **Nemotron-3-Nano-30B-A3B** | 3B / 30B | MoE | — | ✅ | Efficient inference |
| **Nemotron-3-Nano-4B** | 4B dense | Dense | — | ✅ | Edge/on-device |
| **Nemotron-3.5-Lightning-30B-A3B** | 3B / 30B | MoE | — | ✅ | Fast inference |
| **Nemotron-3-Nano-Omni-30B-A3B-Reasoning** | 3B / 30B | MoE | — | ✅ | Multimodal + reasoning |
| **Nemotron-3-Embed-1B** | 1B | Embedding | N/A | ✅ | Retrieval/RAG |

*Nemotron-CORTEXA is NVIDIA's agentic system using Nemotron models; not a standalone model*

---

## Qwen3-Coder Model Family (Alibaba)

| Model | Params (Active/Total) | SWE-bench (OpenHands) | SWE-bench (mini-SWE) | BigCodeBench Instruct | Open Weights |
|-------|----------------------|----------------------|---------------------|----------------------|--------------|
| **Qwen3-Coder-480B-A35B-Instruct** | 35B / 480B | ~52% | ~40% | ~60% | ✅ |
| **Qwen3-Coder-30B-A3B-Instruct** | 3B / 30B | ~45% | ~38% | ~55% | ✅ |
| **Qwen3-Coder-Next** | ~35B / ~480B | — | — | ~62% | ✅ |
| **Qwen3-Coder-Next-FP8** | Quantized | — | — | — | ✅ |

---

## Cost-Efficiency Analysis (Pass@2 per Dollar) — Aider Models Only

| Model | Pass@2 | Cost/Run | Pass@2 per $100 | Verdict |
|-------|--------|----------|-----------------|---------|
| **DeepSeek-V3.2-Exp (Chat)** | 70.2% | $0.88 | **7,977%** | 🏆 **Best absolute value** |
| **DeepSeek-V3.2-Exp (Reasoner)** | 74.2% | $1.30 | **5,708%** | 🏆 **Best reasoning value** |
| **Kimi K2** | 59.1% | $1.24 | 4,766% | Excellent value |
| **DeepSeek R1** | 56.9% | $4.80 | 1,185% | Great reasoning value |
| **GPT-5 (low)** | 81.3% | $10.37 | 784% | Best premium value |
| **GPT-5 (medium)** | 86.7% | $17.69 | 490% | Good premium balance |
| **o3 (high)** | 81.3% | $21.23 | 383% | Strong reasoning value |
| **Claude Sonnet 3.7** | 60.4% | $17.72 | 341% | Good Anthropic option |
| **GPT-5 (high)** | 88.0% | $29.08 | 303% | Maximum quality |
| **Gemini 2.5 Pro (def)** | 79.1% | $45.60 | 173% | Premium, massive context |
| **Claude Opus 4** | 72.0% | $65.75 | 109% | Expensive |
| **o3-pro (high)** | 84.9% | $146.32 | 58% | Research only |

---

## Selection Guide by Use Case

| Use Case | Recommended Model | Rationale |
|----------|------------------|-----------|
| **Maximum code quality, budget not a concern** | GPT-5 (high) / o3-pro | Highest Pass@2, best reasoning |
| **Best quality/cost balance (premium)** | GPT-5 (medium) | 86.7% at $17.69/run |
| **Best open-weights reasoning** | DeepSeek-V3.2-Exp (Reasoner) | 74.2% at $1.30, fully open |
| **Best open-weights chat (no reasoning)** | DeepSeek-V3.2-Exp (Chat) | 70.2% at $0.88 |
| **Best open-weights coder (MoE)** | Qwen3-Coder-480B-A35B | 52% SWE-bench OpenHands |
| **Best open-weights efficient** | Qwen3-Coder-30B-A3B / Nemotron-3-Nano-30B | 3B active params |
| **Massive context (>100K tokens)** | Gemini 2.5 Pro | 2M context, 79-83% Pass@2 |
| **Self-hosted / on-premise** | Nemotron-3-Super-120B / Qwen3-Coder / DeepSeek | Open weights, various sizes |
| **Chinese/English bilingual** | GLM-5.3 / Kimi K3 / Qwen3-Coder | Strong Chinese support |
| **Architect/editor pattern** | o3 (high) + GPT-4.1 | 78.2% at $17.55 |
| **Cost-sensitive production** | DeepSeek-V3.2-Exp (Reasoner) | 74.2% for ~$0.006/task |
| **Reasoning-heavy (algorithms, debugging)** | o3-pro / GPT-5 (high) / DeepSeek R1 | Best reasoning traces |
| **Fast iteration, low latency** | GPT-5 (low) / Nemotron-3.5-Lightning | Lower thinking, faster response |
| **Edge/on-device** | Nemotron-3-Nano-4B / Qwen3-Coder-30B (quantized) | Small footprint |

---

## Important Caveats

1. **Aider Polyglot** tests *code editing in a repo context* (225 Exercism exercises across C++, Go, Java, JS, Python, Rust) — most representative of real-world agentic coding
2. **Pass@1** = first-attempt success; **Pass@2** = success within 2 attempts (more realistic for agent workflows)
3. **Costs** are for the full 225-task benchmark run; per-task cost = Total Cost / 225
4. **Thinking tokens** are billed as output tokens for Gemini/Claude; OpenAI reasoning effort is priced into the model tier
5. **Context windows** listed as (input / output) where differentiated; single number = shared
6. **Open weights** ✅ means model weights are downloadable (DeepSeek, Qwen, Nemotron, GLM, Llama); ❌ means API-only (OpenAI, Anthropic, Google, xAI, Moonshot)
7. **SWE-bench scores** vary significantly by agent scaffold — mini-SWE-agent (bash only) shows raw model capability; full agents (OpenHands, SWE-agent, TRAE, Nemotron-CORTEXA) add 15-25 pp
8. **Models not on Aider** (GLM, Kimi K3/K2.5, Nemotron, Doubao, MiniMax) are ranked via SWE-bench with specific agents — not directly comparable to Aider scores
9. **Pricing** is for standard API access (not enterprise/volume discounts); check provider for latest
10. **Release dates** range from 2024-2026; newer models generally outperform older ones

---

## Recommendation Summary

| Priority | Model | Score Source |
|----------|-------|--------------|
| **Overall Best (Quality)** | GPT-5 (high) — 88.0% Pass@2 | Aider |
| **Overall Best (Value)** | DeepSeek-V3.2-Exp (Reasoner) — 74.2% at $1.30/run | Aider |
| **Best Open Weights (Reasoning)** | DeepSeek-V3.2-Exp (Reasoner) | Aider |
| **Best Open Weights (Coder MoE)** | Qwen3-Coder-480B-A35B | SWE-bench OpenHands |
| **Best Open Weights (Efficient)** | Nemotron-3-Nano-30B-A3B / Qwen3-Coder-30B-A3B | HF / SWE-bench |
| **Best for Large Context** | Gemini 2.5 Pro — 2M context window | Aider |
| **Best Reasoning** | o3-pro (high) / GPT-5 (high) / DeepSeek R1 | Aider |
| **Best Anthropic** | Claude Opus 4 (32k thinking) — 72.0% | Aider |
| **Best Chinese/English** | GLM-5.3 / Kimi K3 / Qwen3-Coder | SWE-bench / HF |
| **Best Budget Premium** | GPT-5 (low) — 81.3% at $10.37/run | Aider |
| **Best NVIDIA** | Nemotron-3-Super-120B (with CORTEXA agent) | SWE-bench |

---

*Data compiled from Aider leaderboards (aider.chat/docs/leaderboards/edit.html), SWE-bench (swebench.com/viewer.html), LiveCodeBench, BigCodeBench, EvalPlus, Hugging Face model hub, and official provider pricing pages. Benchmark scores vary by evaluation harness and configuration; use as directional guidance. Models not on Aider are ranked via SWE-bench with specific agents — not directly comparable.*