#!/bin/bash
# =============================================================================
# Update .env.production with the current Azure backend URL
# =============================================================================
# This script fetches the backend URL from Azure Container Apps and updates
# the NEXT_PUBLIC_API_URL in .env.production
#
# Usage:
#   ./scripts/update-env-backend-url.sh
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - bible-app-backend container app deployed
# =============================================================================

set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

ENV_FILE=".env.production"
RESOURCE_GROUP="bible-app-rg"
BACKEND_APP="bible-app-backend"

echo -e "${BLUE}Fetching backend URL from Azure...${NC}"

# Check if Azure CLI is logged in
if ! az account show &>/dev/null; then
    echo -e "${RED}Error: Not logged in to Azure. Run 'az login' first.${NC}"
    exit 1
fi

# Get the backend FQDN
BACKEND_FQDN=$(az containerapp show \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null)

if [ -z "$BACKEND_FQDN" ]; then
    echo -e "${RED}Error: Could not fetch backend URL. Is the container app deployed?${NC}"
    exit 1
fi

BACKEND_URL="https://${BACKEND_FQDN}"
echo -e "${GREEN}Backend URL: ${BACKEND_URL}${NC}"

# Check if .env.production exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: ${ENV_FILE} not found${NC}"
    exit 1
fi

# Update or add NEXT_PUBLIC_API_URL in .env.production
if grep -q "^NEXT_PUBLIC_API_URL=" "$ENV_FILE"; then
    # Update existing line
    sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=${BACKEND_URL}|" "$ENV_FILE"
    echo -e "${GREEN}✓ Updated NEXT_PUBLIC_API_URL in ${ENV_FILE}${NC}"
else
    # Add new line
    echo "NEXT_PUBLIC_API_URL=${BACKEND_URL}" >> "$ENV_FILE"
    echo -e "${GREEN}✓ Added NEXT_PUBLIC_API_URL to ${ENV_FILE}${NC}"
fi

# Show the current value
echo -e "${YELLOW}Current value:${NC}"
grep "^NEXT_PUBLIC_API_URL=" "$ENV_FILE"
