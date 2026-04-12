# =============================================================================
# Variables for Azure Bible App Deployment
# =============================================================================

# -----------------------------------------------------------------------------
# Azure Configuration
# -----------------------------------------------------------------------------

variable "subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "northeurope" # Changed from westeurope due to availability
}

variable "db_location" {
  description = "Azure region for PostgreSQL (may differ due to availability restrictions)"
  type        = string
  default     = "" # Empty means use same as 'location'
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "bible-app"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "resource_suffix" {
  description = "Override the random resource suffix (useful when importing existing resources)"
  type        = string
  default     = ""

  validation {
    condition     = var.resource_suffix == "" || can(regex("^[a-z0-9]{6}$", var.resource_suffix))
    error_message = "Resource suffix must be exactly 6 lowercase alphanumeric characters."
  }
}

# -----------------------------------------------------------------------------
# PostgreSQL Configuration
# -----------------------------------------------------------------------------

variable "db_admin_username" {
  description = "PostgreSQL administrator username"
  type        = string
  default     = "bibleadmin"

  validation {
    condition     = !contains(["admin", "administrator", "root", "azure_superuser", "azure_pg_admin"], var.db_admin_username)
    error_message = "Username cannot be a reserved PostgreSQL name."
  }
}

variable "db_admin_password" {
  description = "PostgreSQL administrator password (min 8 chars, must include uppercase, lowercase, number)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_admin_password) >= 8
    error_message = "Password must be at least 8 characters long."
  }
}

variable "db_name" {
  description = "Name of the application database"
  type        = string
  default     = "bibleapp"
}

variable "client_ip" {
  description = "Your IP address for direct database access (optional, leave empty to skip)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Container Apps - Backend Configuration
# -----------------------------------------------------------------------------

variable "backend_image" {
  description = "Docker image for backend (leave empty for placeholder)"
  type        = string
  default     = ""
}

variable "backend_cpu" {
  description = "CPU cores for backend container"
  type        = number
  default     = 0.5

  validation {
    condition     = contains([0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0], var.backend_cpu)
    error_message = "CPU must be one of: 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0"
  }
}

variable "backend_memory" {
  description = "Memory for backend container (format: 0.5Gi, 1Gi, etc.)"
  type        = string
  default     = "1Gi"
}

variable "backend_min_replicas" {
  description = "Minimum replicas for backend (0 enables scale-to-zero)"
  type        = number
  default     = 0
}

variable "backend_max_replicas" {
  description = "Maximum replicas for backend"
  type        = number
  default     = 2
}

variable "cors_origins" {
  description = "Additional CORS origins (comma-separated), e.g., 'https://example.com,https://app.example.com'"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Container Apps - Frontend Configuration
# -----------------------------------------------------------------------------

variable "frontend_image" {
  description = "Docker image for frontend (leave empty for placeholder)"
  type        = string
  default     = ""
}

variable "frontend_cpu" {
  description = "CPU cores for frontend container"
  type        = number
  default     = 0.25
}

variable "frontend_memory" {
  description = "Memory for frontend container"
  type        = string
  default     = "0.5Gi"
}

variable "frontend_min_replicas" {
  description = "Minimum replicas for frontend (0 enables scale-to-zero)"
  type        = number
  default     = 0
}

variable "frontend_max_replicas" {
  description = "Maximum replicas for frontend"
  type        = number
  default     = 2
}

# -----------------------------------------------------------------------------
# Custom Domain Configuration
# -----------------------------------------------------------------------------

variable "custom_domain_frontend" {
  description = "Custom domain for frontend (e.g., 'voxquieta.org'). Leave empty to skip."
  type        = string
  default     = ""
}

variable "custom_domain_backend" {
  description = "Custom domain for backend API (e.g., 'api.voxquieta.org'). Leave empty to skip."
  type        = string
  default     = ""
}

variable "cloudflare_origin_cert_frontend" {
  description = "Path to Cloudflare Origin Certificate PFX file for frontend custom domain. Leave empty to skip SSL binding."
  type        = string
  default     = ""
}

variable "cloudflare_origin_cert_backend" {
  description = "Path to Cloudflare Origin Certificate PFX file for backend custom domain. Leave empty to skip SSL binding."
  type        = string
  default     = ""
}

variable "cloudflare_origin_cert_password" {
  description = "Password for Cloudflare Origin Certificate PFX files (use empty string if no password)"
  type        = string
  default     = ""
  sensitive   = true
}

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------

variable "llm_provider" {
  description = "LLM provider to use (claude, openrouter, or ollama)"
  type        = string
  default     = "openrouter"

  validation {
    condition     = contains(["claude", "openrouter", "ollama"], var.llm_provider)
    error_message = "LLM provider must be 'claude', 'openrouter', or 'ollama'."
  }
}

variable "claude_api_key" {
  description = "Anthropic Claude API key (required if llm_provider=claude)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openrouter_api_key" {
  description = "OpenRouter API key (required if llm_provider=openrouter)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openrouter_model" {
  description = "OpenRouter model name (e.g., meta-llama/llama-3.3-70b-instruct:free)"
  type        = string
  default     = "meta-llama/llama-3.3-70b-instruct:free"
}

variable "openrouter_base_url" {
  description = "OpenRouter API base URL"
  type        = string
  default     = "https://openrouter.ai/api/v1"
}

# -----------------------------------------------------------------------------
# Azure OpenAI Configuration (for Embeddings)
# -----------------------------------------------------------------------------

variable "enable_azure_openai" {
  description = "Enable Azure OpenAI for embeddings (recommended, very cheap)"
  type        = bool
  default     = true
}

variable "openai_location" {
  description = "Azure region for OpenAI (may differ from main region due to availability)"
  type        = string
  default     = "eastus" # OpenAI is available in limited regions
}

variable "embedding_model_name" {
  description = "Azure OpenAI embedding model deployment name"
  type        = string
  default     = "text-embedding-3-small"
}

variable "embedding_model_version" {
  description = "Embedding model version"
  type        = string
  default     = "1"
}

variable "embedding_capacity" {
  description = "Embedding model capacity (tokens per minute in thousands)"
  type        = number
  default     = 120
}

# -----------------------------------------------------------------------------
# Security & Rate Limiting Configuration
# -----------------------------------------------------------------------------

variable "debug_mode" {
  description = "Enable debug mode (should be false for production)"
  type        = bool
  default     = false
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL."
  }
}

variable "rate_limit_enabled" {
  description = "Enable rate limiting for API endpoints"
  type        = bool
  default     = true
}

variable "rate_limit_requests_per_minute" {
  description = "Maximum requests per IP per minute"
  type        = number
  default     = 20
}

variable "rate_limit_session_max_requests" {
  description = "Maximum total requests per session (lifetime limit, encourages breaks)"
  type        = number
  default     = 10
}

variable "content_filter_enabled" {
  description = "Enable content filtering for chat messages"
  type        = bool
  default     = true
}

variable "max_message_length" {
  description = "Maximum length of chat messages"
  type        = number
  default     = 200
}

variable "content_safety_enabled" {
  description = "Enable ML-backed content safety pipeline (Llama Guard 3 via OpenRouter)"
  type        = bool
  default     = true
}

variable "content_safety_mode" {
  description = "Content safety pipeline mode: keyword_only (fast, no external call), ml_only (keyword + Llama Guard ~270ms), hybrid (keyword + Llama Guard + Azure Content Safety)"
  type        = string
  default     = "ml_only"

  validation {
    condition     = contains(["keyword_only", "ml_only", "hybrid"], var.content_safety_mode)
    error_message = "content_safety_mode must be one of: keyword_only, ml_only, hybrid."
  }
}

# -----------------------------------------------------------------------------
# OpenRouter Fallback Configuration
# -----------------------------------------------------------------------------

variable "openrouter_fallback_models" {
  description = "Comma-separated list of fallback models for OpenRouter"
  type        = string
  default     = "meta-llama/llama-3.3-70b-instruct"
}

variable "openrouter_allow_fallbacks" {
  description = "Allow automatic fallback to paid models when free models are rate limited"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Application Insights (Monitoring)
# -----------------------------------------------------------------------------

variable "enable_application_insights" {
  description = "Enable Application Insights for monitoring and telemetry"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Budget Configuration
# -----------------------------------------------------------------------------

variable "create_budget_alert" {
  description = "Create budget alert for cost monitoring"
  type        = bool
  default     = true
}

variable "monthly_budget" {
  description = "Monthly budget limit in USD"
  type        = number
  default     = 50
}

variable "budget_alert_emails" {
  description = "Email addresses for budget alerts"
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# Email Notifications (SMTP2GO) Configuration
# -----------------------------------------------------------------------------

variable "smtp2go_enabled" {
  description = "Enable email notifications via SMTP2GO"
  type        = bool
  default     = false
}

variable "smtp2go_api_key" {
  description = "SMTP2GO API key (required if smtp2go_enabled=true)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "smtp2go_sender_email" {
  description = "Sender email address for notifications"
  type        = string
  default     = "noreply@ai4you.sh"
}

variable "smtp2go_sender_name" {
  description = "Sender name for notifications"
  type        = string
  default     = "Bible Inspiration"
}

variable "contact_notification_email" {
  description = "Email address to receive contact form notifications"
  type        = string
  default     = "contact@voxquieta.org"
}

# -----------------------------------------------------------------------------
# Cloudflare Turnstile (Bot Protection) Configuration
# -----------------------------------------------------------------------------

variable "turnstile_enabled" {
  description = "Enable Cloudflare Turnstile bot protection"
  type        = bool
  default     = false
}

variable "turnstile_secret_key" {
  description = "Cloudflare Turnstile server-side secret key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "turnstile_site_key" {
  description = "Cloudflare Turnstile client-side site key"
  type        = string
  default     = ""
}
