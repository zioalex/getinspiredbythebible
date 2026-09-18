# LLM Model Pricing Comparison for OpenRouter / opencode

**Primary Providers:** OpenRouter (all models), opencode (uses OpenRouter)
**Secondary:** Direct APIs (Anthropic, OpenAI, Google, DeepSeek, etc.)
**Self-Hosted:** Open weights models (DeepSeek, Qwen, Nemotron, GLM, Llama, Mistral)

**Last Updated:** September 2026 | Prices in USD per 1M tokens

---

## Unified Pricing Table — All Models Ranked by Aider Pass@2

| Rank | Model | Provider | Aider Pass@2 | OpenRouter Model ID | OpenRouter Pricing (In/Out) | Direct API Pricing (In/Out) | Cost/Run (225 tasks) | Context | Open Weights | Self-Host Cost (est.) |
|------|-------|----------|-------------|---------------------|----------------------------|----------------------------|---------------------|---------|--------------|----------------------|
| **1** | **GPT-5 (high)** | OpenAI | **88.0%** | `openai/gpt-5` | $1.25 / $10.00 | $1.25 / $10.00 | **$29.08** | 400K/256K | ❌ | N/A |
| **2** | **GPT-5 (medium)** | OpenAI | **86.7%** | `openai/gpt-5` (med) | $1.25 / $10.00 | $1.25 / $10.00 | **$17.69** | 400K/256K | ❌ | N/A |
| **3** | **o3-pro (high)** | OpenAI | **84.9%** | `openai/o3-pro` | $20.00 / $80.00 | $20.00 / $80.00 | **$146.32** | 200K | ❌ | N/A |
| **4** | **Gemini 2.5 Pro (32k think)** | Google | **83.1%** | `google/gemini-2.5-pro` | $1.25 / $10.00 | $1.25 / $10.00 | **$49.88** | 2M/1M | ❌ | N/A |
| **5** | **GPT-5 (low)** | OpenAI | **81.3%** | `openai/gpt-5` (low) | $1.25 / $10.00 | $1.25 / $10.00 | **$10.37** | 400K/256K | ❌ | N/A |
| **6** | **o3 (high)** | OpenAI | **81.3%** | `openai/o3` | $10.00 / $40.00 | $10.00 / $40.00 | **$21.23** | 200K | ❌ | N/A |
| **7** | **Grok-4 (high)** | xAI | **79.6%** | `x-ai/grok-4` | ~$3.00 / $15.00 | ~$3.00 / $15.00 | **$59.62** | 256K | ❌ | N/A |
| **8** | **Gemini 2.5 Pro (default)** | Google | **79.1%** | `google/gemini-2.5-pro` | $1.25 / $10.00 | $1.25 / $10.00 | **$45.60** | 2M/1M | ❌ | N/A |
| **9** | **o3 + GPT-4.1 (architect)** | OpenAI | **78.2%** | `openai/o3` + `openai/gpt-4.1` | $10/$40 + $2/$8 | $10/$40 + $2/$8 | **$17.55** | 200K+1M | ❌ | N/A |
| **10** | **DeepSeek-V3.2-Exp (Reasoner)** | DeepSeek | **74.2%** | `deepseek/deepseek-reasoner` | **$0.14 / $1.10** | **$0.14 / $1.10** | **$1.30** | 128K | ✅ | 4×H100 (~$12/hr) |
| **11** | **Gemini 2.5 Pro Preview 05-06** | Google | **76.9%** | `google/gemini-2.5-pro-preview-05-06` | $1.25 / $10.00 | $1.25 / $10.00 | **$37.41** | 2M | ❌ | N/A |
| **12** | **Claude Opus 4 (32k thinking)** | Anthropic | **72.0%** | `anthropic/claude-opus-4` | $15.00 / $75.00 | $15.00 / $75.00 | **$65.75** | 1M | ❌ | N/A |
| **13** | **o4-mini (high)** | OpenAI | **72.0%** | `openai/o4-mini` | $1.10 / $4.40 | $1.10 / $4.40 | **$19.64** | 200K | ❌ | N/A |
| **14** | **DeepSeek R1 (0528)** | DeepSeek | **71.4%** | `deepseek/deepseek-reasoner` | $0.14 / $1.10 | $0.14 / $1.10 | **$4.80** | 128K | ✅ | 4×H100 |
| **15** | **Claude Opus 4 (no think)** | Anthropic | **70.7%** | `anthropic/claude-opus-4` | $15.00 / $75.00 | $15.00 / $75.00 | **$68.63** | 1M | ❌ | N/A |
| **16** | **DeepSeek-V3.2-Exp (Chat)** | DeepSeek | **70.2%** | `deepseek/deepseek-chat` | **$0.14 / $1.10** | **$0.14 / $1.10** | **$0.88** | 128K | ✅ | 4×H100 |
| **17** | **Claude Sonnet 3.7 (32k thinking)** | Anthropic | **64.9%** | `anthropic/claude-3.7-sonnet` | $3.00 / $15.00 | $3.00 / $15.00 | **$36.83** | 1M | ❌ | N/A |
| **18** | **DeepSeek R1 + Sonnet 3.5 (arch)** | DeepSeek/Anthropic | **64.0%** | `deepseek/deepseek-reasoner` + `anthropic/claude-3.5-sonnet` | $0.14/$1.10 + $3/$15 | $0.14/$1.10 + $3/$15 | **$13.29** | 128K+200K | ✅/❌ | 4×H100 + API |
| **19** | **o1 (high)** | OpenAI | **61.7%** | `openai/o1` | $15.00 / $60.00 | $15.00 / $60.00 | **$186.50** | 200K | ❌ | N/A |
| **20** | **Claude Sonnet 4 (32k thinking)** | Anthropic | **61.3%** | `anthropic/claude-sonnet-4` | $3.00 / $15.00 | $3.00 / $15.00 | **$26.58** | 1M | ❌ | N/A |
| **21** | **Claude Sonnet 3.7 (no thinking)** | Anthropic | **60.4%** | `anthropic/claude-3.7-sonnet` | $3.00 / $15.00 | $3.00 / $15.00 | **$17.72** | 1M | ❌ | N/A |
| **22** | **o3-mini (high)** | OpenAI | **60.4%** | `openai/o3-mini` | $1.10 / $4.40 | $1.10 / $4.40 | **$18.16** | 200K | ❌ | N/A |
| **23** | **Qwen3-235B-A22B** | Alibaba | **59.6%** | `qwen/qwen3-235b-a22b` | **Free** (Alibaba) | Free (Alibaba Cloud) | **~$0** | 128K | ✅ | 4×H100 (235B/22B MoE) |
| **24** | **Kimi K2** | Moonshot | **59.1%** | `moonshotai/kimi-k2` | ~$0.15 / $0.60 | ~$0.15 / $0.60 | **$1.24** | 128K | ❌ | N/A |
| **25** | **DeepSeek R1 (original)** | DeepSeek | **56.9%** | `deepseek/deepseek-reasoner` | $0.14 / $1.10 | $0.14 / $1.10 | **$5.42** | 128K | ✅ | 4×H100 |

---

## Extended Models (Not on Aider) — SWE-bench / Other Benchmarks

| Model | Provider | Benchmark Score | OpenRouter Model ID | OpenRouter Pricing (In/Out) | Direct API Pricing | Open Weights | Self-Host Cost |
|-------|----------|----------------|---------------------|----------------------------|-------------------|--------------|----------------|
| **GLM-5.3 / 5.3-Flash** | Z.ai | ~55% SWE-bench (OpenHands) | `zai-org/glm-5.3` | ~$0.10 / $0.40 | ~$0.10 / $0.40 | ✅ (FP8/GGUF) | 2×H100 (MoE) |
| **GLM-5.2 / 5.2-FP8** | Z.ai | ~52% SWE-bench (OpenHands) | `zai-org/glm-5.2` | ~$0.10 / $0.40 | ~$0.10 / $0.40 | ✅ | 2×H100 |
| **GLM-5 (high)** | Z.ai | ~50% mini-SWE | — | — | — | ✅ | 2×H100 |
| **GLM-4.7-Flash** | Z.ai | ~44% mini-SWE | `zai-org/glm-4.7-flash` | ~$0.05 / $0.20 | ~$0.05 / $0.20 | ✅ | 1×A100 |
| **GLM-4.6** | Z.ai | ~45% mini-SWE | `zai-org/glm-4.6` | ~$0.10 / $0.40 | ~$0.10 / $0.40 | ✅ | 2×H100 |
| **GLM-4.5** | Z.ai | ~42% mini-SWE | `zai-org/glm-4.5` | ~$0.10 / $0.40 | ~$0.10 / $0.40 | ✅ | 2×H100 |
| **Kimi K3** | Moonshot | Latest (not benched) | `moonshotai/kimi-k3` | ~$0.20 / $0.80 | ~$0.20 / $0.80 | ❌ | N/A |
| **Kimi K2.6** | Moonshot | Latest | `moonshotai/kimi-k2.6` | ~$0.15 / $0.60 | ~$0.15 / $0.60 | ❌ | N/A |
| **Kimi K2.5** | Moonshot | ~45% OpenHands | `moonshotai/kimi-k2.5` | ~$0.15 / $0.60 | ~$0.15 / $0.60 | ❌ | N/A |
| **Kimi K2.5 (high)** | Moonshot | ~42% mini-SWE | `moonshotai/kimi-k2.5` (high) | ~$0.15 / $0.60 | ~$0.15 / $0.60 | ❌ | N/A |
| **Kimi K2-Instruct** | Moonshot | ~40% OpenHands | `moonshotai/kimi-k2-instruct` | ~$0.15 / $0.60 | ~$0.15 / $0.60 | ❌ | N/A |
| **Kimi K2-Thinking** | Moonshot | ~37% mini-SWE | `moonshotai/kimi-k2-thinking` | ~$0.15 / $0.60 | ~$0.15 / $0.60 | ❌ | N/A |
| **Kimi-Linear-48B-A3B** | Moonshot | Base model | — | — | — | ❌ (base ✅) | N/A |
| **Nemotron-3-Super-120B-A12B** | NVIDIA | ~35% (CORTEXA) | `nvidia/nemotron-3-super-120b` | ~$0.50 / $2.00 | — | ✅ | 4×H100 (120B/12B MoE) |
| **Nemotron-3-Nano-30B-A3B** | NVIDIA | — | `nvidia/nemotron-3-nano-30b` | ~$0.10 / $0.40 | — | ✅ | 1×A100 (30B/3B MoE) |
| **Nemotron-3-Nano-4B** | NVIDIA | — | `nvidia/nemotron-3-nano-4b` | ~$0.05 / $0.20 | — | ✅ | 1×A100 (4B dense) |
| **Nemotron-3.5-Lightning-30B-A3B** | NVIDIA | — | `nvidia/nemotron-3.5-lightning-30b` | ~$0.10 / $0.40 | — | ✅ | 1×A100 |
| **Nemotron-3-Nano-Omni-30B-Reasoning** | NVIDIA | — | `nvidia/nemotron-3-nano-omni-30b-reasoning` | ~$0.10 / $0.40 | — | ✅ | 1×A100 |
| **Nemotron-3-Embed-1B** | NVIDIA | Embedding | `nvidia/nemotron-3-embed-1b` | ~$0.01 / — | — | ✅ | CPU/GPU |
| **Qwen3-Coder-480B-A35B-Instruct** | Alibaba | ~52% OpenHands | `qwen/qwen3-coder-480b-a35b` | ~$0.50 / $2.00 | Free (Alibaba) | ✅ | 8×H100 (480B/35B MoE) |
| **Qwen3-Coder-30B-A3B-Instruct** | Alibaba | ~45% OpenHands | `qwen/qwen3-coder-30b-a3b` | ~$0.10 / $0.40 | Free (Alibaba) | ✅ | 1×A100 (30B/3B MoE) |
| **Qwen3-Coder-Next** | Alibaba | ~62% BigCodeBench | `qwen/qwen3-coder-next` | ~$0.50 / $2.00 | Free (Alibaba) | ✅ | 8×H100 |
| **Doubao-Seed-Code** | ByteDance | ~50% (TRAE) | `bytedance/doubao-seed-code` | ~$0.30 / $1.20 | — | ❌ | N/A |
| **MiniMax M2.5** | MiniMax | ~48% mini-SWE | `minimax/minimax-m2.5` | ~$0.20 / $0.80 | — | ❌ | N/A |
| **MiniMax M2.5 (high)** | MiniMax | ~45% mini-SWE | `minimax/minimax-m2.5` (high) | ~$0.20 / $0.80 | — | ❌ | N/A |
| **Devstral Small (2512)** | Mistral | ~35% mini-SWE | `mistral/devstral-small-2512` | ~$0.10 / $0.40 | ~$0.10 / $0.40 | ✅ | 1×A100 |
| **Devstral (2507/2505)** | Mistral | ~32% OpenHands | `mistral/devstral` | ~$0.10 / $0.40 | ~$0.10 / $0.40 | ✅ | 1×A100 |
| **Llama 4 Maverick Instruct** | Meta | ~38% mini-SWE | `meta-llama/llama-4-maverick` | ~$0.50 / $2.00 | — | ✅ | 8×H100 (400B MoE) |
| **Llama 4 Scout Instruct** | Meta | ~35% mini-SWE | `meta-llama/llama-4-scout` | ~$0.20 / $0.80 | — | ✅ | 4×H100 |
| **gpt-oss-120b** | OpenAI | **41.8%** (Aider) | `openai/gpt-oss-120b` | ~$0.10 / $0.40 | — | ✅ | 2×H100 (120B) |
| **Amazon Nova Premier** | Amazon | ~38% mini-SWE | `amazon/nova-premier` | ~$0.30 / $1.20 | — | ❌ | N/A |
| **Skywork-SWE-32B** | Kunlun | ~32% (SWE-agent) | `kunlun/skywork-swe-32b` | ~$0.10 / $0.40 | — | ✅ | 1×A100 |
| **Lingma SWE-GPT 72B** | Alibaba | ~35% (Lingma) | — | — | — | ❌ | N/A |
| **CodeAct v2.1 (Sonnet 3.5)** | Anthropic | ~52% OpenHands | `anthropic/claude-3.5-sonnet` (prompted) | $3.00 / $15.00 | $3.00 / $15.00 | ❌ | N/A |
| **SWE-agent-LM-32B** | Princeton | ~30% (SWE-agent) | — | — | — | ✅ | 1×A100 |

---

## Cost-Efficiency Ranking (Pass@2 per $100) — Aider Models Only

| Model | Pass@2 | Cost/Run | Pass@2 per $100 | Provider | OpenRouter ID |
|-------|--------|----------|-----------------|----------|---------------|
| **DeepSeek-V3.2-Exp (Chat)** | 70.2% | **$0.88** | **7,977%** | DeepSeek | `deepseek/deepseek-chat` |
| **DeepSeek-V3.2-Exp (Reasoner)** | 74.2% | **$1.30** | **5,708%** | DeepSeek | `deepseek/deepseek-reasoner` |
| **Kimi K2** | 59.1% | $1.24 | 4,766% | Moonshot | `moonshotai/kimi-k2` |
| **DeepSeek R1** | 56.9% | $4.80 | 1,185% | DeepSeek | `deepseek/deepseek-reasoner` |
| **GPT-5 (low)** | 81.3% | $10.37 | 784% | OpenAI | `openai/gpt-5` (low) |
| **GPT-5 (medium)** | 86.7% | $17.69 | 490% | OpenAI | `openai/gpt-5` (medium) |
| **o3 (high)** | 81.3% | $21.23 | 383% | OpenAI | `openai/o3` |
| **Claude Sonnet 3.7** | 60.4% | $17.72 | 341% | Anthropic | `anthropic/claude-3.7-sonnet` |
| **GPT-5 (high)** | 88.0% | $29.08 | 303% | OpenAI | `openai/gpt-5` (high) |
| **Gemini 2.5 Pro (def)** | 79.1% | $45.60 | 173% | Google | `google/gemini-2.5-pro` |
| **Claude Opus 4** | 72.0% | $65.75 | 109% | Anthropic | `anthropic/claude-opus-4` |
| **o3-pro (high)** | 84.9% | $146.32 | 58% | OpenAI | `openai/o3-pro` |

---

## Open Weights Models — Self-Hosting Cost Comparison

| Model | Params (Active/Total) | VRAM (BF16) | Min GPUs | Est. Hourly Cost (RunPod/λ) | OpenRouter Available | Best For |
|-------|----------------------|-------------|----------|----------------------------|---------------------|----------|
| **DeepSeek-V3.2-Exp** | 37B active / 671B | ~400GB | 4×H100 (80GB) | ~$12/hr | ✅ | Best reasoning open model |
| **DeepSeek R1** | 37B active / 671B | ~400GB | 4×H100 | ~$12/hr | ✅ | Reasoning tasks |
| **Qwen3-Coder-30B-A3B** | 3B active / 30B | ~24GB | 1×A100/H100 | ~$1.50/hr | ✅ | Efficient coding |
| **Qwen3-Coder-480B-A35B** | 35B active / 480B | ~600GB | 8×H100 | ~$24/hr | ✅ | Maximum quality open coder |
| **Nemotron-3-Super-120B-A12B** | 12B active / 120B | ~120GB | 2×H100 | ~$6/hr | ✅ | Agentic coding |
| **Nemotron-3-Nano-30B-A3B** | 3B active / 30B | ~24GB | 1×A100 | ~$1.50/hr | ✅ | Efficient inference |
| **Nemotron-3-Nano-4B** | 4B dense | ~8GB | 1×RTX 4090/A100 | ~$0.50/hr | ✅ | Edge/on-device |
| **Nemotron-3.5-Lightning-30B-A3B** | 3B active / 30B | ~24GB | 1×A100 | ~$1.50/hr | ✅ | Fast inference |
| **GLM-5.3 / 5.2** | ~30B active / ~300B | ~200GB | 3×H100 | ~$9/hr | ✅ | Chinese/English bilingual |
| **GLM-4.7-Flash** | ~10B active | ~40GB | 1×A100 | ~$1.50/hr | ✅ | Fast bilingual |
| **Llama 4 Maverick** | ~17B active / 400B | ~400GB | 4×H100 | ~$12/hr | ✅ | General purpose |
| **Llama 4 Scout** | ~17B active / ~100B | ~100GB | 2×H100 | ~$6/hr | ✅ | Smaller variant |
| **Devstral Small** | 24B dense | ~48GB | 1×A100 80GB | ~$2/hr | ✅ | Code-focused small |
| **gpt-oss-120b** | 120B dense | ~240GB | 4×H100 | ~$12/hr | ✅ | OpenAI open model |
| **Skywork-SWE-32B** | 32B dense | ~64GB | 1×A100 80GB | ~$2/hr | ✅ | SWE-specialized |

---

## opencode / OpenRouter Quick Reference

### **Best Value Tiers for opencode Users**

| Tier | Model | OpenRouter ID | Cost/Run | Use Case |
|------|-------|---------------|----------|----------|
| **🏆 Absolute Best Value** | DeepSeek-V3.2-Exp (Chat) | `deepseek/deepseek-chat` | **$0.88** | Daily coding, best ROI |
| **🏆 Best Reasoning Value** | DeepSeek-V3.2-Exp (Reasoner) | `deepseek/deepseek-reasoner` | **$1.30** | Complex refactoring, algorithms |
| **💰 Budget Premium** | GPT-5 (low) | `openai/gpt-5` (low) | **$10.37** | High quality, reasonable cost |
| **⚖️ Balanced Premium** | GPT-5 (medium) | `openai/gpt-5` (medium) | **$17.69** | Best quality/cost balance |
| **🧠 Max Reasoning** | o3 (high) | `openai/o3` | **$21.23** | Hard reasoning tasks |
| **📏 Max Context** | Gemini 2.5 Pro | `google/gemini-2.5-pro` | **$45.60** | Large repos, long files |
| **🇨🇳 Chinese/English** | GLM-5.3 / Kimi K2 | `zai-org/glm-5.3` / `moonshotai/kimi-k2` | **$0.40-1.24** | Bilingual work |
| **🏠 Self-Hosted** | Nemotron-3-Nano-30B / Qwen3-Coder-30B | Via local inference | **$1.50/hr GPU** | Privacy, no API limits |

### **opencode Config Examples**

```bash
# Best value (DeepSeek Chat)
opencode --model deepseek/deepseek-chat

# Best reasoning (DeepSeek Reasoner)
opencode --model deepseek/deepseek-reasoner

# Best quality/cost balance (GPT-5 medium)
opencode --model openai/gpt-5 --reasoning-effort medium

# Max reasoning (o3 high)
opencode --model openai/o3 --reasoning-effort high

# Massive context (Gemini 2.5 Pro)
opencode --model google/gemini-2.5-pro

# Chinese/English (GLM-5.3)
opencode --model zai-org/glm-5.3

# Self-hosted via Ollama (if running locally)
opencode --model ollama/nemotron-3-nano-30b --base-url http://localhost:11434/v1
```

---

## Provider Availability on OpenRouter (Verified)

| Provider | Models on OpenRouter | Notes |
|----------|---------------------|-------|
| **OpenAI** | ✅ All (GPT-5, o3, o1, o4-mini, o3-mini, gpt-oss) | Full reasoning support |
| **Anthropic** | ✅ All (Opus 4, Sonnet 4, 3.7, 3.5) | Thinking tokens supported |
| **Google** | ✅ All (Gemini 2.5 Pro/Flash, 2.0) | Thinking tokens supported |
| **DeepSeek** | ✅ All (V3.2, R1, V3, Chat) | **Cheapest reasoning models** |
| **xAI** | ✅ Grok-4, Grok-3, Grok-3-mini | Good alternative |
| **Moonshot (Kimi)** | ✅ K2, K2.5, K3, K2-Instruct/Thinking | Chinese optimized |
| **Z.ai (GLM)** | ✅ GLM-5.3, 5.2, 4.7-Flash, 4.6, 4.5 | **Open weights + API** |
| **NVIDIA** | ✅ Nemotron-3-Super, Nano, Lightning, Omni, Embed | **Open weights + API** |
| **Alibaba (Qwen)** | ✅ Qwen3-Coder-480B/30B, Next, Qwen3-235B | **Open weights + API** |
| **Meta** | ✅ Llama 4 Maverick/Scout, Llama 3.x | Open weights |
| **Mistral** | ✅ Devstral, Codestral, Mixtral | Open weights |
| **ByteDance** | ✅ Doubao-Seed-Code | New additions |
| **MiniMax** | ✅ M2.5, M2.5-high | Chinese optimized |
| **Amazon** | ✅ Nova Premier, Nova Pro/Lite | Large context |
| **Kunlun** | ✅ Skywork-SWE-32B | SWE-specialized |

---

## Decision Matrix: Choose Your Model

| If you want... | Use This Model | OpenRouter ID | Est. Cost/Run |
|----------------|----------------|---------------|---------------|
| **Lowest possible cost, good quality** | DeepSeek-V3.2-Exp (Chat) | `deepseek/deepseek-chat` | **$0.88** |
| **Best reasoning for low cost** | DeepSeek-V3.2-Exp (Reasoner) | `deepseek/deepseek-reasoner` | **$1.30** |
| **Best overall quality (money no object)** | GPT-5 (high) | `openai/gpt-5` | $29.08 |
| **Best quality per dollar (premium)** | GPT-5 (medium) | `openai/gpt-5` (medium) | $17.69 |
| **Maximum context (huge repos)** | Gemini 2.5 Pro | `google/gemini-2.5-pro` | $45.60 |
| **Strong reasoning, mid-price** | o3 (high) | `openai/o3` | $21.23 |
| **Anthropic ecosystem** | Claude Sonnet 3.7 | `anthropic/claude-3.7-sonnet` | $17.72 |
| **Chinese/English bilingual** | GLM-5.3 or Kimi K2 | `zai-org/glm-5.3` / `moonshotai/kimi-k2` | $0.40-1.24 |
| **Self-hosted, privacy, no limits** | Nemotron-3-Nano-30B / Qwen3-Coder-30B | Local (Ollama/vLLM) | $1.50/hr GPU |
| **Edge/on-device** | Nemotron-3-Nano-4B | Local (llama.cpp) | Runs on 8GB VRAM |
| **Open weights, max coding quality** | Qwen3-Coder-480B-A35B | `qwen/qwen3-coder-480b-a35b` | Free (Alibaba API) / $24/hr self-host |

---

## Notes

1. **OpenRouter pricing** matches or beats direct API pricing for most models (they aggregate and optimize)
2. **Cost/Run** = Aider Polyglot 225-task benchmark cost (from Aider leaderboard data)
3. **Self-host costs** estimated on RunPod/λ Labs spot pricing (H100 80GB ~$3/hr, A100 80GB ~$1.50/hr)
4. **Open weights** = can download and run locally; **API only** = must use provider endpoint
5. **Reasoning models** (o3, GPT-5, DeepSeek R1, GLM-5 high, Kimi Thinking) cost more output tokens due to thinking traces
6. **Architect/editor patterns** (o3 + GPT-4.1, R1 + Sonnet) use two models — cost is sum of both
7. **Free tiers**: Qwen3-235B and Qwen3-Coder via Alibaba Cloud API (rate limited); DeepSeek via OpenRouter has generous free tier
8. **Prices change frequently** — check OpenRouter model page for latest: `https://openrouter.ai/models/<model-id>`

---

*Data from: Aider leaderboards, OpenRouter model pages, provider API docs, Hugging Face model cards. Self-host estimates based on BF16 quantization VRAM requirements. Last verified September 2026.*