# =============================================================================
# Azure Container Apps - Bible Chat Application
# =============================================================================
# Deploys the getinspiredbythebible application on Azure using:
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
  resource_suffix = random_string.suffix.result
  name_prefix     = var.project_name

  tags = merge(var.tags, {
    "project"    = "getinspiredbythebible"
    "managed_by" = "terraform"
  })
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
  name                   = "${local.name_prefix}-db-${local.resource_suffix}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = var.db_admin_username
  administrator_password = var.db_admin_password

  # Burstable B1ms - cheapest option (~$13-16/month)
  sku_name = "B_Standard_B1ms"

  storage_mb                   = 32768 # 32GB minimum
  backup_retention_days        = 7
  geo_redundant_backup_enabled = false
  auto_grow_enabled            = false

  # Allow Azure services to connect
  public_network_access_enabled = true

  tags = local.tags

  lifecycle {
    ignore_changes = [
      zone,
      high_availability[0].standby_availability_zone
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
  value     = "vector,uuid-ossp"
}

# Create the application database
resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = var.db_name
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
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

      env {
        name  = "DATABASE_URL"
        value = "postgresql://${var.db_admin_username}:${var.db_admin_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.db_name}?sslmode=require"
      }

      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }

      # Claude API Key (if using Claude provider)
      dynamic "env" {
        for_each = var.llm_provider == "claude" ? [1] : []
        content {
          name        = "ANTHROPIC_API_KEY"
          secret_name = "claude-api-key"  # pragma: allowlist secret
        }
      }

      # OpenRouter configuration (if using OpenRouter provider)
      dynamic "env" {
        for_each = var.llm_provider == "openrouter" ? [1] : []
        content {
          name        = "OPENROUTER_API_KEY"
          secret_name = "openrouter-api-key"  # pragma: allowlist secret
        }
      }

      dynamic "env" {
        for_each = var.llm_provider == "openrouter" ? [1] : []
        content {
          name  = "OPENROUTER_MODEL"
          value = var.openrouter_model
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }

      # Azure OpenAI Embeddings (if enabled)
      dynamic "env" {
        for_each = var.enable_azure_openai ? [1] : []
        content {
          name  = "EMBEDDING_PROVIDER"
          value = "azure_openai"
        }
      }

      dynamic "env" {
        for_each = var.enable_azure_openai ? [1] : []
        content {
          name  = "EMBEDDING_DIMENSIONS"
          value = "1536"
        }
      }

      dynamic "env" {
        for_each = var.enable_azure_openai ? [1] : []
        content {
          name  = "AZURE_OPENAI_ENDPOINT"
          value = azurerm_cognitive_account.openai[0].endpoint
        }
      }

      dynamic "env" {
        for_each = var.enable_azure_openai ? [1] : []
        content {
          name        = "AZURE_OPENAI_API_KEY"
          secret_name = "azure-openai-key"  # pragma: allowlist secret
        }
      }

      dynamic "env" {
        for_each = var.enable_azure_openai ? [1] : []
        content {
          name  = "AZURE_EMBEDDING_DEPLOYMENT"
          value = var.embedding_model_name
        }
      }

      # Liveness probe
      liveness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000

        initial_delay    = 10
        interval_seconds = 30
        timeout          = 5
        failure_count_threshold = 3
      }

      # Readiness probe
      readiness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000

        interval_seconds = 10
        timeout          = 5
        failure_count_threshold = 3
      }
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

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"  # pragma: allowlist secret
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
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

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }
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
    password_secret_name = "acr-password"  # pragma: allowlist secret
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  tags = local.tags

  depends_on = [azurerm_container_app.backend]
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

  sku {
    name     = "Standard"
    capacity = var.embedding_capacity # Tokens per minute (in thousands)
  }
}

# -----------------------------------------------------------------------------
# Budget Alert (Optional but recommended)
# -----------------------------------------------------------------------------

resource "azurerm_consumption_budget_resource_group" "main" {
  count             = var.create_budget_alert ? 1 : 0
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
