#!/bin/bash
# =============================================================================
# Setup Azure Storage Account for Terraform Remote State
# =============================================================================
#
# This script creates the Azure resources needed for Terraform remote state:
# - Resource Group
# - Storage Account with versioning
# - Blob Container
#
# Usage:
#   ./setup-tf-backend.sh [subscription_id] [location]
#
# Example:
#   ./setup-tf-backend.sh "12345678-1234-1234-1234-123456789012" "northeurope"
#
# After running this script:
#   1. Note the storage account name from the output
#   2. Run: terraform init -backend-config="storage_account_name=<name>"
# =============================================================================

set -euo pipefail

# Configuration
RESOURCE_GROUP_NAME="bible-app-tfstate-rg"
STORAGE_ACCOUNT_PREFIX="bibleapptfstate"
CONTAINER_NAME="tfstate"
SUBSCRIPTION_ID="${1:-}"
LOCATION="${2:-northeurope}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    log_error "Azure CLI (az) is not installed. Please install it first."
    log_info "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    log_error "Not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# Set subscription if provided
if [ -n "$SUBSCRIPTION_ID" ]; then
    log_info "Setting subscription to: $SUBSCRIPTION_ID"
    az account set --subscription "$SUBSCRIPTION_ID"
fi

# Get current subscription info
CURRENT_SUB=$(az account show --query '{name:name, id:id}' -o tsv)
log_info "Using subscription: $CURRENT_SUB"

# Generate unique storage account name (read limited bytes to avoid SIGPIPE)
RANDOM_SUFFIX=$(head -c 100 /dev/urandom | tr -dc 'a-z0-9' | head -c 8)
STORAGE_ACCOUNT_NAME="${STORAGE_ACCOUNT_PREFIX}${RANDOM_SUFFIX}"

log_info "Creating Terraform backend resources..."
log_info "  Resource Group: $RESOURCE_GROUP_NAME"
log_info "  Storage Account: $STORAGE_ACCOUNT_NAME"
log_info "  Container: $CONTAINER_NAME"
log_info "  Location: $LOCATION"

# Create Resource Group
log_info "Creating resource group..."
az group create \
    --name "$RESOURCE_GROUP_NAME" \
    --location "$LOCATION" \
    --tags "purpose=terraform-state" "project=getinspiredbythebible" \
    --output none

# Create Storage Account
log_info "Creating storage account (this may take a minute)..."
az storage account create \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --location "$LOCATION" \
    --sku "Standard_LRS" \
    --kind "StorageV2" \
    --access-tier "Hot" \
    --min-tls-version "TLS1_2" \
    --allow-blob-public-access false \
    --tags "purpose=terraform-state" "project=getinspiredbythebible" \
    --output none

# Enable versioning for state history
log_info "Enabling blob versioning..."
az storage account blob-service-properties update \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --enable-versioning true \
    --output none

# Get storage account key
log_info "Retrieving storage account key..."
STORAGE_KEY=$(az storage account keys list \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query '[0].value' -o tsv)

# Create blob container
log_info "Creating blob container..."
az storage container create \
    --name "$CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_KEY" \
    --output none

# Output results
echo ""
echo "============================================================================="
echo -e "${GREEN}Terraform backend setup complete!${NC}"
echo "============================================================================="
echo ""
echo "Storage Account Name: $STORAGE_ACCOUNT_NAME"
echo "Resource Group:       $RESOURCE_GROUP_NAME"
echo "Container:            $CONTAINER_NAME"
echo ""
echo "Next steps:"
echo ""
echo "1. Initialize Terraform with the backend:"
echo "   cd deployment"
echo "   terraform init -backend-config=\"storage_account_name=$STORAGE_ACCOUNT_NAME\""
echo ""
echo "2. Or create a backend.hcl file:"
echo "   echo 'storage_account_name = \"$STORAGE_ACCOUNT_NAME\"' > backend.hcl"
echo "   terraform init -backend-config=backend.hcl"
echo ""
echo "3. For CI/CD pipelines, set these environment variables:"
echo "   ARM_ACCESS_KEY=<storage-account-key>"
echo "   Or use Azure CLI authentication with a service principal"
echo ""
echo "============================================================================="

# Optionally create backend.hcl
read -p "Create backend.hcl file now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cat > backend.hcl <<EOF
# Terraform Backend Configuration
# Generated by setup-tf-backend.sh

storage_account_name = "$STORAGE_ACCOUNT_NAME"
resource_group_name  = "$RESOURCE_GROUP_NAME"
container_name       = "$CONTAINER_NAME"
key                  = "bible-app.tfstate"
EOF
    log_info "Created backend.hcl"
    echo ""
    echo "Add to .gitignore: backend.hcl"
fi
