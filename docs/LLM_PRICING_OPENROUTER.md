# LLM Model Pricing Comparison for OpenRouter / opencode (UPDATED)

**Primary Providers:** OpenRouter (all models), opencode (uses OpenRouter)
**Secondary:** Direct APIs (Anthropic, OpenAI, Google, DeepSeek, etc.)
**Self-Hosted:** Open weights models (DeepSeek, Qwen, Nemotron, GLM, Llama, Mistral)

**Data Sources:**

- **Aider Polyglot** — 225 Exercism exercises across 6 languages (repo context editing)
- **SWE-bench Verified** — 500 GitHub issues (mini-SWE-agent, OpenHands, etc.)
- **LiveBench** — Contamination-free, monthly updated, objective scoring (coding + overall)
- **OpenRouter Usage** — Real developer adoption (tokens/week, Sep 2026)

**Last Updated:** September 2026 | Prices in USD per 1M tokens

---

## Unified Rankings Table — All Models with Multi-Benchmark Scores

| Rank | Model | Provider | Aider Pass@2 | LiveBench Coding | LiveBench Overall | OpenRouter Usage Rank | OpenRouter Model ID | OpenRouter Price (In/Out) | Context | Open Weights |
|------|-------|----------|-------------|-----------------|------------------|----------------------|---------------------|--------------------------|---------|--------------|
| **1** | **Gemini 2.5 Pro (exp 03-25)** | Google | — | **0.867** | **0.741** | — | `google/gemini-2.5-pro-exp-03-25` | $1.25 / $10.00 | 2M | ❌ |
| **2** | **o3-mini (high)** | OpenAI | 60.4% | **0.828** | 0.636 | — | `openai/o3-mini` (high) | $1.10 / $4.40 | 200K | ❌ |
| **3** | **DeepSeek R1 (local)** | DeepSeek | — | **0.879** | 0.660 | — | — | — | 128K | ✅ |
| **4** | **QwQ-32B** | Alibaba | — | **0.758** | 0.608 | — | `qwen/qwq-32b` | ~$0.10 / $0.40 | 128K | ✅ |
| **5** | **GPT-4.5 Preview** | OpenAI | 44.9% | **0.750** | 0.672 | — | `openai/gpt-4.5-preview` | $15.00 / $60.00 | 200K | ❌ |
| **6** | **Claude 3.7 Sonnet (64k think)** | Anthropic | 64.9% | **0.742** | 0.691 | — | `anthropic/claude-3.7-sonnet` (64k) | $3.00 / $15.00 | 1M | ❌ |
| **7** | **o1-preview** | OpenAI | — | 0.523 | **0.703** | — | `openai/o1-preview` | $15.00 / $60.00 | 200K | ❌ |
| **8** | **o1 (high)** | OpenAI | 61.7% | 0.688 | 0.675 | — | `openai/o1` (high) | $15.00 / $60.00 | 200K | ❌ |
| **9** | **GPT-5 (high)** | OpenAI | **88.0%** | — | — | — | `openai/gpt-5` (high) | $1.25 / $10.00 | 400K/256K | ❌ |
| **10** | **GPT-5 (medium)** | OpenAI | **86.7%** | — | — | — | `openai/gpt-5` (medium) | $1.25 / $10.00 | 400K/256K | ❌ |
| **11** | **o3-pro (high)** | OpenAI | **84.9%** | — | — | — | `openai/o3-pro` | $20.00 / $80.00 | 200K | ❌ |
| **12** | **Gemini 2.5 Pro (32k think)** | Google | **83.1%** | — | — | — | `google/gemini-2.5-pro` | $1.25 / $10.00 | 2M/1M | ❌ |
| **13** | **GPT-5 (low)** | OpenAI | **81.3%** | — | — | — | `openai/gpt-5` (low) | $1.25 / $10.00 | 400K/256K | ❌ |
| **14** | **o3 (high)** | OpenAI | **81.3%** | — | — | — | `openai/o3` | $10.00 / $40.00 | 200K | ❌ |
| **15** | **Grok-4 (high)** | xAI | **79.6%** | — | 0.526 | — | `x-ai/grok-4` | ~$3.00 / $15.00 | 256K | ❌ |
| **16** | **Gemini 2.5 Pro (default)** | Google | **79.1%** | — | — | — | `google/gemini-2.5-pro` | $1.25 / $10.00 | 2M/1M | ❌ |
| **17** | **o3 + GPT-4.1 (architect)** | OpenAI | **78.2%** | — | — | — | `openai/o3` + `openai/gpt-4.1` | $10/$40 + $2/$8 | 200K+1M | ❌ |
| **18** | **DeepSeek-V3.2-Exp (Reasoner)** | DeepSeek | **74.2%** | 0.703 | 0.595 | — | `deepseek/deepseek-reasoner` | **$0.14 / $1.10** | 128K | ✅ |
| **19** | **Claude Opus 4 (32k think)** | Anthropic | **72.0%** | — | — | — | `anthropic/claude-opus-4` | $15.00 / $75.00 | 1M | ❌ |
| **20** | **o4-mini (high)** | OpenAI | **72.0%** | — | — | — | `openai/o4-mini` | $1.10 / $4.40 | 200K | ❌ |
| **21** | **DeepSeek R1 (0528)** | DeepSeek | **71.4%** | 0.703 | 0.595 | — | `deepseek/deepseek-reasoner` | $0.14 / $1.10 | 128K | ✅ |
| **22** | **Claude Opus 4 (no think)** | Anthropic | **70.7%** | — | — | — | `anthropic/claude-opus-4` | $15.00 / $75.00 | 1M | ❌ |
| **23** | **DeepSeek-V3.2-Exp (Chat)** | DeepSeek | **70.2%** | 0.617 | 0.547 | — | `deepseek/deepseek-chat` | **$0.14 / $1.10** | 128K | ✅ |
| **24** | **Claude Sonnet 3.7 (32k think)** | Anthropic | **64.9%** | 0.656 | 0.691 | — | `anthropic/claude-3.7-sonnet` | $3.00 / $15.00 | 1M | ❌ |
| **25** | **DeepSeek R1 + Sonnet 3.5 (arch)** | DeepSeek/Anthropic | **64.0%** | — | — | — | `deepseek/deepseek-reasoner` + `anthropic/claude-3.5-sonnet` | $0.14/$1.10 + $3/$15 | 128K+200K | ✅/❌ |
| **26** | **o1 (high) - legacy** | OpenAI | **61.7%** | 0.688 | 0.675 | — | `openai/o1` | $15.00 / $60.00 | 200K | ❌ |
| **27** | **Claude Sonnet 4 (32k think)** | Anthropic | **61.3%** | — | — | — | `anthropic/claude-sonnet-4` | $3.00 / $15.00 | 1M | ❌ |
| **28** | **Claude Sonnet 3.7 (no think)** | Anthropic | **60.4%** | 0.656 | 0.644 | — | `anthropic/claude-3.7-sonnet` | $3.00 / $15.00 | 1M | ❌ |
| **29** | **o3-mini (high) - legacy** | OpenAI | **60.4%** | 0.828 | 0.636 | — | `openai/o3-mini` (high) | $1.10 / $4.40 | 200K | ❌ |
| **30** | **Qwen3-235B-A22B** | Alibaba | **59.6%** | — | — | — | `qwen/qwen3-235b-a22b` | **Free** (Alibaba) | 128K | ✅ |
| **31** | **Kimi K2** | Moonshot | **59.1%** | — | — | — | `moonshotai/kimi-k2` | ~$0.15 / $0.60 | 128K | ❌ |
| **32** | **DeepSeek R1 (original)** | DeepSeek | **56.9%** | 0.703 | 0.595 | — | `deepseek/deepseek-reasoner` | $0.14 / $1.10 | 128K | ✅ |
| **33** | **Claude 3.5 Sonnet (2024-10-22)** | Anthropic | 51.6% | **0.656** | **0.607** | — | `anthropic/claude-3.5-sonnet` | $3.00 / $15.00 | 200K | ❌ |
| **34** | **ChatGPT-4o-latest (2025-03-27)** | OpenAI | 45.3% | 0.656 | 0.588 | — | `openai/chatgpt-4o-latest` | $2.50 / $10.00 | 128K | ❌ |
| **35** | **Grok-3 Beta** | xAI | 53.3% | 0.523 | 0.584 | — | `x-ai/grok-3-beta` | ~$3.00 / $15.00 | 131K | ❌ |
| **36** | **Grok-3 Mini (reasoning)** | xAI | 49.3% | 0.586 | 0.500 | — | `x-ai/grok-3-mini-beta` | ~$0.50 / $2.00 | 131K | ❌ |
| **37** | **Gemini 2.0 Flash (001)** | Google | — | 0.539 | 0.527 | — | `google/gemini-2.0-flash-001` | $0.075 / $0.30 | 1M | ❌ |
| **38** | **GPT-4o (Aug 2024)** | OpenAI | — | 0.500 | 0.536 | — | `openai/gpt-4o-2024-08-06` | $2.50 / $10.00 | 128K | ❌ |
| **39** | **GPT-4o (May 2024)** | OpenAI | — | 0.500 | 0.544 | — | `openai/gpt-4o-2024-05-13` | $2.50 / $10.00 | 128K | ❌ |
| **40** | **Qwen2.5-Coder-32B** | Alibaba | — | **0.570** | 0.429 | — | `qwen/qwen2.5-coder-32b` | ~$0.10 / $0.40 | 128K | ✅ |
| **41** | **Qwen2.5-72B** | Alibaba | — | 0.563 | 0.496 | — | `qwen/qwen2.5-72b` | ~$0.20 / $0.80 | 128K | ✅ |
| **42** | **Llama 4 Maverick** | Meta | — | 0.511 | 0.524 | — | `meta-llama/llama-4-maverick` | ~$0.50 / $2.00 | 128K | ✅ |
| **43** | **Nemotron 3 Ultra 550B** | NVIDIA | — | — | — | **#4** (2.57T) | `nvidia/nemotron-3-ultra-550b:free` | **FREE** | 1M | ✅ |
| **44** | **DeepSeek V4.1 Flash** | DeepSeek | — | — | — | **#3** (3.99T) | `deepseek/deepseek-v4.1-flash` | **$0.14 / $0.42** | 1.05M | ❌ |
| **45** | **DeepSeek V4 Flash** | DeepSeek | — | — | — | **#5** (2.04T) | `deepseek/deepseek-v4-flash` | **$0.054 / $0.162** | 1.31M | ❌ |
| **46** | **GPT-5.6 Luna** | OpenAI | — | — | — | **#6** (2.01T) | `openai/gpt-5.6-luna` | $0.20 / $1.20 | 1.05M | ❌ |
| **47** | **GLM 5.3 Flash** | Z.ai | — | — | — | **#2** (4.48T) | `z-ai/glm-5.3-flash` | **$0.075 / $0.25** | 1.31M | ❌ |
| **48** | **GLM 5.3** | Z.ai | — | — | — | **#8** (1.38T) | `z-ai/glm-5.3` | $0.89 / $2.80 | 1.31M | ❌ |
| **49** | **Mimo V2.5** | Xiaomi | — | — | — | **#1** (5.46T) | `xiaomi/mimo-v2.5` | $0.119 / $0.238 | 1.05M | ❌ |
| **50** | **Hy4 Preview** | Tencent | — | — | — | **#7** (1.48T) | `tencent/hy4-preview` | $0.834 / $2.50 | 1.05M | ❌ |
| **51** | **Hy3** | Tencent | — | — | — | — | `tencent/hy3` | $0.0825 / $0.33 | 262K | ❌ |
| **52** | **Muse Spark 1.3** | Meta | — | — | — | **#9** (1.16T) | `meta/muse-spark-1.3` | — | — | ❌ |
| **53** | **DeepSeek V3 (0324)** | DeepSeek | 55.1% | 0.711 | 0.601 | — | `deepseek/deepseek-v3-0324` | $0.14 / $1.10 | 128K | ✅ |
| **54** | **Qwen3-Coder-480B** | Alibaba | — | — | — | — | `qwen/qwen3-coder-480b` | ~$0.50 / $2.00 | 128K | ✅ |
| **55** | **Qwen3-Coder-30B** | Alibaba | — | — | — | — | `qwen/qwen3-coder-30b` | ~$0.10 / $0.40 | 128K | ✅ |
| **56** | **Doubao-Seed-Code** | ByteDance | — | — | — | — | `bytedance/doubao-seed-code` | ~$0.30 / $1.20 | 128K | ❌ |
| **57** | **MiniMax M2.5** | MiniMax | — | — | — | — | `minimax/minimax-m2.5` | ~$0.20 / $0.80 | 128K | ❌ |
| **58** | **Devstral Small** | Mistral | — | — | — | — | `mistral/devstral-small` | ~$0.10 / $0.40 | 128K | ✅ |
| **59** | **gpt-oss-120b** | OpenAI | 41.8% | — | — | — | `openai/gpt-oss-120b` | ~$0.10 / $0.40 | 128K | ✅ |
| **60** | **Amazon Nova Premier** | Amazon | — | — | — | — | `amazon/nova-premier` | ~$0.30 / $1.20 | 300K | ❌ |
| **61** | **Skywork-SWE-32B** | Kunlun | — | — | — | — | `kunlun/skywork-swe-32b` | ~$0.10 / $0.40 | 128K | ✅ |
| **62** | **Nemotron 3 Nano 30B** | NVIDIA | — | — | — | — | `nvidia/nemotron-3-nano-30b` | ~$0.10 / $0.40 | 128K | ✅ |
| **63** | **Nemotron 3 Nano 4B** | NVIDIA | — | — | — | — | `nvidia/nemotron-3-nano-4b` | ~$0.05 / $0.20 | 128K | ✅ |
| **64** | **GLM 4.7 Flash** | Z.ai | — | — | — | — | `z-ai/glm-4.7-flash` | ~$0.05 / $0.20 | 128K | ✅ |
| **65** | **Kimi K2.5** | Moonshot | — | — | — | — | `moonshotai/kimi-k2.5` | ~$0.15 / $0.60 | 128K | ❌ |

---

## LiveBench Category Scores (Top 20 Coding)

| Model | LiveBench Coding | LiveBench Overall | LiveBench Instruction Following | # Tasks |
|-------|-----------------|------------------|--------------------------------|---------|
| DeepSeek R1 (local) | **0.879** | 0.660 | — | 33 |
| Gemini 2.5 Pro (exp 03-25) | **0.867** | **0.741** | — | 128 |
| o3-mini (high) | **0.828** | 0.636 | — | 128 |
| QwQ-32B | **0.758** | 0.608 | — | 128 |
| GPT-4.5 Preview | **0.750** | 0.672 | — | 128 |
| Claude 3.7 Sonnet (64k think) | **0.742** | 0.691 | — | 128 |
| DeepSeek R1 (local-2) | **0.711** | 0.643 | — | 128 |
| DeepSeek V3 (0324) | **0.711** | 0.601 | — | 128 |
| DeepSeek R1 | **0.703** | 0.595 | — | 128 |
| o3-mini (medium) | **0.695** | 0.567 | — | 128 |
| o1 (high) | **0.688** | 0.675 | — | 128 |
| Claude 3.7 Sonnet (base) | **0.656** | 0.644 | — | 128 |
| Claude 3.5 Sonnet (2024-10-22) | **0.656** | 0.607 | — | 128 |
| ChatGPT-4o-latest (2025-03-27) | **0.656** | 0.588 | — | 128 |
| o3-mini (low) | **0.648** | 0.519 | — | 128 |
| Qwen2.5-Max | **0.641** | 0.623 | — | 128 |
| o1 | **0.633** | 0.633 | — | 128 |
| Sonar Pro | **0.602** | 0.641 | — | 128 |
| DeepSeek V3 | **0.617** | 0.547 | — | 128 |
| Qwen2.5-Coder-32B | **0.570** | 0.429 | — | 128 |

---

## OpenRouter Programming Collection — Real Usage (Sep 2026)

| Rank | Model | Provider | Tokens/Week | % Share | OpenRouter Price (In/Out) | Context | Notes |
|------|-------|----------|-------------|---------|--------------------------|---------|-------|
| **1** | **Mimo V2.5** | Xiaomi | 5.46T | 15.0% | $0.119 / $0.238 | 1.05M | #1 by usage |
| **2** | **GLM 5.3 Flash** | Z.ai | 4.48T | 12.3% | **$0.075 / $0.25** (50% off) | 1.31M | **Cheapest quality model** |
| **3** | **DeepSeek V4.1 Flash** | DeepSeek | 3.99T | 11.0% | **$0.14 / $0.42** (30% off) | 1.05M | New CED architecture |
| **4** | **Nemotron 3 Ultra 550B** | NVIDIA | 2.57T | 7.1% | **FREE** | 1M | **Free tier!** 55B active MoE |
| **5** | **DeepSeek V4 Flash** | DeepSeek | 2.04T | 5.6% | **$0.054 / $0.162** (88% off) | 1.31M | **Cheapest overall** |
| **6** | **GPT-5.6 Luna** | OpenAI | 2.01T | 5.5% | $0.20 / $1.20 | 1.05M | Fast, cost-efficient |
| **7** | **Hy4 Preview** | Tencent | 1.48T | 4.1% | $0.834 / $2.50 | 1.05M | 49B active / 770B MoE |
| **8** | **GLM 5.3** | Z.ai | 1.38T | 3.8% | $0.89 / $2.80 (36% off) | 1.31M | Reasoning always on |
| **9** | **Muse Spark 1.3** | Meta | 1.16T | 3.2% | — | — | Contributor model |
| **10** | **DeepSeek V4 Flash (0423)** | DeepSeek | 0.46T | — | $0.048 / $0.097 (65% off) | 1.05M | Older version |

---

## Cost-Efficiency Analysis (Aider Pass@2 per $100)

| Model | Aider Pass@2 | Cost/Run | Pass@2 per $100 | OpenRouter ID | Best For |
|-------|-------------|----------|-----------------|---------------|----------|
| **DeepSeek-V3.2-Exp (Chat)** | 70.2% | **$0.88** | **7,977%** | `deepseek/deepseek-chat` | 🏆 **Best absolute value** |
| **DeepSeek-V3.2-Exp (Reasoner)** | 74.2% | **$1.30** | **5,708%** | `deepseek/deepseek-reasoner` | 🏆 **Best reasoning value** |
| **Kimi K2** | 59.1% | $1.24 | 4,766% | `moonshotai/kimi-k2` | Excellent value |
| **DeepSeek R1** | 56.9% | $4.80 | 1,185% | `deepseek/deepseek-reasoner` | Great reasoning value |
| **GPT-5 (low)** | 81.3% | $10.37 | 784% | `openai/gpt-5` (low) | Best premium value |
| **GPT-5 (medium)** | 86.7% | $17.69 | 490% | `openai/gpt-5` (medium) | Best quality/cost balance |
| **o3 (high)** | 81.3% | $21.23 | 383% | `openai/o3` | Strong reasoning value |
| **Claude Sonnet 3.7** | 60.4% | $17.72 | 341% | `anthropic/claude-3.7-sonnet` | Good Anthropic option |
| **GPT-5 (high)** | 88.0% | $29.08 | 303% | `openai/gpt-5` (high) | Maximum quality |
| **Gemini 2.5 Pro (def)** | 79.1% | $45.60 | 173% | `google/gemini-2.5-pro` | Premium, massive context |
| **Nemotron 3 Ultra (FREE)** | — | $0.00 | ∞ | `nvidia/nemotron-3-ultra:free` | **Free tier winner** |
| **DeepSeek V4 Flash** | — | ~$0.02 | ∞ | `deepseek/deepseek-v4-flash` | **Cheapest API** |
| **GLM 5.3 Flash** | — | ~$0.03 | ∞ | `z-ai/glm-5.3-flash` | **Best cheap quality** |

---

## Decision Matrix by Use Case (Updated with New Data)

| Use Case | Recommended Model | OpenRouter ID | Est. Cost/Run | Why |
|----------|------------------|---------------|---------------|-----|
| **🏆 Absolute Best Value (API)** | DeepSeek-V3.2-Exp (Chat) | `deepseek/deepseek-chat` | **$0.88** | 70.2% Aider, cheapest quality |
| **🏆 Best Reasoning Value (API)** | DeepSeek-V3.2-Exp (Reasoner) | `deepseek/deepseek-reasoner` | **$1.30** | 74.2% Aider, full reasoning trace |
| **🆓 Free Tier (OpenRouter)** | Nemotron 3 Ultra 550B | `nvidia/nemotron-3-ultra:free` | **$0.00** | 55B active, 1M context, free |
| **💰 Cheapest Usable API** | DeepSeek V4 Flash | `deepseek/deepseek-v4-flash` | ~$0.02 | 88% off, 1.31M context |
| **⚖️ Best Cheap Quality** | GLM 5.3 Flash | `z-ai/glm-5.3-flash` | ~$0.03 | 50% off, #2 usage, 1.31M context |
| **🧠 Max Reasoning (Budget)** | DeepSeek V3.2 Reasoner | `deepseek/deepseek-reasoner` | $1.30 | Full reasoning, open weights |
| **🧠 Max Reasoning (Premium)** | o3-pro / GPT-5 (high) | `openai/o3-pro` / `openai/gpt-5` | $29-146 | Best benchmarks |
| **📏 Max Context** | Gemini 2.5 Pro | `google/gemini-2.5-pro` | $45.60 | 2M context window |
| **🇨🇳 Chinese/English** | GLM 5.3 / Kimi K2 | `z-ai/glm-5.3` / `moonshotai/kimi-k2` | $0.40-1.24 | Strong bilingual |
| **🏠 Self-Hosted (Best Coder)** | Qwen3-Coder-480B / Nemotron 3 Ultra | Local (vLLM/Ollama) | $12-24/hr GPU | Open weights, no limits |
| **🏠 Self-Hosted (Efficient)** | Qwen3-Coder-30B / Nemotron 3 Nano | Local | $1.50/hr GPU | 3B active MoE |
| **🏠 Self-Hosted (Edge)** | Nemotron 3 Nano 4B | Local (llama.cpp) | Runs on 8GB VRAM | 4B dense |
| **⚡ Fast Iteration** | GPT-5 (low) / Nemotron 3.5 Lightning | `openai/gpt-5` (low) | $10.37 | Lower thinking, fast |
| **🔬 LiveBench Coding Leader** | Gemini 2.5 Pro (exp) | `google/gemini-2.5-pro-exp` | ~$50 | 86.7% LiveBench coding |
| **📊 Real Usage Leader** | Mimo V2.5 | `xiaomi/mimo-v2.5` | ~$5 | #1 by tokens on OpenRouter |

---

## opencode Quick Reference

```bash
# === FREE TIER ===
opencode --model nvidia/nemotron-3-ultra-550b:free          # Nemotron 3 Ultra (FREE)

# === BEST VALUE ===
opencode --model deepseek/deepseek-chat                       # DeepSeek V3.2 Chat ($0.88/run)
opencode --model deepseek/deepseek-reasoner                   # DeepSeek V3.2 Reasoner ($1.30/run)

# === CHEAP QUALITY ===
opencode --model z-ai/glm-5.3-flash                           # GLM 5.3 Flash ($0.03/run)
opencode --model deepseek/deepseek-v4-flash                   # DeepSeek V4 Flash ($0.02/run)

# === PREMIUM BALANCE ===
opencode --model openai/gpt-5 --reasoning-effort low          # GPT-5 Low ($10.37/run)
opencode --model openai/gpt-5 --reasoning-effort medium       # GPT-5 Medium ($17.69/run)

# === MAX REASONING ===
opencode --model openai/o3 --reasoning-effort high            # o3 High ($21.23/run)
opencode --model openai/o3-pro                                # o3-pro ($146/run)

# === MASSIVE CONTEXT ===
opencode --model google/gemini-2.5-pro                        # Gemini 2.5 Pro ($45.60/run)

# === CHINESE/ENGLISH ===
opencode --model z-ai/glm-5.3                                 # GLM 5.3
opencode --model moonshotai/kimi-k2                           # Kimi K2

# === SELF-HOSTED (via Ollama) ===
opencode --model ollama/nemotron-3-ultra --base-url http://localhost:11434/v1
opencode --model ollama/qwen3-coder-30b --base-url http://localhost:11434/v1
```

---

## Provider Availability on OpenRouter (Verified Sep 2026)

| Provider | Key Models | Notes |
|----------|------------|-------|
| **OpenAI** | GPT-5, GPT-5.6, o3, o3-pro, o4-mini, o1, gpt-oss | Full reasoning support |
| **Anthropic** | Opus 4, Sonnet 4, 3.7 Sonnet, 3.5 Sonnet | Thinking tokens supported |
| **Google** | Gemini 2.5 Pro/Flash, 2.0 Flash/Pro | Thinking tokens supported |
| **DeepSeek** | V3.2, V4/V4.1 Flash, R1, V3 | **Cheapest reasoning models** |
| **NVIDIA** | Nemotron 3 Ultra (FREE), Nano, Lightning | **Free tier + open weights** |
| **Z.ai (GLM)** | GLM 5.3/Flash, 4.7-Flash | **Open weights + API**, #2 usage |
| **Moonshot (Kimi)** | K2, K2.5, K3 | Chinese optimized |
| **xAI** | Grok-4, Grok-3, Grok-3-mini | Good alternative |
| **Alibaba (Qwen)** | Qwen3-Coder, Qwen3-235B, QwQ-32B | **Open weights + API** |
| **Meta** | Llama 4 Maverick/Scout, Muse Spark | Open weights |
| **Mistral** | Devstral, Codestral, Large | Open weights |
| **Xiaomi** | Mimo V2.5 | **#1 usage on OpenRouter** |
| **Tencent** | Hy4, Hy3 | MoE models |
| **ByteDance** | Doubao-Seed-Code | New addition |
| **MiniMax** | M2.5 | Chinese optimized |
| **Amazon** | Nova Premier/Pro/Lite | Large context |
| **Kunlun** | Skywork-SWE-32B | SWE-specialized |

---

## Important Notes

1. **Benchmark Coverage**: Aider = 45 models; LiveBench = 195 models (coding); SWE-bench = 100+ with agents; OpenRouter usage = 1000+ models
2. **New Models Missing from Benchmarks**: Mimo V2.5, DeepSeek V4/V4.1, Nemotron 3 Ultra, GLM 5.3 Flash, Hy4, Muse Spark — **run your own eval**
3. **Free Tier**: Nemotron 3 Ultra 550B is **completely free** on OpenRouter (55B active MoE, 1M context)
4. **Cheapest Quality**: GLM 5.3 Flash at **$0.075/$0.25** (50% off) — #2 by usage
5. **Cheapest Overall**: DeepSeek V4 Flash at **$0.054/$0.162** (88% off)
6. **Open Weights**: DeepSeek, Qwen, Nemotron, GLM, Llama, Mistral, gpt-oss — self-hostable
7. **LiveBench Updates Monthly** — contamination-free, objective scoring (no LLM judge)
8. **Prices Change Weekly** — check OpenRouter model page before committing: `https://openrouter.ai/models/<model-id>`

---

*Data compiled from: Aider leaderboards, SWE-bench (swebench.com), LiveBench (livebench.ai + HF datasets), OpenRouter programming collection (openrouter.ai/collections/programming), official provider pricing. Last verified September 2026.*
