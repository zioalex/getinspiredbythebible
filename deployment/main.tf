# =============================================================================
# Azure Container Apps - Vox Quieta Application
# =============================================================================
# Deploys the voxquieta application on Azure using:
# - Azure Container Apps (serverless containers with scale-to-zero)
# - Azure Database for PostgreSQL Flexible Server (with pgvector)
# - Azure Container Registry (for Docker images)
#
# Estimated cost: ~$25-40/month within $50 budget
# =============================================================================

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

# -----------------------------------------------------------------------------
# Provider Configuration
# -----------------------------------------------------------------------------

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  subscription_id = var.subscription_id
}

# -----------------------------------------------------------------------------
# Random Suffix for Unique Names
# -----------------------------------------------------------------------------

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

locals {
  # Use override suffix if provided, otherwise use random (for importing existing resources)
  resource_suffix = var.resource_suffix != "" ? var.resource_suffix : random_string.suffix.result
  name_prefix     = var.project_name

  # Use db_location if specified, otherwise use main location
  db_location = var.db_location != "" ? var.db_location : var.location

  tags = merge(var.tags, {
    "project"    = "voxquieta"
    "managed_by" = "terraform"
  })

  # ---------------------------------------------------------------------------
  # Backend Environment Variables (sorted alphabetically for consistent ordering)
  # ---------------------------------------------------------------------------
  # Using a map ensures Terraform always processes env vars in the same order,
  # preventing false "changes detected" on every plan due to API response ordering.

  # CORS origins computed value (needed before backend_env_vars)
  cors_origins_value = join(",", compact([
    "https://${local.name_prefix}-frontend.${azurerm_container_app_environment.main.default_domain}",
    var.custom_domain_frontend != "" ? "https://${var.custom_domain_frontend}" : "",
    var.cors_origins
  ]))

  backend_env_vars = merge(
    # Core configuration
    {
      "CONTENT_FILTER_ENABLED" = {
        value = tostring(var.content_filter_enabled)
      }
      "CONTENT_SAFETY_ENABLED" = {
        value = tostring(var.content_safety_enabled)
      }
      "CONTENT_SAFETY_MODE" = {
        value = var.content_safety_mode
      }
      "CORS_ORIGINS" = {
        value = local.cors_origins_value
      }
      "DATABASE_URL" = {
        # BITB-112: urlencode() the password here -- this builds a DSN, and a
        # password containing any of :/?#[]@%& silently repoints or breaks a
        # URL instead of erroring (the app would get a working connection to
        # the wrong host, or none at all). See administrator_password below
        # for why that site does the opposite.
        value = "postgresql://${var.db_admin_username}:${urlencode(var.db_admin_password)}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.db_name}?sslmode=require"
      }
      "DEBUG" = {
        value = tostring(var.debug_mode)
      }
      "ENVIRONMENT" = {
        value = "production"
      }
      "LLM_PROVIDER" = {
        value = var.llm_provider
      }
      "LOG_LEVEL" = {
        value = var.log_level
      }
      "MAX_MESSAGE_LENGTH" = {
        value = tostring(var.max_message_length)
      }
      "RATE_LIMIT_ENABLED" = {
        value = tostring(var.rate_limit_enabled)
      }
      "RATE_LIMIT_REQUESTS_PER_MINUTE" = {
        value = tostring(var.rate_limit_requests_per_minute)
      }
      "RATE_LIMIT_SESSION_MAX_REQUESTS" = {
        value = tostring(var.rate_limit_session_max_requests)
      }
    },

    # Claude provider configuration
    var.llm_provider == "claude" ? {
      "ANTHROPIC_API_KEY" = {
        secret_name = "claude-api-key" # pragma: allowlist secret
      }
    } : {},

    # OpenRouter provider configuration
    var.llm_provider == "openrouter" ? {
      "OPENROUTER_ALLOW_FALLBACKS" = {
        value = tostring(var.openrouter_allow_fallbacks)
      }
      "OPENROUTER_API_KEY" = {
        secret_name = "openrouter-api-key" # pragma: allowlist secret
      }
      "OPENROUTER_BASE_URL" = {
        value = var.openrouter_base_url
      }
      "OPENROUTER_FALLBACK_MODELS" = {
        value = var.openrouter_fallback_models
      }
      "OPENROUTER_MODEL" = {
        value = var.openrouter_model
      }
    } : {},

    # Azure OpenAI embeddings configuration
    var.enable_azure_openai ? {
      "AZURE_EMBEDDING_DEPLOYMENT" = {
        value = var.embedding_model_name
      }
      "AZURE_OPENAI_API_KEY" = {
        secret_name = "azure-openai-key" # pragma: allowlist secret
      }
      "AZURE_OPENAI_ENDPOINT" = {
        value = azurerm_cognitive_account.openai[0].endpoint
      }
      "EMBEDDING_DIMENSIONS" = {
        value = "1536"
      }
      "EMBEDDING_PROVIDER" = {
        value = "azure_openai"
      }
    } : {},

    # Application Insights telemetry
    var.enable_application_insights ? {
      "APPLICATIONINSIGHTS_CONNECTION_STRING" = {
        value = azurerm_application_insights.main[0].connection_string
      }
    } : {},

    # SMTP2GO email notification configuration
    var.smtp2go_enabled ? {
      "CONTACT_NOTIFICATION_EMAIL" = {
        value = var.contact_notification_email
      }
      "SMTP2GO_API_KEY" = {
        secret_name = "smtp2go-api-key" # pragma: allowlist secret
      }
      "SMTP2GO_ENABLED" = {
        value = "true"
      }
      "SMTP2GO_SENDER_EMAIL" = {
        value = var.smtp2go_sender_email
      }
      "SMTP2GO_SENDER_NAME" = {
        value = var.smtp2go_sender_name
      }
    } : {},

    # Cloudflare Turnstile bot protection
    var.turnstile_enabled ? {
      "TURNSTILE_ENABLED" = {
        value = "true"
      }
      "TURNSTILE_SECRET_KEY" = {
        secret_name = "turnstile-secret-key" # pragma: allowlist secret
      }
      "TURNSTILE_SITE_KEY" = {
        value = var.turnstile_site_key
      }
    } : {},

    # Synthetic monitor probe bypass (only when secret is provided)
    var.monitor_probe_secret != "" ? {
      "MONITOR_PROBE_SECRET" = {
        secret_name = "monitor-probe-secret" # pragma: allowlist secret
      }
    } : {},

    # Browser smoke-test bypass (only when secret is provided) — BITB-064
    var.smoke_probe_secret != "" ? {
      "SMOKE_PROBE_SECRET" = {
        secret_name = "smoke-probe-secret" # pragma: allowlist secret
      }
    } : {}
  )

  # ---------------------------------------------------------------------------
  # Frontend Environment Variables
  # ---------------------------------------------------------------------------

  frontend_env_vars = {
    "NEXT_PUBLIC_API_URL" = {
      value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
    }
    "NODE_ENV" = {
      value = "production"
    }
  }
}

# -----------------------------------------------------------------------------
# Resource Group
# -----------------------------------------------------------------------------

resource "azurerm_resource_group" "main" {
  name     = "${local.name_prefix}-rg"
  location = var.location

  tags = local.tags
}

# -----------------------------------------------------------------------------
# Log Analytics Workspace (required for Container Apps)
# -----------------------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name_prefix}-logs-${local.resource_suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.tags
}

# -----------------------------------------------------------------------------
# Application Insights (optional - for monitoring and telemetry)
# -----------------------------------------------------------------------------

resource "azurerm_application_insights" "main" {
  count               = var.enable_application_insights ? 1 : 0
  name                = "${local.name_prefix}-insights"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = local.tags
}

# Standard availability test — pings the backend /health/ready endpoint every
# 5 minutes from multiple Azure locations.  This populates the "Availability"
# tab in Application Insights (which is 0% without an explicit test).
resource "azurerm_application_insights_standard_web_test" "backend_availability" {
  count                   = var.enable_application_insights ? 1 : 0
  name                    = "${local.name_prefix}-availability"
  resource_group_name     = azurerm_resource_group.main.name
  location                = azurerm_resource_group.main.location
  application_insights_id = azurerm_application_insights.main[0].id

  geo_locations = [
    "emea-nl-ams-azr", # West Europe
    "emea-gb-db3-azr", # UK South
    "us-va-ash-azr",   # East US
  ]

  frequency = 300 # every 5 minutes

  request {
    url = "https://${azurerm_container_app.backend.ingress[0].fqdn}/health/ready"
  }

  validation_rules {
    expected_status_code = 200
  }

  tags = local.tags
}

# Browser CORS-preflight availability test (BITB-064). The /health/ready GET
# test above stayed green through the 2026-07-05 _IncludedRouter outage because
# that crash only hit the browser's cross-origin OPTIONS preflight — GET/POST
# returned 200. This test issues that exact preflight (OPTIONS + Origin +
# Access-Control-Request-*) against the instrumented backend and expects a 200,
# so an always-on Azure-native alert fires on a preflight-only failure — not
# just the 5-minute GitHub cross-origin-smoke probe. Complements it as the
# second, independent channel.
resource "azurerm_application_insights_standard_web_test" "backend_preflight" {
  count                   = var.enable_application_insights ? 1 : 0
  name                    = "${local.name_prefix}-preflight"
  resource_group_name     = azurerm_resource_group.main.name
  location                = azurerm_resource_group.main.location
  application_insights_id = azurerm_application_insights.main[0].id

  geo_locations = [
    "emea-nl-ams-azr", # West Europe
    "emea-gb-db3-azr", # UK South
    "us-va-ash-azr",   # East US
  ]

  frequency = 300 # every 5 minutes

  request {
    url       = "https://${azurerm_container_app.backend.ingress[0].fqdn}/api/v1/chat/stream"
    http_verb = "OPTIONS"

    header {
      name  = "Origin"
      value = "https://voxquieta.org"
    }
    header {
      name  = "Access-Control-Request-Method"
      value = "POST"
    }
    header {
      name  = "Access-Control-Request-Headers"
      value = "content-type,x-turnstile-token"
    }
  }

  validation_rules {
    # A healthy CORS layer answers the preflight with 200; the _IncludedRouter
    # crash returned 500 here.
    expected_status_code = 200
  }

  tags = local.tags
}

# -----------------------------------------------------------------------------
# Container Apps Environment
# -----------------------------------------------------------------------------

resource "azurerm_container_app_environment" "main" {
  name                       = "${local.name_prefix}-env"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = local.tags
}

# -----------------------------------------------------------------------------
# Azure Container Registry
# -----------------------------------------------------------------------------

resource "azurerm_container_registry" "main" {
  name                = "${replace(local.name_prefix, "-", "")}acr${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic" # ~$5/month
  admin_enabled       = true

  tags = local.tags
}

# -----------------------------------------------------------------------------
# PostgreSQL Flexible Server with pgvector
# -----------------------------------------------------------------------------

resource "azurerm_postgresql_flexible_server" "main" {
  name                = "${local.name_prefix}-db-${local.resource_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.db_location # Can differ from main location
  version             = "16"
  administrator_login = var.db_admin_username
  # BITB-112: literal value, deliberately NOT urlencode()'d -- this is the
  # server's own credential store, not a URL. It must match the raw password
  # exactly, or authentication fails for the (correctly URL-encoded)
  # DATABASE_URL above the moment the password contains a URL-structural
  # character. The two sites are meant to differ.
  administrator_password = var.db_admin_password

  # Burstable B2s - 2 vCores / 4 GB RAM (~$33/month all-in). Upgraded from B1ms
  # (1 vCore / 2 GB) so the per-translation partial HNSW indexes (migration 007)
  # stay cached and the second vCore absorbs concurrent multilingual search load.
  sku_name = "B_Standard_B2s"

  # Provisioning size for a *new* server only. Once auto_grow_enabled is on, Azure
  # owns this value -- see the lifecycle block, which ignores it for that reason.
  storage_mb                   = 32768 # 32GB minimum
  backup_retention_days        = 7
  geo_redundant_backup_enabled = false
  # BITB-056: auto-grow removes the disk-full write-failure cliff (storage was a fixed
  # 32GB with no growth). Storage only ever grows, so this is a safe, one-way change;
  # the db-storage-high alert (monitoring.tf) backstops a fill faster than growth.
  auto_grow_enabled = true

  # Allow Azure services to connect
  public_network_access_enabled = true

  tags = local.tags

  lifecycle {
    ignore_changes = [
      zone,
      high_availability[0].standby_availability_zone,
      # Azure owns storage_mb once auto_grow_enabled is true, and Azure only ever
      # grows it (doubling: 32GB -> 64GB -> ...). Without this, the first auto-grow
      # makes every subsequent `terraform apply` fail with
      #   'storage_mb' can only be scaled up, expected the new 'storage_mb' value
      #   (32768) to be larger than the previous 'storage_mb' value (65536)
      # because Terraform tries to shrink the disk back to the declared size. That
      # blocked the deploy on 2026-08-18. Ignoring it is the only reconciliation
      # available: the shrink is impossible, so the config can never win.
      storage_mb
    ]
  }
}

# Firewall rule to allow Azure services
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Firewall rule for your IP (optional, for direct access)
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_client" {
  count            = var.client_ip != "" ? 1 : 0
  name             = "AllowClientIP"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = var.client_ip
  end_ip_address   = var.client_ip
}

# Enable pgvector extension
resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  # pg_prewarm lets migration 007 warm the partial HNSW indexes into shared_buffers.
  value = "vector,uuid-ossp,pg_cron,pg_prewarm"
}

# Run pg_cron jobs against the application database (default is `postgres`).
# Used by scripts/migrations/005_schedule_blocked_samples_purge.sql to TTL
# the blocked_message_samples table without depending on app restarts.
resource "azurerm_postgresql_flexible_server_configuration" "cron_database_name" {
  name       = "cron.database_name"
  server_id  = azurerm_postgresql_flexible_server.main.id
  value      = var.db_name
  depends_on = [azurerm_postgresql_flexible_server_configuration.extensions]
}

# -----------------------------------------------------------------------------
# PostgreSQL Performance Tuning
# -----------------------------------------------------------------------------

# Increase maintenance_work_mem to prevent index build spill to disk
# Critical for HNSW index builds (31K verses × 1024 dims × 4 bytes ≈ 127MB)
resource "azurerm_postgresql_flexible_server_configuration" "maintenance_work_mem" {
  name      = "maintenance_work_mem"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "262144" # 256MB (in KB) - enough to build HNSW indexes in memory
}

# Increase shared_buffers for better query caching
# PostgreSQL best practice: 25% of RAM. B2s = 4 GB RAM -> 1 GB.
resource "azurerm_postgresql_flexible_server_configuration" "shared_buffers" {
  name      = "shared_buffers"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "131072" # 1GB (in 8KB pages) = 25% of 4GB
}

# Set effective_cache_size to help query planner estimate available OS cache
# PostgreSQL best practice: 50-75% of total RAM. B2s = 4 GB RAM -> 3 GB.
resource "azurerm_postgresql_flexible_server_configuration" "effective_cache_size" {
  name      = "effective_cache_size"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "393216" # 3GB (in 8KB pages) = 75% of 4GB
}

# Increase work_mem for complex sorts and joins (especially pgvector searches)
resource "azurerm_postgresql_flexible_server_configuration" "work_mem" {
  name      = "work_mem"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "16384" # 16MB (in KB) - higher than default 4MB for vector operations
}

# Enable slow query logging (queries slower than 100ms)
resource "azurerm_postgresql_flexible_server_configuration" "log_min_duration_statement" {
  name      = "log_min_duration_statement"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "100" # Log queries taking >100ms
}

# Enable checkpoint logging for performance analysis
resource "azurerm_postgresql_flexible_server_configuration" "log_checkpoints" {
  name      = "log_checkpoints"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

# Increase max_wal_size to reduce checkpoint frequency
resource "azurerm_postgresql_flexible_server_configuration" "max_wal_size" {
  name      = "max_wal_size"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "2048" # 2GB (in MB) - reduces checkpoint storms
}

# Enable connection logging for monitoring
resource "azurerm_postgresql_flexible_server_configuration" "log_connections" {
  name      = "log_connections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

# Create the application database
resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = var.db_name
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# -----------------------------------------------------------------------------
# Secret Change Trigger
# -----------------------------------------------------------------------------
# The backend container app uses ignore_changes = [secret] to avoid false drift
# from the Azure API never returning secret values.  This terraform_data resource
# watches a SHA256 hash of the OpenRouter API key so that when it actually
# changes, terraform_data is replaced, which in turn triggers a replacement of
# the backend container app via replace_triggered_by.
#
# monitor_probe_secret / smoke_probe_secret are deliberately EXCLUDED (BITB-067
# gap #6): they are provisioned out-of-band by the "Populate probe secrets in
# backend Container App" step in azure-deploy.yml (az containerapp secret set),
# mirroring the BITB-056 Telegram-token pattern, so rotating them no longer
# forces a full app replacement (which previously re-triggered the origin-TLS
# cert-unbind bug, BITB-067 gap #5). The `secret` blocks below still declare
# these as ACA secrets (so the env var `secretRef`s resolve) but their `value`
# is a bootstrap placeholder only ever consumed on a genuine create/replace —
# ignore_changes = [secret] (below) means Terraform never reverts the
# CLI-set live value back to the placeholder.

resource "terraform_data" "backend_secret_trigger" {
  # Hash GH-sourced sensitive values that must force a backend replacement when
  # they change. Do NOT add monitor_probe_secret / smoke_probe_secret here —
  # see the comment above.
  triggers_replace = sha256(join("|", [
    var.openrouter_api_key,
  ]))
}

# -----------------------------------------------------------------------------
# Container App - Backend (FastAPI)
# -----------------------------------------------------------------------------

resource "azurerm_container_app" "backend" {
  name                         = "${local.name_prefix}-backend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    min_replicas = var.backend_min_replicas
    max_replicas = var.backend_max_replicas

    container {
      name   = "backend"
      image  = var.backend_image != "" ? var.backend_image : "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = var.backend_cpu
      memory = var.backend_memory

      # Environment variables from sorted map (prevents false changes due to API ordering)
      dynamic "env" {
        for_each = { for k, v in local.backend_env_vars : k => v }
        content {
          name        = env.key
          value       = lookup(env.value, "value", null)
          secret_name = lookup(env.value, "secret_name", null)
        }
      }

      # Liveness probe - checks if container is alive
      liveness_probe {
        transport = "HTTP"
        path      = "/health/live"
        port      = 8000

        initial_delay           = 10
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 3
      }

      # Readiness probe - checks if container can serve traffic
      readiness_probe {
        transport = "HTTP"
        path      = "/health/ready"
        port      = 8000

        interval_seconds        = 10
        timeout                 = 5
        failure_count_threshold = 3
      }
    }

    # Explicit HTTP scale rule with longer cooldown to avoid aggressive scale-to-zero
    http_scale_rule {
      name                = "http-requests"
      concurrent_requests = 10
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  # Claude API Key secret (if using Claude provider)
  dynamic "secret" {
    for_each = var.llm_provider == "claude" ? [1] : []
    content {
      name  = "claude-api-key"
      value = var.claude_api_key
    }
  }

  # OpenRouter API Key secret (if using OpenRouter provider)
  dynamic "secret" {
    for_each = var.llm_provider == "openrouter" ? [1] : []
    content {
      name  = "openrouter-api-key"
      value = var.openrouter_api_key
    }
  }

  # Azure OpenAI Key secret (if using Azure OpenAI for embeddings)
  dynamic "secret" {
    for_each = var.enable_azure_openai ? [1] : []
    content {
      name  = "azure-openai-key"
      value = azurerm_cognitive_account.openai[0].primary_access_key
    }
  }

  # SMTP2GO API Key secret (if email notifications enabled)
  dynamic "secret" {
    for_each = var.smtp2go_enabled ? [1] : []
    content {
      name  = "smtp2go-api-key"
      value = var.smtp2go_api_key
    }
  }

  # Turnstile secret key (if bot protection enabled)
  dynamic "secret" {
    for_each = var.turnstile_enabled ? [1] : []
    content {
      name  = "turnstile-secret-key"
      value = var.turnstile_secret_key
    }
  }

  # Synthetic monitor probe shared secret (only when set). The `value` here is
  # a bootstrap placeholder, not the real secret (BITB-067 gap #6) — the real
  # value is set post-apply by azure-deploy.yml via `az containerapp secret
  # set` and preserved thereafter by lifecycle.ignore_changes = [secret]
  # below. var.monitor_probe_secret only gates whether this secret exists.
  dynamic "secret" {
    for_each = var.monitor_probe_secret != "" ? [1] : []
    content {
      name  = "monitor-probe-secret"
      value = "set-out-of-band-see-azure-deploy-yml" # pragma: allowlist secret
    }
  }

  # Browser smoke-test secret (only when set) — BITB-064. See the
  # monitor-probe-secret comment above: value is a bootstrap placeholder,
  # real value provisioned out-of-band (BITB-067 gap #6).
  dynamic "secret" {
    for_each = var.smoke_probe_secret != "" ? [1] : []
    content {
      name  = "smoke-probe-secret"
      value = "set-out-of-band-see-azure-deploy-yml" # pragma: allowlist secret
    }
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password" # pragma: allowlist secret
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  lifecycle {
    # The Azure Container Apps API never returns secret values in plain text,
    # so the azurerm provider (v3.x) always reports secrets as "changed" even
    # when the value is identical.  This causes a phantom "2 to change" on
    # every terraform plan/apply with zero actual effect in Azure.
    # ignore_changes = [secret] prevents this false drift.
    # NOTE: to rotate a secret (ACR password, API key, etc.) run:
    #   terraform apply -replace=azurerm_container_app.backend
    ignore_changes = [secret]

    # Automatically replace the backend container app when the OpenRouter
    # API key changes, even though ignore_changes hides secret drift.
    replace_triggered_by = [terraform_data.backend_secret_trigger.id]
  }

  tags = local.tags

  depends_on = [
    azurerm_postgresql_flexible_server_database.app,
    azurerm_postgresql_flexible_server_configuration.extensions
  ]
}

# -----------------------------------------------------------------------------
# Container App - Frontend (Next.js)
# -----------------------------------------------------------------------------

resource "azurerm_container_app" "frontend" {
  name                         = "${local.name_prefix}-frontend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    min_replicas = var.frontend_min_replicas
    max_replicas = var.frontend_max_replicas

    container {
      name   = "frontend"
      image  = var.frontend_image != "" ? var.frontend_image : "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = var.frontend_cpu
      memory = var.frontend_memory

      # Environment variables from sorted map (prevents false changes due to API ordering)
      dynamic "env" {
        for_each = { for k, v in local.frontend_env_vars : k => v }
        content {
          name        = env.key
          value       = lookup(env.value, "value", null)
          secret_name = lookup(env.value, "secret_name", null)
        }
      }
    }

    # Explicit HTTP scale rule with longer cooldown to avoid aggressive scale-to-zero
    http_scale_rule {
      name                = "http-requests"
      concurrent_requests = 10
    }
  }

  ingress {
    external_enabled = true
    target_port      = 3000
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password" # pragma: allowlist secret
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  lifecycle {
    # The Azure Container Apps API never returns secret values in plain text,
    # so the azurerm provider (v3.x) always reports secrets as "changed" even
    # when the value is identical.  This causes a phantom "2 to change" on
    # every terraform plan/apply with zero actual effect in Azure.
    # ignore_changes = [secret] prevents this false drift.
    # NOTE: to rotate a secret (ACR password, API key, etc.) run:
    #   terraform apply -replace=azurerm_container_app.frontend
    ignore_changes = [secret]
  }

  tags = local.tags

  depends_on = [azurerm_container_app.backend]
}

# -----------------------------------------------------------------------------
# Custom Domain Configuration (Optional - for Cloudflare or other DNS)
# -----------------------------------------------------------------------------
# When using Cloudflare proxy, Cloudflare handles SSL termination.
# We use null_resource with local-exec to add the custom domain via Azure CLI.
#
# IMPORTANT: Before running terraform apply with custom domains:
# 1. Add CNAME record in Cloudflare pointing to the frontend/backend FQDN
# 2. Add TXT record for domain verification (see output for verification ID)
#
# See: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_app_custom_domain

# Add frontend custom domain via Azure CLI
resource "null_resource" "frontend_custom_domain" {
  count = var.custom_domain_frontend != "" ? 1 : 0

  triggers = {
    hostname       = var.custom_domain_frontend
    container_app  = azurerm_container_app.frontend.name
    resource_group = azurerm_resource_group.main.name
    cert_hash      = var.cloudflare_origin_cert_hash
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      DOMAIN="${var.custom_domain_frontend}"
      APP="${azurerm_container_app.frontend.name}"
      RG="${azurerm_resource_group.main.name}"
      EXISTING=$(az containerapp show --name "$APP" --resource-group "$RG" \
        --query "properties.configuration.ingress.customDomains[].name" -o tsv 2>/dev/null || true)
      if echo "$EXISTING" | grep -qx "$DOMAIN"; then
        echo "Custom domain $DOMAIN already attached to $APP"
      else
        echo "Adding custom domain $DOMAIN to $APP..."
        az containerapp hostname add --name "$APP" --resource-group "$RG" --hostname "$DOMAIN"
      fi
    EOT
  }

  depends_on = [azurerm_container_app.frontend]
}

# Add backend custom domain via Azure CLI (optional)
resource "null_resource" "backend_custom_domain" {
  count = var.custom_domain_backend != "" ? 1 : 0

  triggers = {
    hostname       = var.custom_domain_backend
    container_app  = azurerm_container_app.backend.name
    resource_group = azurerm_resource_group.main.name
    cert_hash      = var.cloudflare_origin_cert_hash
    # When backend_secret_trigger forces a REPLACEMENT of the backend app
    # (currently: only an OpenRouter API key rotation — BITB-067 gap #6
    # removed probe-secret rotation as a replacement cause), the recreated app
    # loses its imperatively-bound custom domain + certificate — the app
    # *name* above doesn't change, so nothing re-ran and prod served
    # Cloudflare 525 (2026-07-07 incident). terraform_data gets a fresh id on
    # each replacement, so keying on it re-runs this provisioner in the same
    # apply.
    secret_trigger = terraform_data.backend_secret_trigger.id
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      DOMAIN="${var.custom_domain_backend}"
      APP="${azurerm_container_app.backend.name}"
      RG="${azurerm_resource_group.main.name}"
      EXISTING=$(az containerapp show --name "$APP" --resource-group "$RG" \
        --query "properties.configuration.ingress.customDomains[].name" -o tsv 2>/dev/null || true)
      if echo "$EXISTING" | grep -qx "$DOMAIN"; then
        echo "Custom domain $DOMAIN already attached to $APP"
      else
        echo "Adding custom domain $DOMAIN to $APP..."
        az containerapp hostname add --name "$APP" --resource-group "$RG" --hostname "$DOMAIN"
      fi
    EOT
  }

  depends_on = [azurerm_container_app.backend]
}

# -----------------------------------------------------------------------------
# Cloudflare Origin Certificate Configuration (Optional)
# -----------------------------------------------------------------------------
# When using Cloudflare proxy with Full (Strict) SSL mode, you need to install
# a Cloudflare Origin Certificate on your Azure Container App.
#
# Prerequisites:
# 1. Create Cloudflare Origin Certificate in Cloudflare Dashboard:
#    SSL/TLS → Origin Server → Create Certificate
# 2. Save the certificate (.pem) and private key (.key)
# 3. Convert to PFX format:
#    openssl pkcs12 -export -out cert.pfx -inkey origin-key.pem -in origin-cert.pem -passout pass:
# 4. Set cloudflare_origin_cert_frontend or cloudflare_origin_cert_backend to the PFX path

# Upload frontend Cloudflare Origin Certificate
resource "null_resource" "frontend_ssl_cert_upload" {
  count = var.cloudflare_origin_cert_frontend != "" ? 1 : 0

  triggers = {
    cert_file      = var.cloudflare_origin_cert_frontend
    cert_hash      = var.cloudflare_origin_cert_hash
    environment    = azurerm_container_app_environment.main.name
    resource_group = azurerm_resource_group.main.name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      echo "Uploading Cloudflare Origin Certificate for frontend..."
      az containerapp env certificate upload \
        --name ${azurerm_container_app_environment.main.name} \
        --resource-group ${azurerm_resource_group.main.name} \
        --certificate-file ${var.cloudflare_origin_cert_frontend} \
        --password "${var.cloudflare_origin_cert_password}"
    EOT
  }

  depends_on = [azurerm_container_app_environment.main]
}

# Bind frontend certificate to custom domain
resource "null_resource" "frontend_ssl_cert_bind" {
  count = var.custom_domain_frontend != "" && var.cloudflare_origin_cert_frontend != "" ? 1 : 0

  triggers = {
    hostname       = var.custom_domain_frontend
    cert_file      = var.cloudflare_origin_cert_frontend
    cert_hash      = var.cloudflare_origin_cert_hash
    container_app  = azurerm_container_app.frontend.name
    resource_group = azurerm_resource_group.main.name
    environment    = azurerm_container_app_environment.main.name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      DOMAIN="${var.custom_domain_frontend}"
      # Wildcard SAN one level up, e.g. api.voxquieta.org -> *.voxquieta.org.
      # For an apex domain this yields harmless *.tld which won't match any real cert.
      PARENT_WILDCARD="*.$(echo "$DOMAIN" | cut -d. -f2-)"
      echo "Binding SSL certificate to $DOMAIN (also matching $PARENT_WILDCARD)..."

      # Find a cert whose SAN equals $DOMAIN or the parent wildcard, newest first.
      CERT_ID=$(az containerapp env certificate list \
        --name ${azurerm_container_app_environment.main.name} \
        --resource-group ${azurerm_resource_group.main.name} \
        --query "[?contains(properties.subjectAlternativeNames, '$DOMAIN') || contains(properties.subjectAlternativeNames, '$PARENT_WILDCARD')] | sort_by(@, &properties.expirationDate) | reverse(@) | [0].id" \
        -o tsv)

      if [ -z "$CERT_ID" ]; then
        echo "ERROR: No certificate found with SAN covering $DOMAIN"
        echo "Available certificates:"
        az containerapp env certificate list \
          --name ${azurerm_container_app_environment.main.name} \
          --resource-group ${azurerm_resource_group.main.name} \
          --query "[].{name:name, SANs:properties.subjectAlternativeNames, expiry:properties.expirationDate}" \
          -o table
        exit 1
      fi

      echo "Found certificate $CERT_ID for domain $DOMAIN"
      az containerapp hostname bind \
        --name ${azurerm_container_app.frontend.name} \
        --resource-group ${azurerm_resource_group.main.name} \
        --hostname $DOMAIN \
        --certificate "$CERT_ID" \
        --environment ${azurerm_container_app_environment.main.name}
    EOT
  }

  depends_on = [
    null_resource.frontend_custom_domain,
    null_resource.frontend_ssl_cert_upload
  ]
}

# Upload backend Cloudflare Origin Certificate (if different from frontend)
resource "null_resource" "backend_ssl_cert_upload" {
  count = var.cloudflare_origin_cert_backend != "" && var.cloudflare_origin_cert_backend != var.cloudflare_origin_cert_frontend ? 1 : 0

  triggers = {
    cert_file      = var.cloudflare_origin_cert_backend
    cert_hash      = var.cloudflare_origin_cert_hash
    environment    = azurerm_container_app_environment.main.name
    resource_group = azurerm_resource_group.main.name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      echo "Uploading Cloudflare Origin Certificate for backend..."
      az containerapp env certificate upload \
        --name ${azurerm_container_app_environment.main.name} \
        --resource-group ${azurerm_resource_group.main.name} \
        --certificate-file ${var.cloudflare_origin_cert_backend} \
        --password "${var.cloudflare_origin_cert_password}"
    EOT
  }

  depends_on = [azurerm_container_app_environment.main]
}

# Bind backend certificate to custom domain
resource "null_resource" "backend_ssl_cert_bind" {
  count = var.custom_domain_backend != "" && (var.cloudflare_origin_cert_backend != "" || var.cloudflare_origin_cert_frontend != "") ? 1 : 0

  triggers = {
    hostname       = var.custom_domain_backend
    cert_file      = var.cloudflare_origin_cert_backend != "" ? var.cloudflare_origin_cert_backend : var.cloudflare_origin_cert_frontend
    cert_hash      = var.cloudflare_origin_cert_hash
    container_app  = azurerm_container_app.backend.name
    resource_group = azurerm_resource_group.main.name
    environment    = azurerm_container_app_environment.main.name
    # Re-run the cert bind whenever the backend app is replaced by a secret
    # rotation (see backend_custom_domain trigger comment — 525 incident).
    secret_trigger = terraform_data.backend_secret_trigger.id
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      DOMAIN="${var.custom_domain_backend}"
      PARENT_WILDCARD="*.$(echo "$DOMAIN" | cut -d. -f2-)"
      echo "Binding SSL certificate to $DOMAIN (also matching $PARENT_WILDCARD)..."

      # Find a cert whose SAN equals $DOMAIN or the parent wildcard, newest first.
      CERT_ID=$(az containerapp env certificate list \
        --name ${azurerm_container_app_environment.main.name} \
        --resource-group ${azurerm_resource_group.main.name} \
        --query "[?contains(properties.subjectAlternativeNames, '$DOMAIN') || contains(properties.subjectAlternativeNames, '$PARENT_WILDCARD')] | sort_by(@, &properties.expirationDate) | reverse(@) | [0].id" \
        -o tsv)

      if [ -z "$CERT_ID" ]; then
        echo "ERROR: No certificate found with SAN covering $DOMAIN"
        echo "Available certificates:"
        az containerapp env certificate list \
          --name ${azurerm_container_app_environment.main.name} \
          --resource-group ${azurerm_resource_group.main.name} \
          --query "[].{name:name, SANs:properties.subjectAlternativeNames, expiry:properties.expirationDate}" \
          -o table
        exit 1
      fi

      echo "Found certificate $CERT_ID for domain $DOMAIN"
      az containerapp hostname bind \
        --name ${azurerm_container_app.backend.name} \
        --resource-group ${azurerm_resource_group.main.name} \
        --hostname $DOMAIN \
        --certificate "$CERT_ID" \
        --environment ${azurerm_container_app_environment.main.name}
    EOT
  }

  depends_on = [
    null_resource.backend_custom_domain,
    null_resource.frontend_ssl_cert_upload,
    null_resource.backend_ssl_cert_upload
  ]
}

# -----------------------------------------------------------------------------
# Azure OpenAI for Embeddings (Optional but recommended)
# -----------------------------------------------------------------------------

resource "azurerm_cognitive_account" "openai" {
  count = var.enable_azure_openai ? 1 : 0

  name                = "${local.name_prefix}-openai-${local.resource_suffix}"
  location            = var.openai_location # OpenAI may not be available in all regions
  resource_group_name = azurerm_resource_group.main.name
  kind                = "OpenAI"
  sku_name            = "S0"

  tags = local.tags
}

resource "azurerm_cognitive_deployment" "embedding" {
  count = var.enable_azure_openai ? 1 : 0

  name                 = var.embedding_model_name
  cognitive_account_id = azurerm_cognitive_account.openai[0].id

  model {
    format  = "OpenAI"
    name    = var.embedding_model_name
    version = var.embedding_model_version
  }

  scale {
    type     = "Standard"
    capacity = var.embedding_capacity # Tokens per minute (in thousands)
  }
}

# -----------------------------------------------------------------------------
# Budget Alert (Optional but recommended)
# -----------------------------------------------------------------------------

resource "azurerm_consumption_budget_resource_group" "main" {
  count             = var.create_budget_alert && length(var.budget_alert_emails) > 0 ? 1 : 0
  name              = "${local.name_prefix}-budget"
  resource_group_id = azurerm_resource_group.main.id

  amount     = var.monthly_budget
  time_grain = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
    end_date   = "2030-12-31T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_emails = var.budget_alert_emails
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"

    contact_emails = var.budget_alert_emails
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

# -----------------------------------------------------------------------------
# Azure Monitor Workbook — Performance Dashboard (optional)
# -----------------------------------------------------------------------------
# Deploys a visual performance dashboard to Azure Monitor Workbooks.
# Only created when Application Insights is enabled.
# Access via: Azure Portal → Application Insights → Workbooks

resource "azurerm_application_insights_workbook" "performance_dashboard" {
  count = var.enable_application_insights ? 1 : 0

  # Fixed UUID so the workbook is stable across re-applies
  name                = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  display_name        = "${local.name_prefix} - Performance Dashboard"

  # CRITICAL: scope the workbook to the Application Insights resource.
  # Without source_id the workbook is created under "azure monitor" scope,
  # which means every KQL query panel shows "No data" because the workbook
  # has no resource context and cannot resolve the correct Log Analytics
  # workspace. Setting this to the Application Insights resource ID causes
  # the portal to pin all panels to bible-app-insights automatically.
  source_id = lower(azurerm_application_insights.main[0].id)

  data_json = file("${path.module}/azure-monitor/workbook-performance-dashboard.json")

  tags = local.tags
}
