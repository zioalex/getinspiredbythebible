# Deployment Guide

## Local Development

```bash
# Use local environment
docker compose --env-file .env.local up -d

# Or just use defaults (same as .env.local)
docker compose up -d
```

Access:

- Frontend: <http://localhost:3000>
- API: <http://localhost:8000>
- API Docs: <http://localhost:8000/docs>

## Production (with Cloudflare Tunnel)

```bash
# Use production environment
docker compose --env-file .env.production up -d --build

# Or set variables directly
export NEXT_PUBLIC_API_URL=https://getinspiredbythebible.ai4you.sh
docker compose up -d --build frontend
```

### Cloudflare Tunnel Configuration

Your `config.yml` should route requests like this:

```yaml
ingress:
  # API endpoints
  - hostname: getinspiredbythebible.ai4you.sh
    path: /api/*
    service: http://localhost:8000

  - hostname: getinspiredbythebible.ai4you.sh
    path: /health
    service: http://localhost:8000

  - hostname: getinspiredbythebible.ai4you.sh
    path: /config
    service: http://localhost:8000

  # Frontend (catch-all)
  - hostname: getinspiredbythebible.ai4you.sh
    service: http://localhost:3000

  - service: http_status:404
```

## Quick Commands

```bash
# Local development (CPU)
make docker-up

# Local with GPU
make docker-up-gpu

# Production deployment
make docker-up ARGS="--env-file .env.production"

# Stop services
make docker-down

# View logs
make docker-logs
```
