<!-- markdownlint-disable MD040 -->
# Azure Terraform Module - Bible Chat Application

Deploy the **Vox Quieta** application on Azure using Container Apps with scale-to-zero capability.

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

The configuration is split between two files:

- **`terraform.tfvars`** - Non-sensitive configuration (committed to git)
- **`terraform.tfvars.secrets`** - Sensitive credentials (gitignored, local only)

```bash
# Navigate to deployment directory
cd deployment

# The terraform.tfvars file is already committed with default values
# Review and update non-sensitive values as needed
vim terraform.tfvars

# Copy secrets template and fill in your credentials
cp terraform.tfvars.secrets.example terraform.tfvars.secrets
vim terraform.tfvars.secrets
```

### 4. Configuration Files

**`terraform.tfvars`** (committed - non-sensitive values):

```hcl
subscription_id   = "your-subscription-id"
location          = "northeurope"  # or eastus, westus2
resource_suffix   = "mb0172"

# LLM Provider - OpenRouter recommended (has free models)
llm_provider     = "openrouter"
openrouter_model = "meta-llama/llama-3.3-70b-instruct:free"

# Budget alerts
budget_alert_emails = ["your-email@example.com"]
```

**`terraform.tfvars.secrets`** (gitignored - sensitive values):

```hcl
db_admin_password  = "YourSecurePassword123!"  # pragma: allowlist secret
openrouter_api_key = "sk-or-v1-..."            # pragma: allowlist secret
# claude_api_key   = "sk-ant-..."              # pragma: allowlist secret (if using Claude)
```

**Region Notes:**

- Some Azure regions have restrictions for certain services
- `northeurope` is recommended for European users
- If PostgreSQL fails in your region, set `db_location` to a different region

### 5. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes (uses both tfvars files)
terraform plan -var-file="terraform.tfvars" -var-file="terraform.tfvars.secrets"

# Deploy (takes ~5-10 minutes)
terraform apply -var-file="terraform.tfvars" -var-file="terraform.tfvars.secrets"
```

> **Note:** Both var-files must be specified. The secrets file overrides/supplements the main config.

### 6. Build and Push Images

#### Option A: Using Docker Compose with .env.production (Recommended)

The `.env.production` file contains all required variables including `ACR_NAME` and `NEXT_PUBLIC_API_URL`.

```bash
# From the project root (not deployment/)
cd /path/to/getinspiredbythebible

# Login to ACR (source variables from .env.production)
source .env.production
az acr login --name $ACR_NAME

# Build and push using --env-file flag (IMPORTANT: required for build args)
docker compose --env-file .env.production -f docker-compose.prod.yml build --push

# Or build only (without push)
docker compose --env-file .env.production -f docker-compose.prod.yml build

# Push separately
docker compose --env-file .env.production -f docker-compose.prod.yml push
```

**Important:** The `--env-file .env.production` flag is required for docker compose to read
the `NEXT_PUBLIC_API_URL` build argument correctly.

#### Option B: Using Make (Simplified)

```bash
# Build and push all images
make docker-build-prod

# Or build only frontend/backend
make docker-build-prod-frontend
make docker-build-prod-backend
```

#### Option C: Manual Docker Build

```bash
# Source variables
source .env.production

# Login to ACR
az acr login --name $ACR_NAME

# Build backend image
docker build -t ${ACR_NAME}.azurecr.io/bible-backend:latest ./api

# Build frontend image with API URL
docker build -t ${ACR_NAME}.azurecr.io/bible-frontend:latest \
  --target production \
  --build-arg NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
  ./frontend

# Push images to ACR
docker push ${ACR_NAME}.azurecr.io/bible-backend:latest
docker push ${ACR_NAME}.azurecr.io/bible-frontend:latest
```

#### Verify Image Configuration

After building, verify the correct API URL is baked into the frontend image:

```bash
# Should return NO output (localhost:8000 should NOT be in the image)
docker run --rm ${ACR_NAME}.azurecr.io/bible-frontend:latest \
  sh -c "grep -r 'localhost:8000' .next/ 2>/dev/null | head -3"

# Should return output showing the correct URL
docker run --rm ${ACR_NAME}.azurecr.io/bible-frontend:latest \
  sh -c "grep -r '${NEXT_PUBLIC_API_URL}' .next/ 2>/dev/null | head -3"
```

#### Expected Image Tags

After building, your images should be tagged as:

```
bibleappacrmb0172.azurecr.io/bible-backend:latest
bibleappacrmb0172.azurecr.io/bible-frontend:latest
```

Verify images in ACR:

```bash
az acr repository list --name $ACR_NAME -o table
az acr repository show-tags --name $ACR_NAME --repository bible-backend -o table
az acr repository show-tags --name $ACR_NAME --repository bible-frontend -o table
```

### 7. Update Container Apps

```bash
# Update terraform.tfvars with your images
backend_image  = "bibleappacrmb0172.azurecr.io/bible-backend:latest"
frontend_image = "bibleappacrmb0172.azurecr.io/bible-frontend:latest"

# Re-apply
terraform apply
```

Or update directly via Azure CLI (faster for iterations):

```bash
az containerapp update \
  --name bible-app-backend \
  --resource-group bible-app-rg \
  --image bibleappacrmb0172.azurecr.io/bible-backend:latest

az containerapp update \
  --name bible-app-frontend \
  --resource-group bible-app-rg \
  --image bibleappacrmb0172.azurecr.io/bible-frontend:latest
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

## 🔒 Custom Domain with Cloudflare SSL (Optional)

When using Cloudflare as a reverse proxy, you need to configure SSL properly to avoid 525 errors.

### Understanding the SSL Flow

```
User Browser → Cloudflare Edge → Azure Container App
     |              |                    |
     |   HTTPS      |      HTTPS         |
     |   Cloudflare |      Cloudflare    |
     |   SSL Cert   |      Origin Cert   |
```

Azure's default certificate is for `*.azurecontainerapps.io`, not your custom domain.
Cloudflare Origin Certificates solve this by providing a certificate trusted by Cloudflare.

### Step 1: Create Cloudflare Origin Certificate

1. Go to **Cloudflare Dashboard** → Your domain → **SSL/TLS** → **Origin Server**
2. Click **Create Certificate**
3. Select:
   - Private key type: **RSA (2048)**
   - Hostnames: `yourdomain.com`, `*.yourdomain.com`
   - Certificate validity: **15 years** (recommended)
4. Click **Create**
5. Save both files:
   - Certificate → `origin-cert.pem`
   - Private Key → `origin-key.pem`

### Step 2: Convert to PFX Format

Azure Container Apps requires PFX format:

```bash
# Without password (simpler)
openssl pkcs12 -export -out cloudflare-origin.pfx \
  -inkey origin-key.pem \
  -in origin-cert.pem \
  -passout pass:

# Or with password
openssl pkcs12 -export -out cloudflare-origin.pfx \
  -inkey origin-key.pem \
  -in origin-cert.pem \
  -passout pass:yourpassword
```

### Step 3: Configure Terraform

Add to your `terraform.tfvars`:

```hcl
# Custom domain configuration
custom_domain_frontend = "getinspiredbythebible.ai4you.sh"

# Cloudflare Origin Certificate (path to PFX file)
cloudflare_origin_cert_frontend = "./cloudflare-origin.pfx"
cloudflare_origin_cert_password = ""  # Empty if no password
```

Then apply:

```bash
terraform apply
```

### Step 4: Set Cloudflare SSL Mode

In **Cloudflare Dashboard** → **SSL/TLS** → **Overview**:

- Select **Full (strict)**

This ensures encrypted traffic between Cloudflare and your origin with certificate validation.

### Manual Setup (Without Terraform)

If you prefer to set up manually or need to troubleshoot:

```bash
# 1. Upload certificate to Container App Environment
az containerapp env certificate upload \
  --name bible-app-env \
  --resource-group bible-app-rg \
  --certificate-file cloudflare-origin.pfx \
  --password ""

# 2. List certificates to get the ID
az containerapp env certificate list \
  --name bible-app-env \
  --resource-group bible-app-rg \
  --query "[].{name:name, id:id}" -o table

# 3. Add hostname (if not already added)
az containerapp hostname add \
  --name bible-app-frontend \
  --resource-group bible-app-rg \
  --hostname getinspiredbythebible.ai4you.sh

# 4. Bind certificate to hostname
az containerapp hostname bind \
  --name bible-app-frontend \
  --resource-group bible-app-rg \
  --hostname getinspiredbythebible.ai4you.sh \
  --certificate <certificate-name-or-id> \
  --environment bible-app-env

# 5. Verify
curl -I https://getinspiredbythebible.ai4you.sh
```

### Troubleshooting SSL Issues

| Error | Cause | Solution |
|-------|-------|----------|
| 525 SSL Handshake Failed | Certificate mismatch | Install Cloudflare Origin Certificate |
| 526 Invalid SSL Certificate | Origin cert not trusted | Use "Full" mode (not strict) or fix cert |
| 521 Web Server Down | Container not running | Check container app status |

```bash
# Check if certificate is bound
az containerapp hostname list \
  --name bible-app-frontend \
  --resource-group bible-app-rg

# Check container logs
az containerapp logs show \
  --name bible-app-frontend \
  --resource-group bible-app-rg \
  --follow
```

## 📁 Project Structure

```
deployment/
├── main.tf                        # Main infrastructure
├── backend.tf                     # Remote state configuration
├── variables.tf                   # Input variables
├── outputs.tf                     # Output values
├── terraform.tfvars               # Non-sensitive config (COMMITTED)
├── terraform.tfvars.secrets       # Secrets (GITIGNORED, local only)
├── terraform.tfvars.secrets.example # Template for secrets
├── terraform.tfvars.example       # Full example for reference
├── backend.hcl.example            # Example backend config
├── scripts/
│   ├── setup-tf-backend.sh        # Setup Azure storage for state
│   └── setup-github-spn.sh        # Setup Service Principal for CI/CD
├── .gitignore                     # Ignore secrets
└── README.md                      # This file
```

**Configuration Split:**

| File | Contains | Git Status |
|------|----------|------------|
| `terraform.tfvars` | Non-sensitive config (regions, sizes, models) | Committed |
| `terraform.tfvars.secrets` | Passwords, API keys | Gitignored |
| GitHub Secrets | CI/CD secrets only | N/A |

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

The repository includes a GitHub Actions workflow (`.github/workflows/azure-deploy.yml`) that automates infrastructure management:

| Trigger | Action |
|---------|--------|
| Pull Request | Plan only (shows what would change) |
| Push to main | Plan + Apply (with approval) |
| Manual dispatch | Plan, Apply, or Destroy |

**Configuration in CI/CD:**

The workflow uses a split configuration approach:

- **`terraform.tfvars`** (committed) - Non-sensitive config is read from the repo
- **GitHub Secrets** - Only actual secrets are stored as repository secrets

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
| `TF_VAR_CLAUDE_API_KEY` | Claude API key (optional, if using Claude) |
| `CLOUDFLARE_ORIGIN_CERT_B64` | Base64-encoded Cloudflare Origin Certificate (optional) |
| `TF_VAR_CLOUDFLARE_ORIGIN_CERT_PASSWORD` | Certificate password (optional) |

**Create a Service Principal for GitHub Actions:**

Use the automated setup script to create the SPN for your environment:

```bash
cd deployment/scripts

# For development environment
./setup-github-spn.sh -e dev

# For non-production/staging
./setup-github-spn.sh -e np

# For production (recommended: also set secrets automatically)
./setup-github-spn.sh -e prod -r ${GITHUB_REPO} -g

# With specific subscription
./setup-github-spn.sh -e prod -s "${ARM_SUBSCRIPTION_ID}" -r ${GITHUB_REPO}
```

The script will:

- Create a service principal named `github-actions-bible-app-{env}`
- Assign the Contributor role to your subscription
- Output the secrets you need to add to GitHub
- Optionally set GitHub secrets directly (requires `gh` CLI)

**Environment Protection:**

Create a GitHub environment named `production` with required reviewers for apply/destroy operations:

1. Go to your repo → Settings → Environments
2. Create environment: `production`
3. Add required reviewers (people who must approve deployments)
4. Optionally restrict deployments to the `main` branch only

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
   smtp2go_sender_name  = "Vox Quieta"
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

## Cloudflare Manual Configuration Checklist

Some Cloudflare settings cannot be managed by Terraform and must be
configured manually in the Cloudflare Dashboard. After deploying a new
domain or changing certificates, verify all of these:

### Turnstile Hostname Allow-List

The Cloudflare Turnstile widget will silently fail if the hostname it
runs on is not in the allow-list. When adding a new domain:

1. Go to **Cloudflare Dashboard** -> **Turnstile** -> select your widget
2. Under **Hostname Management**, add every domain the frontend runs on (e.g. `voxquieta.org`, `www.voxquieta.org`)
3. The Turnstile site key in `terraform.tfvars` (`turnstile_site_key`) must match the widget

**Symptom if missing:** Backend logs show "Missing Turnstile token"
for all requests. Frontend silently falls back to sending requests
without a token.

### SSL/TLS Mode

1. Go to **SSL/TLS** -> **Overview**
2. Set mode to **Full (Strict)** when using Cloudflare Origin Certificates
3. "Full (Strict)" validates the origin cert is trusted by Cloudflare; "Full" skips validation

**Symptom if wrong:** Error 526 (Invalid SSL Certificate) when set to "Full (Strict)" without a valid origin cert installed.

### Origin Certificate Creation

When creating a new Cloudflare Origin Certificate:

1. Go to **SSL/TLS** -> **Origin Server** -> **Create Certificate**
2. Select RSA (2048), add hostnames: `yourdomain.com`, `*.yourdomain.com`
3. Set validity to 15 years
4. Save cert as `origin-cert.pem` and key as `origin-key.pem`
5. Convert to PFX:
   `openssl pkcs12 -export -out cloudflare-origin.pfx -inkey origin-key.pem -in origin-cert.pem -passout pass:`
6. Base64-encode for CI: `base64 -w 0 cloudflare-origin.pfx` and store as `CLOUDFLARE_ORIGIN_CERT_B64` GitHub secret

**Important:** A wildcard cert (`*.voxquieta.org`) does NOT cover
the apex domain (`voxquieta.org`). Ensure both are listed as
hostnames when creating the cert.

### DNS Records

For each custom domain, create:

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `@` (or subdomain) | `<app>.agreeablesea-6ee07535.northeurope.azurecontainerapps.io` | Proxied |
| TXT | `asuid.<domain>` | `<domain_verification_id>` (from `terraform output`) | DNS only |

### Domain Verification ID

Get the verification ID needed for the TXT record:

```bash
terraform output domain_verification_id
```

## Rollback: Emergency Cert Rebind

If a deployment breaks custom domain HTTPS (e.g. Error 526), use
these commands to manually fix without waiting for a full CI/CD cycle:

```bash
# Variables — adjust for your environment
ENV_NAME="bible-app-env"
RG="bible-app-rg"
FRONTEND_APP="bible-app-frontend"
BACKEND_APP="bible-app-backend"

# 1. Upload the certificate (if not already present)
az containerapp env certificate upload \
  --name $ENV_NAME \
  --resource-group $RG \
  --certificate-file cloudflare-origin.pfx \
  --password ""

# 2. Find the correct certificate by SAN
az containerapp env certificate list \
  --name $ENV_NAME \
  --resource-group $RG \
  --query "[].{name:name, SANs:properties.subjectAlternativeNames, expiry:properties.expirationDate}" \
  -o table

# 3. Get cert ID for voxquieta.org
CERT_ID=$(az containerapp env certificate list \
  --name $ENV_NAME \
  --resource-group $RG \
  --query "[?properties.subjectAlternativeNames[?contains(@, 'voxquieta.org')]] | [0].id" \
  -o tsv)
echo "Using cert: $CERT_ID"

# 4. Bind to frontend
az containerapp hostname bind \
  --name $FRONTEND_APP \
  --resource-group $RG \
  --hostname voxquieta.org \
  --certificate "$CERT_ID" \
  --environment $ENV_NAME

# 5. Bind to backend
az containerapp hostname bind \
  --name $BACKEND_APP \
  --resource-group $RG \
  --hostname api.voxquieta.org \
  --certificate "$CERT_ID" \
  --environment $ENV_NAME

# 6. Verify through Cloudflare edge
curl -sI https://voxquieta.org/health | grep -E 'HTTP|cf-ray'
curl -sI https://api.voxquieta.org/health | grep -E 'HTTP|cf-ray'
```

## 📝 License

MIT License - see repository root for details.
