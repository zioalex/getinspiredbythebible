<!-- markdownlint-disable MD040 -->
# Azure Terraform Module - Bible Chat Application

Deploy the **Get Inspired by the Bible** application on Azure using Container Apps with scale-to-zero capability.

## 💰 Cost Breakdown (~$25-40/month)

| Service | SKU | Monthly Cost |
|---------|-----|--------------|
| PostgreSQL Flexible | B1ms (1 vCore, 2GB) | ~$13-16 |
| Container Registry | Basic | ~$5 |
| Container Apps | Consumption (scale-to-zero) | ~$5-15* |
| Log Analytics | Per GB | ~$2-3 |
| **Total** | | **~$25-40** |

*Container Apps includes generous free tier: 180,000 vCPU-seconds + 360,000 GiB-seconds/month

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Container Apps Environment              │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Frontend        │ ──────▶ │  Backend         │             │
│  │  (Next.js)       │         │  (FastAPI)       │             │
│  │  Port 3000       │         │  Port 8000       │             │
│  └──────────────────┘         └────────┬─────────┘             │
│         │                              │                        │
└─────────┼──────────────────────────────┼────────────────────────┘
          │                              │
          ▼                              ▼
    ┌──────────┐              ┌─────────────────────┐
    │  Users   │              │  PostgreSQL         │
    │  (HTTPS) │              │  + pgvector         │
    └──────────┘              │  (Flexible Server)  │
                              └─────────────────────┘
```

## 📋 Prerequisites

1. **Azure Account** with active subscription
2. **Azure CLI** installed and logged in
3. **Terraform** >= 1.0.0
4. **Docker** for building images

## 🚀 Quick Start

### 1. Azure CLI Setup

```bash
# Install Azure CLI (if needed)
# macOS: brew install azure-cli
# Windows: winget install Microsoft.AzureCLI
# Linux: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Set your subscription
az account set --subscription "Your Subscription Name"

# Verify
az account show
```

### 2. Clone and Configure

```bash
# Navigate to terraform directory
cd terraform-azure

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
vim terraform.tfvars
```

### 3. Required Variables

```hcl
# terraform.tfvars

subscription_id   = "your-subscription-id"
location          = "westeurope"
db_admin_password = "YourSecurePassword123!"  # pragma: allowlist secret
claude_api_key    = "sk-ant-api03-..."  # pragma: allowlist secret
budget_alert_emails = ["your-email@example.com"]
```

### 4. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy (takes ~5-10 minutes)
terraform apply
```

### 5. Build and Push Images

```bash
# Login to your new ACR
az acr login --name $(terraform output -raw acr_login_server | cut -d'.' -f1)

# Build backend (from your repo root)
cd backend
docker build --platform linux/amd64 -t $(terraform output -raw acr_login_server)/bible-backend:latest .
docker push $(terraform output -raw acr_login_server)/bible-backend:latest

# Build frontend
cd ../frontend
docker build --platform linux/amd64 -t $(terraform output -raw acr_login_server)/bible-frontend:latest .
docker push $(terraform output -raw acr_login_server)/bible-frontend:latest
```

### 6. Update Container Apps

```bash
# Update terraform.tfvars with your images
backend_image  = "bibleappacr123abc.azurecr.io/bible-backend:latest"
frontend_image = "bibleappacr123abc.azurecr.io/bible-frontend:latest"

# Re-apply
terraform apply
```

### 7. Initialize Database

```bash
# Get connection details
terraform output postgresql_fqdn

# Connect with psql (use your password)
psql "host=$(terraform output -raw postgresql_fqdn) dbname=bibleapp user=bibleadmin sslmode=require"

# Enable pgvector (already configured, but verify)
CREATE EXTENSION IF NOT EXISTS vector;

# Run your migrations
# (depends on your app setup)
```

## 🌐 Access Your Application

After deployment, get URLs with:

```bash
terraform output frontend_url
terraform output backend_url
```

## 📁 Project Structure

```
terraform-azure/
├── main.tf                    # Main infrastructure
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── terraform.tfvars.example   # Example configuration
├── .gitignore                 # Ignore secrets
└── README.md                  # This file
```

## 🔧 Configuration Options

### Scale-to-Zero (Cost Savings)

```hcl
# Containers scale to 0 when not in use
backend_min_replicas  = 0  # Scale to zero
backend_max_replicas  = 2  # Handle traffic spikes

frontend_min_replicas = 0
frontend_max_replicas = 2
```

**Trade-off:** First request after idle takes ~2-5 seconds (cold start).

### Always-On (No Cold Starts)

```hcl
# Keep at least 1 replica running
backend_min_replicas  = 1  # ~$15-20 more/month
frontend_min_replicas = 1
```

### Resource Sizing

```hcl
# Larger containers for better performance
backend_cpu    = 1.0    # More CPU for embeddings
backend_memory = "2Gi"  # More memory for vector operations
```

## 🔄 CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure

on:
  push:
    branches: [main]

env:
  ACR_NAME: bibleappacr123abc  # Your ACR name

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Build and push backend
        run: |
          az acr login --name $ACR_NAME
          docker build -t $ACR_NAME.azurecr.io/bible-backend:${{ github.sha }} ./backend
          docker push $ACR_NAME.azurecr.io/bible-backend:${{ github.sha }}

      - name: Deploy backend
        run: |
          az containerapp update \
            --name bible-app-backend \
            --resource-group bible-app-rg \
            --image $ACR_NAME.azurecr.io/bible-backend:${{ github.sha }}
```

## 🛠️ Useful Commands

```bash
# View container logs
az containerapp logs show \
  --name bible-app-backend \
  --resource-group bible-app-rg \
  --follow

# Check container status
az containerapp show \
  --name bible-app-backend \
  --resource-group bible-app-rg \
  --query "properties.runningStatus"

# Scale manually
az containerapp update \
  --name bible-app-backend \
  --resource-group bible-app-rg \
  --min-replicas 1 \
  --max-replicas 5

# View costs
az consumption usage list \
  --start-date 2024-01-01 \
  --end-date 2024-01-31
```

## 🔐 Security Best Practices

1. **Restrict Database Access**

   ```hcl
   client_ip = "YOUR.IP.ADDRESS"  # Only allow your IP
   ```

2. **Use Managed Identity** (advanced)
   - Remove ACR admin credentials
   - Use system-assigned identity

3. **Enable HTTPS Only**
   - Already configured in Container Apps

4. **Rotate Secrets Regularly**

   ```bash
   az containerapp secret set \
     --name bible-app-backend \
     --resource-group bible-app-rg \
     --secrets claude-api-key=NEW_KEY
   ```

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check logs
az containerapp logs show -n bible-app-backend -g bible-app-rg

# Check events
az containerapp revision list -n bible-app-backend -g bible-app-rg -o table
```

### Database Connection Issues

```bash
# Verify firewall rules
az postgres flexible-server firewall-rule list \
  --resource-group bible-app-rg \
  --name bible-app-db-xxx

# Test connection
psql "host=bible-app-db-xxx.postgres.database.azure.com dbname=bibleapp user=bibleadmin sslmode=require"
```

### Cold Start Too Slow

Set `min_replicas = 1` to keep containers warm (costs ~$15-20 more/month).

## 🗑️ Cleanup

```bash
# Destroy all resources
terraform destroy

# Or delete resource group directly
az group delete --name bible-app-rg --yes
```

## 📊 Monitoring

View your spending in Azure Portal:

1. Go to **Cost Management + Billing**
2. Select **Cost analysis**
3. Filter by resource group: `bible-app-rg`

Budget alerts will email you at 80% and 100% of your $50 limit.

## 🔗 Resources

- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/)
- [pgvector on Azure](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-use-pgvector)
- [Terraform AzureRM Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest)

## 📝 License

MIT License - see repository root for details.
