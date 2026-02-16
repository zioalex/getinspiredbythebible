#!/bin/bash
# =============================================================================
# Import Existing Azure Resources into Terraform State
# =============================================================================
#
# Use this script when Terraform state was lost but Azure resources still exist.
#
# Usage:
#   ./import-existing-resources.sh <subscription_id> <resource_suffix>
#
# Example:
#   ./import-existing-resources.sh "f5bc5a63-92f8-4ab6-ad94-84673eeebb56" "abc123"
#
# To find the resource_suffix, run:
#   az resource list --resource-group bible-app-rg --output table
#   Look for pattern like: bible-app-logs-XXXXXX (the XXXXXX is your suffix)
#
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Arguments
# =============================================================================

if [ $# -lt 2 ]; then
    echo "Usage: $0 <subscription_id> <resource_suffix>"
    echo ""
    echo "Example: $0 'f5bc5a63-92f8-4ab6-ad94-84673eeebb56' 'abc123'"
    echo ""
    echo "To find your resource_suffix:"
    echo "  az resource list --resource-group bible-app-rg --output table"
    exit 1
fi

SUBSCRIPTION_ID="$1"
SUFFIX="$2"

# Resource naming (must match main.tf)
PROJECT_NAME="bible-app"
RG_NAME="${PROJECT_NAME}-rg"

# Derived names (matching main.tf patterns)
LOG_ANALYTICS_NAME="${PROJECT_NAME}-logs-${SUFFIX}"
CONTAINER_ENV_NAME="${PROJECT_NAME}-env"
ACR_NAME="bibleappacr${SUFFIX}"
POSTGRES_NAME="${PROJECT_NAME}-db-${SUFFIX}"
DB_NAME="bibleapp"
BACKEND_APP_NAME="${PROJECT_NAME}-backend"
FRONTEND_APP_NAME="${PROJECT_NAME}-frontend"
OPENAI_NAME="${PROJECT_NAME}-openai-${SUFFIX}"
EMBEDDING_DEPLOYMENT_NAME="text-embedding-3-small"
BUDGET_NAME="${PROJECT_NAME}-budget"

# Base resource ID prefix
BASE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG_NAME}"

# =============================================================================
# Pre-flight checks
# =============================================================================

log_info "Checking Terraform state..."
cd "$(dirname "$0")/.."

if ! terraform state list &>/dev/null; then
    log_warn "No Terraform state found. Make sure you've run 'terraform init' first."
fi

# =============================================================================
# Import Functions
# =============================================================================

import_resource() {
    local tf_address="$1"
    local azure_id="$2"
    local description="$3"

    echo ""
    log_info "Importing: $description"
    echo "  TF Address: $tf_address"
    echo "  Azure ID:   $azure_id"

    if terraform state show "$tf_address" &>/dev/null; then
        log_warn "Already in state, skipping: $tf_address"
        return 0
    fi

    if terraform import "$tf_address" "$azure_id"; then
        log_info "Successfully imported: $description"
    else
        log_error "Failed to import: $description"
        return 1
    fi
}

# =============================================================================
# Import Resources
# =============================================================================

echo "============================================================================="
echo "Importing Azure Resources into Terraform State"
echo "============================================================================="
echo ""
echo "Subscription: $SUBSCRIPTION_ID"
echo "Suffix:       $SUFFIX"
echo "RG:           $RG_NAME"
echo ""
echo "============================================================================="

# 1. Random string (special case - we need to import the suffix value)
log_info "Importing random_string.suffix..."
# Random strings can't be imported normally, we'll handle this with a state manipulation
# For now, skip and let terraform recreate (won't affect other resources if we set suffix in locals)
log_warn "random_string.suffix cannot be imported - will need manual state edit or recreation"

# 2. Resource Group
import_resource \
    "azurerm_resource_group.main" \
    "${BASE}" \
    "Resource Group"

# 3. Log Analytics Workspace
import_resource \
    "azurerm_log_analytics_workspace.main" \
    "${BASE}/providers/Microsoft.OperationalInsights/workspaces/${LOG_ANALYTICS_NAME}" \
    "Log Analytics Workspace"

# 4. Container Apps Environment
import_resource \
    "azurerm_container_app_environment.main" \
    "${BASE}/providers/Microsoft.App/managedEnvironments/${CONTAINER_ENV_NAME}" \
    "Container Apps Environment"

# 5. Container Registry
import_resource \
    "azurerm_container_registry.main" \
    "${BASE}/providers/Microsoft.ContainerRegistry/registries/${ACR_NAME}" \
    "Container Registry"

# 6. PostgreSQL Flexible Server
import_resource \
    "azurerm_postgresql_flexible_server.main" \
    "${BASE}/providers/Microsoft.DBforPostgreSQL/flexibleServers/${POSTGRES_NAME}" \
    "PostgreSQL Flexible Server"

# 7. PostgreSQL Firewall Rule - Allow Azure
import_resource \
    "azurerm_postgresql_flexible_server_firewall_rule.allow_azure" \
    "${BASE}/providers/Microsoft.DBforPostgreSQL/flexibleServers/${POSTGRES_NAME}/firewallRules/AllowAzureServices" \
    "PostgreSQL Firewall - Allow Azure"

# 8. PostgreSQL Firewall Rule - Allow Client (if exists)
log_info "Checking for client firewall rule..."
if az postgres flexible-server firewall-rule show \
    --resource-group "$RG_NAME" \
    --name "$POSTGRES_NAME" \
    --rule-name "AllowClientIP" &>/dev/null; then
    import_resource \
        "azurerm_postgresql_flexible_server_firewall_rule.allow_client[0]" \
        "${BASE}/providers/Microsoft.DBforPostgreSQL/flexibleServers/${POSTGRES_NAME}/firewallRules/AllowClientIP" \
        "PostgreSQL Firewall - Allow Client"
else
    log_warn "No client firewall rule found, skipping"
fi

# 9. PostgreSQL Configuration - Extensions
import_resource \
    "azurerm_postgresql_flexible_server_configuration.extensions" \
    "${BASE}/providers/Microsoft.DBforPostgreSQL/flexibleServers/${POSTGRES_NAME}/configurations/azure.extensions" \
    "PostgreSQL Configuration - Extensions"

# 10. PostgreSQL Database
import_resource \
    "azurerm_postgresql_flexible_server_database.app" \
    "${BASE}/providers/Microsoft.DBforPostgreSQL/flexibleServers/${POSTGRES_NAME}/databases/${DB_NAME}" \
    "PostgreSQL Database"

# 11. Container App - Backend
import_resource \
    "azurerm_container_app.backend" \
    "${BASE}/providers/Microsoft.App/containerApps/${BACKEND_APP_NAME}" \
    "Container App - Backend"

# 12. Container App - Frontend
import_resource \
    "azurerm_container_app.frontend" \
    "${BASE}/providers/Microsoft.App/containerApps/${FRONTEND_APP_NAME}" \
    "Container App - Frontend"

# 13. Azure OpenAI (if exists)
log_info "Checking for Azure OpenAI resource..."
if az cognitiveservices account show \
    --resource-group "$RG_NAME" \
    --name "$OPENAI_NAME" &>/dev/null; then
    import_resource \
        "azurerm_cognitive_account.openai[0]" \
        "${BASE}/providers/Microsoft.CognitiveServices/accounts/${OPENAI_NAME}" \
        "Azure OpenAI Account"

    # OpenAI Embedding Deployment
    import_resource \
        "azurerm_cognitive_deployment.embedding[0]" \
        "${BASE}/providers/Microsoft.CognitiveServices/accounts/${OPENAI_NAME}/deployments/${EMBEDDING_DEPLOYMENT_NAME}" \
        "Azure OpenAI Embedding Deployment"
else
    log_warn "No Azure OpenAI resource found, skipping"
fi

# 14. Budget (if exists)
log_info "Checking for budget..."
if az consumption budget show \
    --budget-name "$BUDGET_NAME" \
    --resource-group "$RG_NAME" &>/dev/null 2>&1; then
    import_resource \
        "azurerm_consumption_budget_resource_group.main" \
        "${BASE}/providers/Microsoft.Consumption/budgets/${BUDGET_NAME}" \
        "Consumption Budget"
else
    log_warn "No budget found, skipping"
fi

# =============================================================================
# Post-import
# =============================================================================

echo ""
echo "============================================================================="
echo -e "${GREEN}Import Complete!${NC}"
echo "============================================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Handle the random_string.suffix issue by editing the state:"
echo "   Option A: Add suffix to terraform.tfvars to override:"
echo "     # In variables.tf, add a variable for suffix override"
echo "     # Then set: resource_suffix_override = \"${SUFFIX}\""
echo ""
echo "   Option B: Let Terraform recreate it (may cause drift warnings)"
echo ""
echo "2. Run terraform plan to check for drift:"
echo "   terraform plan"
echo ""
echo "3. If there are differences, review and apply or adjust tfvars:"
echo "   terraform apply"
echo ""
echo "============================================================================="
