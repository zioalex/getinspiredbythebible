# =============================================================================
# Terraform Backend Configuration - Azure Blob Storage
# =============================================================================
#
# This configures Terraform to store state in Azure Blob Storage, enabling:
# - Team collaboration (shared state)
# - CI/CD pipeline integration
# - State locking (prevents concurrent modifications)
# - State versioning (via blob versioning)
#
# SETUP REQUIRED:
# Before using this backend, run the setup script:
#   ./scripts/setup-tf-backend.sh
#
# Or manually create:
# 1. Resource Group: bible-app-tfstate-rg
# 2. Storage Account: bibleapptfstate<random>
# 3. Container: tfstate
#
# Then initialize with:
#   terraform init -backend-config="storage_account_name=<your-storage-account>"
# =============================================================================

terraform {
  backend "azurerm" {
    # These values can be provided via:
    # 1. -backend-config flags during init
    # 2. Environment variables (ARM_*)
    # 3. backend.hcl file

    resource_group_name = "bible-app-tfstate-rg"
    container_name      = "tfstate"
    key                 = "bible-app.tfstate"

    # storage_account_name is provided via:
    # - terraform init -backend-config="storage_account_name=xxx"
    # - Or set in backend.hcl file
  }
}
