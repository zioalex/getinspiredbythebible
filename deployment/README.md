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

### 0. Set Up Terraform Remote State (Recommended)

For team collaboration and CI/CD pipelines, use Azure Blob Storage for Terraform state:

```bash
cd deployment

# Run the setup script (creates storage account, resource group, container)
./scripts/setup-tf-backend.sh [subscription_id] [location]

# Example:
./scripts/setup-tf-backend.sh "12345678-1234-1234-1234-123456789012" "northeurope"
```

The script will:

- Create resource group `bible-app-tfstate-rg`
- Create a storage account with versioning enabled
- Create a blob container `tfstate`
- Output the storage account name for use in `terraform init`

**Initialize with remote state:**

```bash
# Option 1: Pass storage account name directly
terraform init -backend-config="storage_account_name=bibleapptfstateXXXXXX"

# Option 2: Use a backend config file (recommended)
cp backend.hcl.example backend.hcl
# Edit backend.hcl with your storage account name
terraform init -backend-config=backend.hcl
```

> **Note:** `backend.hcl` is git-ignored to prevent committing sensitive infrastructure details.

For CI/CD setup, see the [GitHub Actions Workflow](#-cicd-with-github-actions) section.

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

### 2. Register Required Azure Resource Providers

Azure requires resource providers to be registered before use. Run these commands:

```bash
# Register Container Apps provider
az provider register --namespace Microsoft.App --wait

# Register other required providers
az provider register --namespace Microsoft.ContainerService --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.CognitiveServices --wait

# Verify registration (should show "Registered")
az provider show --namespace Microsoft.App --query "registrationState" -o tsv
```

**Note:** Registration can take a few minutes. The `--wait` flag will block until complete.

### 3. Clone and Configure

```bash
# Navigate to deployment directory
cd deployment

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
vim terraform.tfvars
```

### 4. Required Variables

```hcl
# terraform.tfvars

subscription_id   = "your-subscription-id"
location          = "northeurope"  # or eastus, westus2
db_admin_password = "YourSecurePassword123!"  # pragma: allowlist secret

# LLM Provider - OpenRouter recommended (has free models)
llm_provider       = "openrouter"
openrouter_api_key = "sk-or-v1-..."  # pragma: allowlist secret
openrouter_model   = "google/gemma-3-27b-it:free"

# Budget alerts
budget_alert_emails = ["your-email@example.com"]
```

**Region Notes:**

- Some Azure regions have restrictions for certain services
- `northeurope` is recommended for European users
- If PostgreSQL fails in your region, set `db_location` to a different region

### 5. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy (takes ~5-10 minutes)
terraform apply
```

### 6. Build and Push Images

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

### 7. Update Container Apps

```bash
# Update terraform.tfvars with your images
backend_image  = "bibleappacr123abc.azurecr.io/bible-backend:latest"
frontend_image = "bibleappacr123abc.azurecr.io/bible-frontend:latest"

# Re-apply
terraform apply
```

### 8. Load Bible Data and Generate Embeddings

The database needs to be populated with Bible text and vector embeddings for semantic search.

#### Option A: Load from Local Machine (Recommended for First Setup)

```bash
# Navigate to project root
cd /path/to/getinspiredbythebible

# Get Azure database connection details
cd deployment
DB_HOST=$(terraform output -raw postgresql_fqdn)
DB_PASSWORD="your-db-password"  # pragma: allowlist secret

# Set environment variables for scripts
export DATABASE_URL="postgresql://bibleadmin:${DB_PASSWORD}@${DB_HOST}:5432/bibleapp?sslmode=require"

# For Azure OpenAI embeddings (get from Azure Portal)
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-azure-openai-key"  # pragma: allowlist secret
export AZURE_EMBEDDING_DEPLOYMENT="text-embedding-3-small"

# Install dependencies (if not already)
cd ../scripts
pip install httpx asyncpg sqlalchemy openai

# Step 1: Load Bible translations
python load_bible.py --all  # Loads KJV, Italian, German, etc.

# Step 2: Generate embeddings (takes ~10-15 minutes, costs ~$0.20)
python create_azure_embeddings.py

# Verify data loaded
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM verses;"
# Expected: ~100,000+ verses (31K per translation)
```

#### Option B: Test Locally First, Then Push to Azure

```bash
# 1. Test with local Docker setup
make docker-up
cd scripts
DATABASE_URL="postgresql://bible:bible123@localhost:5432/bibledb" python load_bible.py --all  # pragma: allowlist secret

# 2. Once verified, run against Azure DB (replace PASSWORD with your actual password)
export DATABASE_URL="postgresql://bibleadmin:PASSWORD@your-db.postgres.database.azure.com:5432/bibleapp?sslmode=require"  # pragma: allowlist secret
python load_bible.py --all
python create_azure_embeddings.py
```

#### Available Translations

| Code | Language | Name |
|------|----------|------|
| `kjv` | English | King James Version |
| `web` | English | World English Bible |
| `ita1927` | Italian | Riveduta 1927 |
| `deu1912` | German | Luther 1912 |

```bash
# Load specific translation
python load_bible.py --translation kjv

# Load all translations
python load_bible.py --all

# List available translations
python load_bible.py --list
```

## 🌐 Access Your Application

After deployment, get URLs with:

```bash
terraform output frontend_url
terraform output backend_url
```

## 📁 Project Structure

```
deployment/
├── main.tf                    # Main infrastructure
├── backend.tf                 # Remote state configuration
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── terraform.tfvars.example   # Example configuration
├── backend.hcl.example        # Example backend config
├── scripts/
│   └── setup-tf-backend.sh    # Setup Azure storage for state
├── .gitignore                 # Ignore secrets
└── README.md                  # This file
```

## 🔧 Configuration Options

### Scale-to-Zero (Cost Savings)

```hcl
# Containers scale to 0 when not in use
backend_min_replicas  = 0  # Scale to zero
backend_max_replicas  = 2  # Handle traffic spikesged

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

### Terraform Infrastructure Pipeline

The repository includes a GitHub Actions workflow (`.github/workflows/terraform.yml`) that automates infrastructure management:

| Trigger | Action |
|---------|--------|
| Pull Request | Plan only (shows what would change) |
| Push to main | Plan + Apply (with approval) |
| Manual dispatch | Plan, Apply, or Destroy |

**Required GitHub Secrets:**

| Secret | Description |
|--------|-------------|
| `ARM_CLIENT_ID` | Azure Service Principal Client ID |
| `ARM_CLIENT_SECRET` | Azure Service Principal Client Secret |
| `ARM_SUBSCRIPTION_ID` | Azure Subscription ID |
| `ARM_TENANT_ID` | Azure Tenant ID |
| `TF_STORAGE_ACCOUNT` | Storage account name for Terraform state |
| `TF_VAR_DB_ADMIN_PASSWORD` | Database admin password |
| `TF_VAR_OPENROUTER_API_KEY` | OpenRouter API key |

**Create a Service Principal for GitHub Actions:**

```bash
# Create service principal with Contributor role
az ad sp create-for-rbac \
  --name "github-actions-bible-app" \
  --role Contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID \
  --json-auth

# The output JSON contains all ARM_* values needed for secrets
```

**Environment Protection:**

Create a GitHub environment named `production` with required reviewers for apply/destroy operations.

### Application Deployment Pipeline

Create `.github/workflows/deploy.yml` for container deployments:

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

### Built-in Security Features (Enabled by Default)

The application includes several security features that are enabled by default in production:

| Feature | Variable | Default | Description |
|---------|----------|---------|-------------|
| Rate Limiting | `rate_limit_enabled` | `true` | Limits requests per IP/session |
| Content Filtering | `content_filter_enabled` | `true` | Blocks profanity, spam, URLs |
| Debug Mode | `debug_mode` | `false` | Prevents verbose error messages |
| Message Length | `max_message_length` | `200` | Prevents oversized messages |

### Configuration in Terraform

```hcl
# Security settings (in terraform.tfvars)
debug_mode                     = false  # MUST be false in production
log_level                      = "INFO"
rate_limit_enabled             = true
rate_limit_requests_per_minute = 20
content_filter_enabled         = true
max_message_length             = 200
```

### Additional Best Practices

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

5. **Monitor Security Violations**
   - Check logs for rate limit and content filter violations
   - Review Azure Log Analytics for suspicious patterns

## 📧 Email Notifications (SMTP2GO)

The application can send email notifications for contact form submissions and negative feedback.
This uses [SMTP2GO](https://www.smtp2go.com/)'s HTTP API.

### Setup Steps

1. **Create SMTP2GO Account**
   - Sign up at [smtp2go.com](https://www.smtp2go.com/) (free tier: 1,000 emails/month)
   - Verify your sender domain or email address

2. **Get API Key**
   - Go to Settings → API Keys in SMTP2GO dashboard
   - Create a new API key with "Email sending" permission
   - Copy the key (starts with `api-`)

3. **Configure Environment Variables**

   Add to your `terraform.tfvars`:

   ```hcl
   # Email notifications
   smtp2go_enabled      = true
   smtp2go_api_key      = "api-xxxxxxxxxxxxxxxx"  # pragma: allowlist secret
   smtp2go_sender_email = "noreply@yourdomain.com"
   smtp2go_sender_name  = "Bible Inspiration"
   contact_notification_email = "your-email@example.com"
   ```

   Or set as Container App secrets:

   ```bash
   az containerapp secret set \
     --name bible-app-backend \
     --resource-group bible-app-rg \
     --secrets smtp2go-api-key=api-xxxxxxxxxxxxxxxx

   az containerapp update \
     --name bible-app-backend \
     --resource-group bible-app-rg \
     --set-env-vars \
       SMTP2GO_ENABLED=true \
       SMTP2GO_API_KEY=secretref:smtp2go-api-key \
       SMTP2GO_SENDER_EMAIL=noreply@yourdomain.com \
       CONTACT_NOTIFICATION_EMAIL=your-email@example.com
   ```

### What Gets Notified

| Event | Email Sent To | Content |
|-------|---------------|---------|
| Contact form submission | `CONTACT_NOTIFICATION_EMAIL` | Subject type, message, user's reply email |
| Negative feedback (thumbs down) | `CONTACT_NOTIFICATION_EMAIL` | User comment, original question, AI response |

### Verifying Setup

1. Submit a test contact form on the website
2. Check your notification email inbox
3. Check SMTP2GO dashboard for delivery status

### Troubleshooting Email Issues

```bash
# Check backend logs for email errors
az containerapp logs show \
  --name bible-app-backend \
  --resource-group bible-app-rg \
  --filter "email"

# Common issues:
# - "SMTP2GO API key not configured" → Set SMTP2GO_API_KEY
# - "Email disabled" → Set SMTP2GO_ENABLED=true
# - API returns failure → Check SMTP2GO dashboard for errors
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
