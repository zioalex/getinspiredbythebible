<!-- markdownlint-disable MD024 MD036 MD040 MD013 -->
# Azure Deployment Options Comparison

## Your Question: VM vs Container Apps vs Kubernetes?

For your Bible Chat app with a **$50/month budget**, here's the detailed analysis:

## TL;DR Recommendation

**🏆 Winner: Azure Container Apps**

| Criteria | VM | Container Apps ⭐ | AKS |
|----------|-----|-------------------|-----|
| **Fits $50 budget** | ⚠️ Tight | ✅ Yes | ❌ Barely |
| **Docker Compose** | ✅ As-is | ❌ Split | ❌ Convert |
| **Operational burden** | High | Low | Medium |
| **Scale-to-zero** | ❌ No | ✅ Yes | ❌ No |
| **Cold starts** | None | 2-5s | None |
| **Best for** | Dev/test | **Production MVP** | Enterprise |

---

## Option 1: Single VM (Azure VM B-series)

### Architecture

```
┌─────────────────────────────────────────┐
│           Azure VM (B2s)                │
│  ┌─────────────────────────────────┐   │
│  │     Docker Compose              │   │
│  │  ┌─────────┐  ┌──────────┐     │   │
│  │  │Frontend │  │ Backend  │     │   │
│  │  └─────────┘  └──────────┘     │   │
│  │       ┌──────────────┐         │   │
│  │       │  PostgreSQL  │         │   │
│  │       │  + pgvector  │         │   │
│  │       └──────────────┘         │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Cost Breakdown

| Resource | SKU | Monthly Cost |
|----------|-----|--------------|
| VM | B2s (2 vCPU, 4GB) | ~$30 |
| Managed Disk | 64GB SSD | ~$5 |
| Public IP | Static | ~$3 |
| **Total** | | **~$38** |

**Or with managed PostgreSQL:**
| Resource | SKU | Monthly Cost |
|----------|-----|--------------|
| VM | B1s (1 vCPU, 1GB) | ~$7 |
| PostgreSQL Flexible | B1ms | ~$16 |
| Disk + IP | | ~$8 |
| **Total** | | **~$31** |

### Pros

- ✅ Docker Compose works unchanged
- ✅ Simple mental model
- ✅ No cold starts
- ✅ Full control

### Cons

- ❌ You manage OS updates, security patches
- ❌ Always running = always paying
- ❌ No auto-scaling
- ❌ Single point of failure
- ❌ Manual SSL setup (Certbot)

### Best For

- Development/testing
- Learning
- When you need Docker Compose exactly as-is

---

## Option 2: Azure Container Apps ⭐ RECOMMENDED

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Azure Container Apps Environment                │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │    Frontend      │ ──────▶ │    Backend       │         │
│  │    (Next.js)     │         │    (FastAPI)     │         │
│  │   Scale: 0-2     │         │   Scale: 0-2     │         │
│  └──────────────────┘         └────────┬─────────┘         │
└───────────────────────────────────────┼─────────────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────┐
                          │  PostgreSQL Flexible    │
                          │  Server + pgvector      │
                          │  (B1ms - managed)       │
                          └─────────────────────────┘
```

### Cost Breakdown

| Resource | Details | Monthly Cost |
|----------|---------|--------------|
| Container Apps | Scale-to-zero, consumption | ~$5-15* |
| PostgreSQL | B1ms (1 vCore) | ~$13-16 |
| Container Registry | Basic | ~$5 |
| Log Analytics | Per GB | ~$2-3 |
| **Total** | | **~$25-40** |

*Includes 180,000 free vCPU-seconds/month

### Pros

- ✅ **Scale-to-zero** = pay only when used
- ✅ Managed infrastructure (no patching)
- ✅ Built-in HTTPS with custom domains
- ✅ Easy CI/CD integration
- ✅ Fits comfortably in $50 budget
- ✅ Production-ready

### Cons

- ❌ Must split Docker Compose into services
- ❌ Cold starts (2-5 seconds) after idle
- ❌ Learning curve for Azure

### Best For

- **Production MVPs** ← Your case
- Cost-conscious deployments
- Apps with variable traffic
- Serverless-style architecture

---

## Option 3: Azure Kubernetes Service (AKS)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AKS Cluster                              │
│  ┌────────────────────────────────────────────────────────┐│
│  │                   Node Pool                            ││
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐ ││
│  │  │Frontend │  │Backend  │  │  Nginx  │  │PostgreSQL│ ││
│  │  │  Pod    │  │  Pod    │  │ Ingress │  │   Pod    │ ││
│  │  └─────────┘  └─────────┘  └─────────┘  └──────────┘ ││
│  │           Node: Standard_B2s (~$30/mo)                 ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Cost Breakdown

| Resource | Details | Monthly Cost |
|----------|---------|--------------|
| AKS Control Plane | Free tier | $0 |
| Node (B2s) | 2 vCPU, 4GB | ~$30 |
| PostgreSQL Flexible | B1ms | ~$16 |
| Load Balancer | Standard | ~$18 |
| **Total** | | **~$64** ❌ Over budget |

**Cheaper alternative (self-hosted DB):**
| Resource | Details | Monthly Cost |
|----------|---------|--------------|
| AKS + Node | B2s | ~$30 |
| PostgreSQL in-cluster | StatefulSet | $0 (included) |
| Load Balancer | Basic | ~$5 |
| **Total** | | **~$35** ⚠️ Tight |

### Pros

- ✅ Kubernetes experience
- ✅ Maximum flexibility
- ✅ Industry standard
- ✅ Easy to scale later

### Cons

- ❌ **Over $50 budget** with managed DB
- ❌ Complex for simple apps
- ❌ Need to convert Docker Compose to K8s manifests
- ❌ Overkill for your use case
- ❌ Operational complexity

### Best For

- Enterprise applications
- Teams with K8s experience
- Multi-service architectures
- When you'll scale significantly

---

## Decision Matrix

| Your Priority | Choose |
|--------------|--------|
| **Lowest cost** | Container Apps |
| **Simplest migration** | VM |
| **Production ready** | Container Apps |
| **Learning K8s** | AKS |
| **No cold starts** | VM or AKS |
| **Auto-scaling** | Container Apps |
| **Full control** | VM |

---

## Migration Effort Comparison

### From Docker Compose to

**VM**: Minimal changes

```bash
# Just copy and run
scp -r . azure-vm:/app
ssh azure-vm "cd /app && docker compose up -d"
```

**Container Apps**: Moderate changes

- Split `docker-compose.yml` into separate container definitions
- Update environment variables for Azure
- Configure ingress rules
- ~2-4 hours of work

**AKS**: Significant changes

- Convert to Kubernetes manifests (Deployments, Services, ConfigMaps)
- Set up Ingress controller
- Configure persistent volumes for PostgreSQL
- ~4-8 hours of work (or use Kompose tool)

---

## My Recommendation for Your Project

**Start with Container Apps because:**

1. **Budget**: Comfortably fits $50/month with room to spare
2. **Scale-to-zero**: When no one's using it at 3 AM, you're not paying
3. **Managed**: No VMs to patch, no infrastructure to manage
4. **Production-ready**: HTTPS, custom domains, health checks built-in
5. **Growth path**: Easy to increase resources or add services later

**The trade-off** (2-5s cold start) is acceptable for a Bible inspiration app - users won't mind a brief pause before receiving spiritual encouragement.

---

## Quick Start with Container Apps

```bash
# 1. Deploy infrastructure
cd terraform-azure
terraform init
terraform apply

# 2. Build and push images
az acr login --name <your-acr>
docker build -t <acr>/bible-backend:latest ./backend
docker push <acr>/bible-backend:latest

# 3. Update container apps
az containerapp update --name bible-app-backend --image <acr>/bible-backend:latest
```

That's it - you're running in production! 🎉
