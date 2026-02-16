#!/bin/bash
# =============================================================================
# Setup Azure Service Principal for GitHub Actions
# =============================================================================
#
# This script creates an Azure Service Principal (SPN) for GitHub Actions
# CI/CD pipelines and optionally configures GitHub repository secrets.
#
# Usage:
#   ./setup-github-spn.sh -e <environment> [-s <subscription_id>] [-r <repo>] [-g]
#
# Options:
#   -e, --env          Environment: dev, np (non-prod), or prod (required)
#   -s, --subscription Azure Subscription ID (optional, uses current if not set)
#   -r, --repo         GitHub repo (owner/name) for setting secrets (optional)
#   -g, --set-secrets  Set GitHub secrets using gh CLI (requires -r)
#   -h, --help         Show this help message
#
# Examples:
#   # Create SPN for dev environment
#   ./setup-github-spn.sh -e dev
#
#   # Create SPN for prod and set GitHub secrets
#   ./setup-github-spn.sh -e prod -r myorg/myrepo -g
#
#   # Create SPN for specific subscription
#   ./setup-github-spn.sh -e np -s "12345678-1234-1234-1234-123456789012"
#
# Prerequisites:
#   - Azure CLI (az) installed and logged in
#   - GitHub CLI (gh) installed and authenticated (only if using -g flag)
#   - Sufficient Azure AD permissions to create service principals
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================
APP_NAME_PREFIX="github-actions-bible-app"
VALID_ENVIRONMENTS=("dev" "np" "prod")

# Role assignments per environment
# - dev: Contributor (full access for development)
# - np: Contributor (testing deployments)
# - prod: Contributor (required for Terraform, but with environment protection)
declare -A ENV_ROLES=(
    ["dev"]="Contributor"
    ["np"]="Contributor"
    ["prod"]="Contributor"
)

# Optional: Restrict to specific resource group per environment
declare -A ENV_SCOPES=(
    ["dev"]="subscription"    # Full subscription access
    ["np"]="subscription"     # Full subscription access
    ["prod"]="subscription"   # Full subscription (use GitHub environment protection)
)

# =============================================================================
# Colors and Logging
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# =============================================================================
# Help
# =============================================================================
show_help() {
    head -35 "$0" | tail -32 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# =============================================================================
# Argument Parsing
# =============================================================================
ENVIRONMENT=""
SUBSCRIPTION_ID=""
GITHUB_REPO=""
SET_SECRETS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--subscription)
            SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        -r|--repo)
            GITHUB_REPO="$2"
            shift 2
            ;;
        -g|--set-secrets)
            SET_SECRETS=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use -h for help"
            exit 1
            ;;
    esac
done

# =============================================================================
# Validation
# =============================================================================

# Check environment is provided
if [ -z "$ENVIRONMENT" ]; then
    log_error "Environment (-e) is required"
    echo "Valid environments: ${VALID_ENVIRONMENTS[*]}"
    exit 1
fi

# Validate environment
ENVIRONMENT=$(echo "$ENVIRONMENT" | tr '[:upper:]' '[:lower:]')
if [[ ! " ${VALID_ENVIRONMENTS[*]} " =~ ${ENVIRONMENT} ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    echo "Valid environments: ${VALID_ENVIRONMENTS[*]}"
    exit 1
fi

# Check if setting secrets requires repo
if [ "$SET_SECRETS" = true ] && [ -z "$GITHUB_REPO" ]; then
    log_error "GitHub repo (-r) is required when using -g flag"
    exit 1
fi

# Check Azure CLI
if ! command -v az &> /dev/null; then
    log_error "Azure CLI (az) is not installed"
    log_info "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    log_error "Not logged in to Azure. Run 'az login' first"
    exit 1
fi

# Check GitHub CLI if setting secrets
if [ "$SET_SECRETS" = true ]; then
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) is not installed"
        log_info "Install from: https://cli.github.com/"
        exit 1
    fi
    if ! gh auth status &> /dev/null; then
        log_error "Not logged in to GitHub. Run 'gh auth login' first"
        exit 1
    fi
fi

# =============================================================================
# Main Script
# =============================================================================

log_info "Setting up Service Principal for environment: ${ENVIRONMENT^^}"

# Set subscription if provided
if [ -n "$SUBSCRIPTION_ID" ]; then
    log_step "Setting subscription to: $SUBSCRIPTION_ID"
    az account set --subscription "$SUBSCRIPTION_ID"
fi

# Get current subscription info
SUBSCRIPTION_ID=$(az account show --query 'id' -o tsv)
SUBSCRIPTION_NAME=$(az account show --query 'name' -o tsv)
TENANT_ID=$(az account show --query 'tenantId' -o tsv)

log_info "Using subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"

# Generate SPN name
SPN_NAME="${APP_NAME_PREFIX}-${ENVIRONMENT}"
ROLE="${ENV_ROLES[$ENVIRONMENT]}"

# Determine scope
if [ "${ENV_SCOPES[$ENVIRONMENT]}" = "subscription" ]; then
    SCOPE="/subscriptions/${SUBSCRIPTION_ID}"
else
    # Could be extended to support resource group scopes
    SCOPE="/subscriptions/${SUBSCRIPTION_ID}"
fi

log_step "Creating Service Principal: $SPN_NAME"
log_info "  Role: $ROLE"
log_info "  Scope: $SCOPE"

# Check if SPN already exists
EXISTING_APP=$(az ad app list --display-name "$SPN_NAME" --query '[0].appId' -o tsv 2>/dev/null || true)
if [ -n "$EXISTING_APP" ]; then
    log_warn "Service Principal '$SPN_NAME' already exists (App ID: $EXISTING_APP)"
    read -p "Do you want to reset the credentials? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Keeping existing credentials. Exiting."
        exit 0
    fi
    log_step "Resetting credentials for existing SPN..."
    SPN_OUTPUT=$(az ad sp credential reset --id "$EXISTING_APP" --query '{clientId:appId, clientSecret:password, tenantId:tenant}' -o json)
    CLIENT_ID=$(echo "$SPN_OUTPUT" | jq -r '.clientId')
    CLIENT_SECRET=$(echo "$SPN_OUTPUT" | jq -r '.clientSecret')
else
    # Create new SPN with role assignment
    log_step "Creating new Service Principal..."
    SPN_OUTPUT=$(az ad sp create-for-rbac \
        --name "$SPN_NAME" \
        --role "$ROLE" \
        --scopes "$SCOPE" \
        --query '{clientId:appId, clientSecret:password, tenantId:tenant}' \
        -o json)

    CLIENT_ID=$(echo "$SPN_OUTPUT" | jq -r '.clientId')
    CLIENT_SECRET=$(echo "$SPN_OUTPUT" | jq -r '.clientSecret')
fi

# Verify the SPN was created
if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "null" ]; then
    log_error "Failed to create Service Principal"
    exit 1
fi

log_info "Service Principal created successfully!"

# =============================================================================
# Output Credentials
# =============================================================================

echo ""
echo "============================================================================="
echo -e "${GREEN}Service Principal Created Successfully!${NC}"
echo "============================================================================="
echo ""
echo "Environment:    ${ENVIRONMENT^^}"
echo "SPN Name:       $SPN_NAME"
echo "Role:           $ROLE"
echo ""
echo "============================================================================="
echo "GitHub Secrets (add these to your repository)"
echo "============================================================================="
echo ""
echo "ARM_CLIENT_ID=$CLIENT_ID"
echo "ARM_CLIENT_SECRET=$CLIENT_SECRET"
echo "ARM_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
echo "ARM_TENANT_ID=$TENANT_ID"
echo ""

# =============================================================================
# Set GitHub Secrets (optional)
# =============================================================================

if [ "$SET_SECRETS" = true ]; then
    log_step "Setting GitHub secrets for repository: $GITHUB_REPO"

    # Determine environment suffix for secret names (optional: use different secrets per env)
    # Determine environment suffix for secret names (optional: use different secrets per env)
    if [ "$ENVIRONMENT" = "prod" ]; then
        SECRET_SUFFIX=""  # pragma: allowlist secret
    else
        SECRET_SUFFIX="_${ENVIRONMENT^^}"  # pragma: allowlist secret
    fi

    echo ""
    read -p "Set secrets with suffix '${SECRET_SUFFIX:-<none>}'? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Setting ARM_CLIENT_ID${SECRET_SUFFIX}..."
        echo "$CLIENT_ID" | gh secret set "ARM_CLIENT_ID${SECRET_SUFFIX}" --repo "$GITHUB_REPO"

        log_info "Setting ARM_CLIENT_SECRET${SECRET_SUFFIX}..."
        echo "$CLIENT_SECRET" | gh secret set "ARM_CLIENT_SECRET${SECRET_SUFFIX}" --repo "$GITHUB_REPO"

        log_info "Setting ARM_SUBSCRIPTION_ID${SECRET_SUFFIX}..."
        echo "$SUBSCRIPTION_ID" | gh secret set "ARM_SUBSCRIPTION_ID${SECRET_SUFFIX}" --repo "$GITHUB_REPO"

        log_info "Setting ARM_TENANT_ID${SECRET_SUFFIX}..."
        echo "$TENANT_ID" | gh secret set "ARM_TENANT_ID${SECRET_SUFFIX}" --repo "$GITHUB_REPO"

        log_info "GitHub secrets configured successfully!"
    else
        log_info "Skipped setting GitHub secrets"
    fi
fi

# =============================================================================
# Additional Instructions
# =============================================================================

echo ""
echo "============================================================================="
echo "Next Steps"
echo "============================================================================="
echo ""
echo "1. Add the secrets above to your GitHub repository:"
echo "   - Go to: https://github.com/${GITHUB_REPO:-your-org/your-repo}/settings/secrets/actions"
echo "   - Click 'New repository secret' for each secret"
echo ""

if [ "$ENVIRONMENT" = "prod" ]; then
    echo "2. Create a GitHub Environment for production deployments:"
    echo "   - Go to: https://github.com/${GITHUB_REPO:-your-org/your-repo}/settings/environments"
    echo "   - Create environment: 'production'"
    echo "   - Add required reviewers for deployment approval"
    echo "   - Optionally restrict to 'main' branch only"
    echo ""
fi

echo "3. Run the Terraform backend setup (if not done):"
echo "   ./scripts/setup-tf-backend.sh"
echo ""
echo "4. Add the TF_STORAGE_ACCOUNT secret to GitHub:"
echo "   - Value: your storage account name from setup-tf-backend.sh"
echo ""
echo "============================================================================="

# =============================================================================
# Cleanup Reminder
# =============================================================================

if [ "$ENVIRONMENT" = "dev" ] || [ "$ENVIRONMENT" = "np" ]; then
    echo ""
    log_warn "Remember to delete unused SPNs when no longer needed:"
    echo "   az ad sp delete --id $CLIENT_ID"
    echo ""
fi
