# =============================================================================
# Outputs for Azure Bible App Deployment
# =============================================================================

# -----------------------------------------------------------------------------
# Resource Group
# -----------------------------------------------------------------------------

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_id" {
  description = "ID of the resource group"
  value       = azurerm_resource_group.main.id
}

# -----------------------------------------------------------------------------
# Container Registry
# -----------------------------------------------------------------------------

output "acr_login_server" {
  description = "Azure Container Registry login server"
  value       = azurerm_container_registry.main.login_server
}

output "acr_admin_username" {
  description = "ACR admin username"
  value       = azurerm_container_registry.main.admin_username
}

output "acr_admin_password" {
  description = "ACR admin password"
  value       = azurerm_container_registry.main.admin_password
  sensitive   = true
}

# -----------------------------------------------------------------------------
# PostgreSQL
# -----------------------------------------------------------------------------

output "postgresql_fqdn" {
  description = "PostgreSQL server fully qualified domain name"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "postgresql_connection_string" {
  description = "PostgreSQL connection string (without password)"
  value       = "postgresql://${var.db_admin_username}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.db_name}?sslmode=require"
}

output "postgresql_database" {
  description = "PostgreSQL database name"
  value       = var.db_name
}

# -----------------------------------------------------------------------------
# Container Apps URLs
# -----------------------------------------------------------------------------

output "backend_url" {
  description = "Backend API URL"
  value       = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
}

output "frontend_url" {
  description = "Frontend application URL"
  value       = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}

output "backend_fqdn" {
  description = "Backend FQDN (for internal use)"
  value       = azurerm_container_app.backend.ingress[0].fqdn
}

output "frontend_fqdn" {
  description = "Frontend FQDN"
  value       = azurerm_container_app.frontend.ingress[0].fqdn
}

# -----------------------------------------------------------------------------
# Custom Domains
# -----------------------------------------------------------------------------

output "custom_domain_frontend" {
  description = "Custom domain for frontend (if configured)"
  value       = var.custom_domain_frontend != "" ? "https://${var.custom_domain_frontend}" : "Not configured"
}

output "custom_domain_backend" {
  description = "Custom domain for backend API (if configured)"
  value       = var.custom_domain_backend != "" ? "https://${var.custom_domain_backend}" : "Not configured"
}

output "dns_configuration" {
  description = "DNS configuration for Cloudflare or other DNS providers"
  value       = <<-EOT

    ============================================================
    DNS CONFIGURATION (for Cloudflare)
    ============================================================

    FRONTEND CNAME:
      Name:   ${var.custom_domain_frontend != "" ? var.custom_domain_frontend : "your-domain.com"}
      Target: ${azurerm_container_app.frontend.ingress[0].fqdn}
      Proxy:  Enabled (orange cloud)

    ${var.custom_domain_backend != "" ? "BACKEND API CNAME:\n      Name:   ${var.custom_domain_backend}\n      Target: ${azurerm_container_app.backend.ingress[0].fqdn}\n      Proxy:  Enabled (orange cloud)" : ""}

    CLOUDFLARE SSL SETTINGS:
      SSL/TLS Mode: Full (Strict)
      Always Use HTTPS: On
      Minimum TLS Version: 1.2

    ============================================================
  EOT
}

output "domain_verification_id" {
  description = "Domain verification ID for TXT record (if domain verification fails)"
  value       = azurerm_container_app.frontend.custom_domain_verification_id
  sensitive   = true
}

output "custom_domain_dns_setup" {
  description = "DNS records to add in Cloudflare before terraform apply"
  sensitive   = true
  value       = <<-EOT

    ============================================================
    DNS SETUP FOR CUSTOM DOMAINS (Cloudflare)
    ============================================================

    ${var.custom_domain_frontend != "" ? "FRONTEND (${var.custom_domain_frontend}):" : ""}
    ${var.custom_domain_frontend != "" ? "  1. CNAME Record:" : ""}
    ${var.custom_domain_frontend != "" ? "     Name:   @ (or subdomain)" : ""}
    ${var.custom_domain_frontend != "" ? "     Target: ${azurerm_container_app.frontend.ingress[0].fqdn}" : ""}
    ${var.custom_domain_frontend != "" ? "     Proxy:  Enabled (orange cloud)" : ""}
    ${var.custom_domain_frontend != "" ? "" : ""}
    ${var.custom_domain_frontend != "" ? "  2. TXT Record (for verification, if needed):" : ""}
    ${var.custom_domain_frontend != "" ? "     Name:   asuid.${var.custom_domain_frontend}" : ""}
    ${var.custom_domain_frontend != "" ? "     Value:  ${azurerm_container_app.frontend.custom_domain_verification_id}" : ""}

    ${var.custom_domain_backend != "" ? "BACKEND API (${var.custom_domain_backend}):" : ""}
    ${var.custom_domain_backend != "" ? "  1. CNAME Record:" : ""}
    ${var.custom_domain_backend != "" ? "     Name:   api (or subdomain)" : ""}
    ${var.custom_domain_backend != "" ? "     Target: ${azurerm_container_app.backend.ingress[0].fqdn}" : ""}
    ${var.custom_domain_backend != "" ? "     Proxy:  Enabled (orange cloud)" : ""}

    CLOUDFLARE SSL SETTINGS:
      SSL/TLS Mode: Full (Strict)
      Always Use HTTPS: On

    ============================================================
    NOTE: Add DNS records BEFORE running terraform apply with
    custom domains, or the hostname binding will fail.
    ============================================================
  EOT
}

# -----------------------------------------------------------------------------
# Azure OpenAI (Embeddings)
# -----------------------------------------------------------------------------

output "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint for embeddings"
  value       = var.enable_azure_openai ? azurerm_cognitive_account.openai[0].endpoint : "Azure OpenAI not enabled"
}

output "azure_openai_deployment" {
  description = "Azure OpenAI embedding deployment name"
  value       = var.enable_azure_openai ? var.embedding_model_name : "Azure OpenAI not enabled"
}

# -----------------------------------------------------------------------------
# Deployment Commands
# -----------------------------------------------------------------------------

output "docker_login_command" {
  description = "Command to login to Azure Container Registry"
  value       = "az acr login --name ${azurerm_container_registry.main.name}"
}

output "build_and_push_backend" {
  description = "Commands to build and push backend image"
  value       = <<-EOT
    # Build and push backend
    cd backend
    docker build -t ${azurerm_container_registry.main.login_server}/bible-backend:latest .
    docker push ${azurerm_container_registry.main.login_server}/bible-backend:latest

    # Update container app
    az containerapp update \
      --name ${azurerm_container_app.backend.name} \
      --resource-group ${azurerm_resource_group.main.name} \
      --image ${azurerm_container_registry.main.login_server}/bible-backend:latest
  EOT
}

output "build_and_push_frontend" {
  description = "Commands to build and push frontend image"
  value       = <<-EOT
    # Build and push frontend
    cd frontend
    docker build -t ${azurerm_container_registry.main.login_server}/bible-frontend:latest .
    docker push ${azurerm_container_registry.main.login_server}/bible-frontend:latest

    # Update container app
    az containerapp update \
      --name ${azurerm_container_app.frontend.name} \
      --resource-group ${azurerm_resource_group.main.name} \
      --image ${azurerm_container_registry.main.login_server}/bible-frontend:latest
  EOT
}

# -----------------------------------------------------------------------------
# Cost Estimation
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Application Insights
# -----------------------------------------------------------------------------

output "application_insights_connection_string" {
  description = "Application Insights connection string"
  value       = var.enable_application_insights ? azurerm_application_insights.main[0].connection_string : ""
  sensitive   = true
}

output "application_insights_instrumentation_key" {
  description = "Application Insights instrumentation key (for frontend JS SDK)"
  value       = var.enable_application_insights ? azurerm_application_insights.main[0].instrumentation_key : ""
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Cost Estimates
# -----------------------------------------------------------------------------

output "estimated_monthly_cost" {
  description = "Estimated monthly cost breakdown"
  value       = <<-EOT

    ================================================
    ESTIMATED MONTHLY COST (USD)
    ================================================

    PostgreSQL Flexible Server (B1ms):  ~$13-16
    Container Registry (Basic):         ~$5
    Container Apps (scale-to-zero):     ~$5-15*
    Log Analytics:                      ~$2-3
    Azure OpenAI Embeddings:            ~$0.05**
    ------------------------------------------------
    TOTAL ESTIMATE:                     ~$25-40/month

    * Container Apps cost depends on usage:
      - Scale-to-zero = pay only when processing requests
      - First 180,000 vCPU-seconds/month FREE
      - First 360,000 GiB-seconds/month FREE

    ** Azure OpenAI Embeddings are extremely cheap:
      - One-time Bible embedding (~31K verses): ~$0.20
      - Per query embedding: ~$0.00002
      - Monthly estimate for 1000 queries: ~$0.05

    Budget alert set at: $${var.monthly_budget}
    ================================================
  EOT
}

# -----------------------------------------------------------------------------
# Next Steps
# -----------------------------------------------------------------------------

output "next_steps" {
  description = "Instructions for completing the deployment"
  value       = <<-EOT

    ============================================================
    DEPLOYMENT COMPLETE - Next Steps
    ============================================================

    1. LOGIN TO AZURE CONTAINER REGISTRY:
       az acr login --name ${azurerm_container_registry.main.name}

    2. BUILD AND PUSH YOUR IMAGES:

       # Backend
       cd backend
       docker build --platform linux/amd64 -t ${azurerm_container_registry.main.login_server}/bible-backend:latest .
       docker push ${azurerm_container_registry.main.login_server}/bible-backend:latest

       # Frontend
       cd frontend
       docker build --platform linux/amd64 -t ${azurerm_container_registry.main.login_server}/bible-frontend:latest .
       docker push ${azurerm_container_registry.main.login_server}/bible-frontend:latest

    3. UPDATE TERRAFORM VARIABLES:
       backend_image  = "${azurerm_container_registry.main.login_server}/bible-backend:latest"
       frontend_image = "${azurerm_container_registry.main.login_server}/bible-frontend:latest"

    4. RE-APPLY TERRAFORM:
       terraform apply

    5. INITIALIZE DATABASE:
       # Connect and run migrations
       psql "${azurerm_postgresql_flexible_server.main.fqdn}" -U ${var.db_admin_username} -d ${var.db_name}
       # Or use your app's migration command

    6. ACCESS YOUR APP:
       Frontend: https://${azurerm_container_app.frontend.ingress[0].fqdn}
       Backend:  https://${azurerm_container_app.backend.ingress[0].fqdn}

    ============================================================
  EOT
}
