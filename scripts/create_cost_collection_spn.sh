#!/usr/bin/env bash
# =============================================================================
# Create Service Principal for BITB-150 Cost Evidence Collection
# =============================================================================
# Creates an Azure AD Service Principal with the minimum required RBAC roles
# to run the cost evidence collection scripts.
#
# Usage:
#   ./scripts/create_cost_collection_spn.sh [SP_NAME]
#
# Example:
#   ./scripts/create_cost_collection_spn.sh bitb150-cost-collector
#
# Output: Prints the credentials (clientId, clientSecret, tenantId) to stdout.
#         Save these securely — the secret is shown only once.
# =============================================================================

set -euo pipefail

# Configuration
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-f5bc5a63-92f8-4ab6-ad94-84673eeebb56}"
RESOURCE_GROUP="bible-app-rg"
SP_NAME="${1:-bitb150-cost-collector}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================================================================${NC}"
echo -e "${GREEN}BITB-150 Cost Collection SPN Creator${NC}"
echo -e "${GREEN}================================================================================${NC}"
echo ""
echo "Subscription: ${SUBSCRIPTION_ID}"
echo "Resource Group: ${RESOURCE_GROUP}"
echo "SP Name: ${SP_NAME}"
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}ERROR: Azure CLI not found. Install: https://aka.ms/installazurecli${NC}"
    exit 1
fi

# Check login
echo "Checking Azure login..."
if ! az account show --output none 2>/dev/null; then
    echo -e "${YELLOW}Not logged in. Starting interactive login...${NC}"
    az login --output none
fi

# Set subscription
az account set --subscription "${SUBSCRIPTION_ID}"

# Check if SP already exists
echo ""
echo "Checking for existing Service Principal..."
EXISTING_SP=$(az ad sp list --display-name "${SP_NAME}" --query "[0].appId" -o tsv 2>/dev/null || true)

if [[ -n "${EXISTING_SP}" && "${EXISTING_SP}" != "null" ]]; then
    echo -e "${YELLOW}Service Principal '${SP_NAME}' already exists (appId: ${EXISTING_SP})${NC}"
    read -p "Reset credentials and re-assign roles? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi

    echo "Resetting credentials..."
    az ad sp credential reset --id "${EXISTING_SP}" --years 2 --output json
    APP_ID="${EXISTING_SP}"
else
    echo "Creating new Service Principal..."
    SP_OUTPUT=$(az ad sp create-for-rbac \
        --name "${SP_NAME}" \
        --role "Reader" \
        --scopes "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
        --years 2 \
        --output json)

    APP_ID=$(echo "${SP_OUTPUT}" | jq -r '.appId')
    CLIENT_SECRET=$(echo "${SP_OUTPUT}" | jq -r '.password')
    TENANT_ID=$(echo "${SP_OUTPUT}" | jq -r '.tenant')

    echo -e "${GREEN}Service Principal created: ${APP_ID}${NC}"
fi

# Wait for SP propagation
echo ""
echo "Waiting for SP propagation (10s)..."
sleep 10

# Assign required roles
echo ""
echo "Assigning required RBAC roles..."

RG_SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"

# 1. Cost Management Reader
echo "  → Cost Management Reader..."
az role assignment create \
    --assignee "${APP_ID}" \
    --role "Cost Management Reader" \
    --scope "${RG_SCOPE}" \
    --output none 2>/dev/null || echo "    (may already exist)"

# 2. Monitoring Reader
echo "  → Monitoring Reader..."
az role assignment create \
    --assignee "${APP_ID}" \
    --role "Monitoring Reader" \
    --scope "${RG_SCOPE}" \
    --output none 2>/dev/null || echo "    (may already exist)"

# 3. PostgreSQL Flexible Server Reader
echo "  → PostgreSQL Flexible Server Reader..."
az role assignment create \
    --assignee "${APP_ID}" \
    --role "PostgreSQL Flexible Server Reader" \
    --scope "${RG_SCOPE}" \
    --output none 2>/dev/null || echo "    (may already exist)"

# 4. Log Analytics Reader
echo "  → Log Analytics Reader..."
az role assignment create \
    --assignee "${APP_ID}" \
    --role "Log Analytics Reader" \
    --scope "${RG_SCOPE}" \
    --output none 2>/dev/null || echo "    (may already exist)"

# 5. Container Apps Reader (for container app config)
echo "  → Azure Container Apps Reader..."
az role assignment create \
    --assignee "${APP_ID}" \
    --role "Azure Container Apps Reader" \
    --scope "${RG_SCOPE}" \
    --output none 2>/dev/null || echo "    (may already exist)"

# 6. App Configuration Data Reader (for App Insights)
echo "  → App Configuration Data Reader..."
az role assignment create \
    --assignee "${APP_ID}" \
    --role "App Configuration Data Reader" \
    --scope "${RG_SCOPE}" \
    --output none 2>/dev/null || echo "    (may already exist)"

# Verify assignments
echo ""
echo "Verifying role assignments..."
az role assignment list --assignee "${APP_ID}" --scope "${RG_SCOPE}" --output table

# Output credentials
echo ""
echo -e "${GREEN}================================================================================${NC}"
echo -e "${GREEN}CREDENTIALS — SAVE THESE SECURELY (clientSecret shown only once!)${NC}"
echo -e "${GREEN}================================================================================${NC}"
echo ""
echo "export AZURE_CLIENT_ID=\"${APP_ID}\""
echo "export AZURE_CLIENT_SECRET=\"${CLIENT_SECRET}\""
echo "export AZURE_TENANT_ID=\"${TENANT_ID}\""
echo "export AZURE_SUBSCRIPTION_ID=\"${SUBSCRIPTION_ID}\""
echo ""
echo -e "${YELLOW}Also set DATABASE_URL for PostgreSQL SQL queries:${NC}"
echo "export DATABASE_URL=\"postgresql://<user>:<pass>@<server>.postgres.database.azure.com:5432/<db>?sslmode=require\""
echo ""
echo -e "${GREEN}================================================================================${NC}"
echo "Add these to your shell profile or GitHub Actions secrets:"
echo "  - AZURE_CLIENT_ID"
echo "  - AZURE_CLIENT_SECRET"
echo "  - AZURE_TENANT_ID"
echo "  - AZURE_SUBSCRIPTION_ID"
echo "  - DATABASE_URL (optional, for SQL queries)"
echo -e "${GREEN}================================================================================${NC}"
