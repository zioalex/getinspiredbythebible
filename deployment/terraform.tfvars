# =============================================================================
# Terraform Variables for Azure Deployment
# =============================================================================
# This file contains NON-CONFIDENTIAL configuration values.
# Secrets are stored in terraform.tfvars.secrets (gitignored) or GitHub Secrets.
# =============================================================================

# -----------------------------------------------------------------------------
# Azure Configuration
# -----------------------------------------------------------------------------

# Your Azure Subscription ID
subscription_id = "f5bc5a63-92f8-4ab6-ad94-84673eeebb56"

# Fixed suffix used to import old resources
resource_suffix = "mb0172"

# Azure region - choose one close to your users
location = "northeurope"

# Project name (used for all resource names)
project_name = "bible-app"

# Additional tags
tags = {
  "environment" = "production"
  "owner"       = "Alessandro S."
}

# -----------------------------------------------------------------------------
# PostgreSQL Configuration
# -----------------------------------------------------------------------------

# Database admin username
# Username restrictions: can't be admin, administrator, root, etc.
db_admin_username = "bibleadmin"

# Database name
db_name = "bibleapp"

# Your IP for direct database access (optional)
client_ip = ""

# -----------------------------------------------------------------------------
# Container Images
# -----------------------------------------------------------------------------

backend_image  = "bibleappacrmb0172.azurecr.io/bible-backend:latest"
frontend_image = "bibleappacrmb0172.azurecr.io/bible-frontend:latest"

# -----------------------------------------------------------------------------
# Container Resources (Optimized for $50 budget)
# -----------------------------------------------------------------------------

# Backend (FastAPI)
backend_cpu          = 0.5
backend_memory       = "1Gi"
backend_min_replicas = 0
backend_max_replicas = 2

# Frontend (Next.js)
frontend_cpu          = 0.25
frontend_memory       = "0.5Gi"
frontend_min_replicas = 0
frontend_max_replicas = 2

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------

llm_provider = "openrouter"

# OpenRouter model (API key is in secrets file)
openrouter_model = "meta-llama/llama-3.3-70b-instruct:free"

# OpenRouter fallback configuration
openrouter_fallback_models = "meta-llama/llama-3.3-70b-instruct"
openrouter_allow_fallbacks = true

# -----------------------------------------------------------------------------
# Security & Rate Limiting
# -----------------------------------------------------------------------------

debug_mode = false
log_level  = "INFO"

rate_limit_enabled             = true
rate_limit_requests_per_minute = 10

content_filter_enabled = true
max_message_length     = 200

# -----------------------------------------------------------------------------
# Azure OpenAI for Embeddings
# -----------------------------------------------------------------------------

enable_azure_openai     = true
openai_location         = "eastus"
embedding_model_name    = "text-embedding-3-small"
embedding_model_version = "1"
embedding_capacity      = 120

# -----------------------------------------------------------------------------
# Application Insights (Monitoring)
# -----------------------------------------------------------------------------

enable_application_insights = true

# -----------------------------------------------------------------------------
# Budget Alerts
# -----------------------------------------------------------------------------

create_budget_alert = true
monthly_budget      = 50
budget_alert_emails = ["zioalex@gmail.com"]

# -----------------------------------------------------------------------------
# Custom Domain
# -----------------------------------------------------------------------------

custom_domain_frontend = "getinspiredbythebible.ai4you.sh"

# email settings
smtp2go_enabled      = true
smtp2go_sender_email = "noreply@getinspiredbythebible.ai4you.sh"
smtp2go_sender_name  = "Bible Inspiration"
contact_notification_email = "getinspiredbythebible@ai4you.sh"# SMTP2GO config
