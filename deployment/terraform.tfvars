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
backend_min_replicas = 1
backend_max_replicas = 2

# Frontend (Next.js)
frontend_cpu          = 0.25
frontend_memory       = "0.5Gi"
frontend_min_replicas = 1
frontend_max_replicas = 2

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------

llm_provider = "openrouter"

# OpenRouter model (API key is in secrets file)
openrouter_model = "meta-llama/llama-3.3-70b-instruct"

# OpenRouter fallback configuration
openrouter_fallback_models = "google/gemma-4-31b-it"
openrouter_allow_fallbacks = true

# -----------------------------------------------------------------------------
# Security & Rate Limiting
# -----------------------------------------------------------------------------

debug_mode = false
log_level  = "INFO"

rate_limit_enabled             = true
rate_limit_requests_per_minute = 10

content_filter_enabled = true
max_message_length     = 500

# -----------------------------------------------------------------------------
# Follow-Up Suggestions Rollout (BITB-080) — WEB ONLY
# -----------------------------------------------------------------------------
# Latency eval returned latency-GO (PR #1214). The backend flag makes the API
# emit `follow_ups` on chat completions for ALL clients; each client gates its
# own rendering:
#   - web:  NEXT_PUBLIC_FOLLOW_UPS_ENABLED is BAKED into the frontend image at
#           build time — azure-deploy.yml reads web_follow_ups_enabled from
#           this file and passes it as a docker build-arg (frontend/Dockerfile).
#   - Android: stays dark — its gate is compile-time (PR #1217), default off.
# Code defaults stay false (variables.tf / api/config.py / featureFlags.ts);
# only this production tfvars turns them on (BITB-187 FR5).
# Rollback: flip either flag to false and redeploy; the web flag additionally
# needs a frontend image rebuild (it is baked, not runtime).

chat_follow_ups_enabled = true
web_follow_ups_enabled  = true

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
# BITB-150: measured average spend Jul-Sep 2026 was ~93 CHF/mo (2 vCPU B2s,
# 64 GB storage, 32 alert rules, always-on container apps). The old budget of
# 50 made the 80% alert fire continuously. Set to the measured run rate; the
# accepted optimization levers (BITB-223…234) bring it down from here.

create_budget_alert = true
monthly_budget      = 100
# budget_alert_emails is sourced from repo secret TF_VAR_BUDGET_ALERT_EMAILS
# (JSON array, e.g. '["alerts@example.com"]'). Defaults to [] if unset.

# -----------------------------------------------------------------------------
# Custom Domain
# -----------------------------------------------------------------------------

custom_domain_frontend = "voxquieta.org"
custom_domain_backend  = "api.voxquieta.org"

# email settings
smtp2go_enabled            = true
smtp2go_sender_email       = "noreply@voxquieta.org"
smtp2go_sender_name        = "Vox Quieta"
contact_notification_email = "support@voxquieta.org"

# -----------------------------------------------------------------------------
# Cloudflare Turnstile (Bot Protection)
# -----------------------------------------------------------------------------

turnstile_enabled  = true
turnstile_site_key = "0x4AAAAAACaR4GHzrw8fgN5O"
