<!-- markdownlint-disable MD013 MD040 -->
# Embedding Models on Azure: Options for Your Bible Chat App

## TL;DR Recommendation

**Use Azure OpenAI Embeddings** - It's incredibly cheap (~$0.20 one-time to embed all 31K Bible verses) and works perfectly with Container Apps. No GPU needed, no infrastructure to manage.

## Quick Comparison

| Option | Works on Container Apps | Monthly Cost | Cold Start | Quality | Setup Effort |
|--------|------------------------|--------------|------------|---------|--------------|
| **Azure OpenAI Embeddings** ⭐ | ✅ API call | ~$0.01-0.05 | None | Excellent | Easy |
| **OpenAI API (direct)** | ✅ API call | ~$0.01-0.05 | None | Excellent | Easy |
| **Self-hosted (CPU)** | ⚠️ Slow | ~$10-20 | 30-60s | Good | Medium |
| **Azure ML Endpoint** | ✅ | ~$15-30 | 5-10s | Excellent | Complex |
| **Hugging Face Inference** | ✅ API call | Free tier | Variable | Good | Easy |

---

## Option 1: Azure OpenAI Embeddings ⭐ RECOMMENDED

### Why It's Best for Your Project

Your Bible has ~31,000 verses. Here's the math:

| Metric | Value |
|--------|-------|
| Verses | ~31,000 |
| Avg tokens/verse | ~65 |
| Total tokens | ~2,000,000 |
| **One-time embedding cost** | **~$0.20** |
| Runtime queries (per month) | ~$0.01-0.05 |

**That's 20 cents to embed the entire Bible!**

### Available Models

| Model | Dimensions | Price per 1M tokens | Best For |
|-------|------------|---------------------|----------|
| text-embedding-3-small | 1536 | $0.02 | General use ⭐ |
| text-embedding-3-large | 3072 | $0.13 | Maximum quality |
| text-embedding-ada-002 | 1536 | $0.10 | Legacy support |

### Integration Code

```python
# backend/app/services/embeddings.py
from openai import AzureOpenAI
import os

class AzureEmbeddingService:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-01",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment_name = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        response = self.client.embeddings.create(
            input=texts,
            model=self.deployment_name
        )
        return [item.embedding for item in response.data]

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return self.embed([text])[0]
```

### Setup in Azure Portal

1. **Create Azure OpenAI resource:**

   ```bash
   az cognitiveservices account create \
     --name bible-app-openai \
     --resource-group bible-app-rg \
     --kind OpenAI \
     --sku S0 \
     --location eastus
   ```

2. **Deploy embedding model:**

   ```bash
   az cognitiveservices account deployment create \
     --name bible-app-openai \
     --resource-group bible-app-rg \
     --deployment-name text-embedding-3-small \
     --model-name text-embedding-3-small \
     --model-version "1" \
     --model-format OpenAI \
     --sku-name Standard \
     --sku-capacity 120
   ```

3. **Get credentials:**

   ```bash
   az cognitiveservices account keys list \
     --name bible-app-openai \
     --resource-group bible-app-rg
   ```

### Terraform Addition

Add to your `main.tf`:

```hcl
# Azure OpenAI for Embeddings
resource "azurerm_cognitive_account" "openai" {
  name                = "${local.name_prefix}-openai-${local.resource_suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  kind                = "OpenAI"
  sku_name            = "S0"

  tags = local.tags
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }

  sku {
    name     = "Standard"
    capacity = 120  # Tokens per minute (in thousands)
  }
}
```

---

## Option 2: Self-Hosted on Container Apps (CPU)

### ⚠️ Limitations

Container Apps **does NOT support GPUs**. You're limited to CPU inference which is:

- **Slow**: 100-500ms per embedding (vs 10-50ms with GPU)
- **Resource hungry**: Needs 2GB+ RAM for decent models
- **Cold start**: 30-60 seconds to load model

### When It Makes Sense

- You need 100% data privacy (no external API calls)
- You're embedding millions of documents continuously
- You have specific model requirements

### Recommended CPU-Efficient Models

| Model | Size | RAM Needed | Speed (CPU) | Quality |
|-------|------|------------|-------------|---------|
| all-MiniLM-L6-v2 | 80MB | 512MB | ~50ms/text | Good |
| static-retrieval-mrl-en-v1 | 25MB | 256MB | ~0.5ms/text ⚡ | Moderate |
| all-mpnet-base-v2 | 420MB | 1.5GB | ~200ms/text | Better |
| bge-small-en-v1.5 | 130MB | 768MB | ~80ms/text | Good |

### Implementation with HuggingFace TEI (Text Embeddings Inference)

**Dockerfile for embedding service:**

```dockerfile
# embeddings/Dockerfile
FROM ghcr.io/huggingface/text-embeddings-inference:cpu-latest

# Pre-download model at build time
ENV MODEL_ID=sentence-transformers/all-MiniLM-L6-v2
```

**Or custom FastAPI service:**

```dockerfile
# embeddings/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download model during build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**requirements.txt:**

```
fastapi==0.109.0
uvicorn==0.27.0
sentence-transformers==2.2.2
torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
```

**main.py:**

```python
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI()
model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')

class EmbedRequest(BaseModel):
    texts: list[str]

@app.post("/embed")
async def embed(request: EmbedRequest):
    embeddings = model.encode(request.texts, convert_to_numpy=True)
    return {"embeddings": embeddings.tolist()}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### Container Apps Configuration (if self-hosted)

```hcl
resource "azurerm_container_app" "embeddings" {
  name                         = "${local.name_prefix}-embeddings"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    min_replicas = 1  # Keep warm to avoid cold starts
    max_replicas = 2

    container {
      name   = "embeddings"
      image  = "${azurerm_container_registry.main.login_server}/bible-embeddings:latest"
      cpu    = 1.0      # Need decent CPU
      memory = "2Gi"    # Model needs RAM

      env {
        name  = "MODEL_NAME"
        value = "sentence-transformers/all-MiniLM-L6-v2"
      }
    }
  }

  ingress {
    external_enabled = false  # Internal only
    target_port      = 8000
    transport        = "http"
  }
}
```

**Monthly cost for self-hosted embeddings:**

- Container App (1 CPU, 2GB, always-on): ~$30-40/month
- **This exceeds your entire budget!**

---

## Option 3: Hugging Face Inference API (Free Tier)

### Good for Prototyping

```python
import requests

def embed_with_hf(texts: list[str]) -> list[list[float]]:
    API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
    headers = {"Authorization": f"Bearer {os.getenv('HF_API_TOKEN')}"}

    response = requests.post(API_URL, headers=headers, json={"inputs": texts})
    return response.json()
```

### Limitations

- Rate limited on free tier
- Variable latency (can be slow)
- Model may be cold (loading delay)
- Not recommended for production

---

## Cost Comparison Summary

For your Bible app with 31K verses + ~1000 queries/month:

| Option | One-time Embed | Monthly Runtime | Total Year 1 |
|--------|---------------|-----------------|--------------|
| **Azure OpenAI** ⭐ | $0.20 | ~$0.05 | **~$0.80** |
| OpenAI API (direct) | $0.04 | ~$0.02 | **~$0.28** |
| Self-hosted (Container Apps) | $0 | ~$35 | **~$420** ❌ |
| HuggingFace Free | $0 | $0 | **$0** (rate limits) |

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Azure Container Apps Environment                    │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │    Frontend      │ ──────▶ │    Backend       │             │
│  │    (Next.js)     │         │    (FastAPI)     │             │
│  └──────────────────┘         └────────┬─────────┘             │
└───────────────────────────────────────┼─────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
          ┌─────────────────┐  ┌───────────────┐  ┌─────────────────┐
          │  PostgreSQL +   │  │ Azure OpenAI  │  │  Claude API     │
          │  pgvector       │  │ Embeddings    │  │  (Chat)         │
          │  (Flexible)     │  │ (~$0.05/mo)   │  │                 │
          └─────────────────┘  └───────────────┘  └─────────────────┘
```

### Flow

1. **Initial Setup (one-time):**
   - Load Bible verses into PostgreSQL
   - Call Azure OpenAI to generate embeddings for all verses
   - Store embeddings in pgvector column
   - Cost: ~$0.20

2. **Runtime (per user query):**
   - User asks question
   - Backend calls Azure OpenAI to embed the query (~$0.00002)
   - pgvector finds similar verses (free - in PostgreSQL)
   - Claude generates inspirational response (your existing setup)

---

## Final Recommendation

**Stick with Azure OpenAI Embeddings:**

1. ✅ Works perfectly with Container Apps (just API calls)
2. ✅ Costs pennies per month
3. ✅ No infrastructure to manage
4. ✅ Fast (no cold starts)
5. ✅ High quality embeddings
6. ✅ Stays well within your $50 budget

**Updated budget with embeddings:**

| Service | Monthly Cost |
|---------|--------------|
| PostgreSQL Flexible | ~$16 |
| Container Registry | ~$5 |
| Container Apps | ~$5-15 |
| Log Analytics | ~$2-3 |
| **Azure OpenAI Embeddings** | **~$0.05** |
| **Total** | **~$28-40** ✅ |

The embedding cost is negligible - about the price of a coffee per year!
