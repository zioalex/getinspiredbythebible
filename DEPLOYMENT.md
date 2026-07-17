# Deployment Guide

## Local environments

All local run modes (fully local stack, side-by-side dev stack, local
containers against the production DB + LLMs) are documented in
**[docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md)**.

```bash
make docker-up               # fully local (Ollama + local Postgres)
make docker-up-dev           # second stack on shifted ports (3001/8001)
make docker-up-local-prod    # local containers -> PROD DB + cloud LLMs
```

## Production (Azure Container Apps)

Production runs on Azure Container Apps behind <https://voxquieta.org>,
provisioned by Terraform (`deployment/`) and deployed by the
`azure-deploy.yml` GitHub Actions workflow, which builds and pushes the
`bible-backend` / `bible-frontend` images to ACR and applies Terraform.

**The normal deploy path is CI**: merge to `main` and let the workflow run.

### Manual build & deploy (fallback)

Requires `az login` and a filled-in `.env.production`
(`cp .env.production.example .env.production`).

```bash
# Build and push both images to ACR, tagged with the git SHA
make docker-build-prod

# Deploy via Terraform (updates terraform.tfvars image tags, then applies)
make docker-deploy-prod

# Or: fast deploy of already-pushed images via az CLI (no Terraform)
make docker-deploy-prod-quick
```

Useful companions:

```bash
make az-acr-list-tags        # what's in the registry
make az-deployed-images      # what's actually running
make az-logs-backend         # tail prod backend logs
make az-logs-frontend        # tail prod frontend logs
make update-env-backend-url  # refresh NEXT_PUBLIC_API_URL in .env.production
```

### Infrastructure (Terraform)

```bash
make tf-init      # backend config auto-detected from Azure
make tf-plan      # requires deployment/terraform.tfvars.secrets
make tf-apply
```

See `deployment/README.md` for the full infrastructure documentation.

## Legacy: self-hosted with Cloudflare Tunnel

The pre-Azure self-hosted mode (full stack on one box, exposed through a
Cloudflare Tunnel) still works via:

```bash
make docker-up-prod        # CPU
make docker-up-prod-gpu    # GPU
```

It uses `docker-compose.yml` with `.env.production` and expects a Cloudflare
Tunnel routing `/api/*`, `/health`, and `/config` to `localhost:8000` and
everything else to `localhost:3000`. This path is kept for reference and is
not the production deployment.
