# Safety Rules for Backend Monitoring Implementation

## Critical Constraints

### DO NOT Modify These Files (Core Functionality)

- `api/providers/*.py` - Keep all existing providers unchanged
- `api/scripture/*.py` - Keep scripture models/repository unchanged
- `scripts/create_embeddings.py` - Keep existing embedding scripts
- `scripts/create_azure_embeddings.py` - Keep Azure embedding script
- `scripts/load_bible.py` - Keep Bible loading script unchanged
- `deployment/*.tf` - Keep Terraform infrastructure unchanged (except adding new env vars)

### DO NOT Change Defaults

- `embedding_provider` default must remain `"ollama"`
- `embedding_model` default must remain `"mxbai-embed-large"`
- `embedding_dimensions` default must remain `1024`
- `llm_provider` default must remain `"ollama"`
- Existing API endpoint paths must not change
- Existing response formats must remain backward compatible

### DO NOT Delete

- Any existing provider implementations
- Any existing configuration options
- Any existing API endpoints
- Any existing log statements
- Any existing health check logic

### Performance Constraints

- Metrics collection must add <1ms overhead per request
- Logging must not block request handling
- Health checks must complete within 5 seconds
- Middleware must be non-blocking and async-safe

### Security Constraints

- NEVER log sensitive data:
  - API keys, passwords, tokens
  - Full user messages (log lengths only)
  - Database connection strings
  - Personal email addresses
- Request ID must be UUID format (not sequential)
- `/metrics` endpoint should be protected or rate-limited in production

## Required Validations

### Before Any Code Changes

1. Run `make lint` - must pass
2. Run `make test-backend` - must pass
3. Run `make test-frontend` - must pass

### Before Committing

1. Verify all existing tests still pass
2. Verify app starts with default config: `cd api && uvicorn main:app`
3. Verify existing endpoints still work: `/health`, `/api/v1/chat`, `/api/v1/scripture/search`
4. Verify new monitoring features are opt-in (don't break existing deployments)
5. No changes to files in the "DO NOT Modify" list

## Git Safety

- Create commits with descriptive messages
- Create a new feature branch (e.g., `feature/backend-monitoring`)
- DO NOT force push
- DO NOT modify git history
- DO NOT commit secrets or API keys
- Add new sensitive env vars to `.env.example` with placeholder values

## File Creation Rules

### New Files Allowed

- `api/middleware/__init__.py` - Middleware module init
- `api/middleware/request_id.py` - Request ID middleware
- `api/utils/metrics.py` - Prometheus metrics
- `api/routes/health.py` - Enhanced health endpoints (if separating from main.py)
- `api/tests/test_monitoring.py` - Monitoring tests
- `api/tests/test_metrics.py` - Metrics tests
- `api/tests/test_request_id.py` - Request ID middleware tests

### Modifications Allowed

- `api/main.py` - Register middleware and new routes
- `api/utils/logging_config.py` - Add JSON formatter, request context
- `api/config.py` - Add new monitoring configuration options
- `api/chat/service.py` - Add metrics instrumentation
- `api/routes/chat.py` - Add request/response logging
- `api/routes/scripture.py` - Add request/response logging
- `api/routes/feedback.py` - Add metrics for feedback
- `api/requirements.txt` - ADD dependencies (don't remove existing)
- `api/.env.example` - Document new configuration options

## Implementation Guidelines

### Logging Best Practices

- Use structured logging with consistent field names
- Always include `request_id` in log context
- Use appropriate log levels:
  - DEBUG: Detailed diagnostic info
  - INFO: Normal operational messages
  - WARNING: Potential issues, graceful degradation
  - ERROR: Errors that affect single request
  - CRITICAL: System-wide failures
- Avoid logging at DEBUG level in hot paths

### Metrics Best Practices

- Use descriptive metric names with namespace: `bible_chat_*`
- Include relevant labels but avoid high cardinality
- Use Histogram for latencies, Counter for totals, Gauge for current state
- Document all metrics with help text

### Middleware Best Practices

- Keep middleware lightweight
- Use async where possible
- Handle exceptions gracefully
- Don't modify request/response content (only add headers/context)

## Testing Protocol

1. After each implementation step, run:

   ```bash
   make lint && make test-backend
   ```

2. If any check fails, fix the issue before proceeding

3. Create tests for new functionality:
   - Test middleware adds request ID
   - Test JSON log format
   - Test metrics increment
   - Test health checks

4. Performance testing (manual):
   - Verify no significant latency increase
   - Check memory usage with metrics enabled

## Error Handling

- If tests fail after changes, revert and investigate
- If type checking fails, fix type annotations
- If linting fails, run `make format` and re-check
- DO NOT skip or disable tests to make them pass
- DO NOT catch and silence exceptions in monitoring code

## Backward Compatibility

- New features must be opt-in via environment variables
- Default behavior must match current production
- Existing API contracts must not change
- Health endpoint must maintain current response format (can extend but not change)

## Dependencies

### Allowed New Dependencies

- `prometheus-client` - For Prometheus metrics
- `python-json-logger` - For structured JSON logging

### Dependency Guidelines

- Pin versions in requirements.txt
- Check for security vulnerabilities before adding
- Prefer well-maintained, widely-used packages
- No dependencies with restrictive licenses

## Rollout Strategy

1. Implement Phase 1 (Logging) first - lowest risk
2. Deploy to staging and verify logs appear correctly
3. Implement Phase 2 (Metrics) - medium risk
4. Deploy to staging and verify Prometheus scraping works
5. Implement Phase 3+ only after Phases 1-2 are stable
