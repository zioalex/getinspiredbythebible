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
  default     = "westeurope" # Change to your preferred region
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
# LLM Configuration
# -----------------------------------------------------------------------------

variable "llm_provider" {
  description = "LLM provider to use (claude or ollama)"
  type        = string
  default     = "claude"

  validation {
    condition     = contains(["claude", "ollama"], var.llm_provider)
    error_message = "LLM provider must be 'claude' or 'ollama'."
  }
}

variable "claude_api_key" {
  description = "Anthropic Claude API key"
  type        = string
  default     = ""
  sensitive   = true
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
