# Task: Add Production Monitoring to Backend

Implement comprehensive monitoring and observability for the backend API to enable proactive issue
detection, faster debugging, and better understanding of application health in production.

## Goal

Enable the team to:

- Detect and diagnose production issues quickly
- Understand application performance and bottlenecks
- Track business metrics and user experience
- Receive alerts before users are impacted

## Current State

The application has basic logging to stdout but lacks:

- Centralized log aggregation
- Metrics collection (request rates, latencies, error rates)
- Request tracing with correlation IDs
- Alerting for anomalies
- Dashboard for visualizing system health

## Implementation Steps

### Phase 1: Structured Logging with Correlation IDs (Priority: High)

#### 1.1 Add Request ID Middleware

Create `api/middleware/request_id.py`:

- Generate unique request ID for each incoming request
- Add request ID to all log messages automatically
- Return request ID in response headers (`X-Request-ID`)

```python
# Example structure
class RequestIDMiddleware:
    async def __call__(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Store in context for logging
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

#### 1.2 Enhance Logging to JSON Format

Update `api/utils/logging_config.py`:

- Add JSON formatter option for production
- Include request_id in all log entries
- Add configurable formatter (JSON for prod, readable for dev)
- Environment variable: `LOG_FORMAT=json|text`

#### 1.3 Add Request/Response Logging

Create request logging middleware:

- Log incoming requests (method, path, query params)
- Log response status codes and timing
- Redact sensitive data (auth headers, passwords)
- Log request body size (not content)

### Phase 2: Metrics Collection (Priority: High)

#### 2.1 Add Prometheus Metrics

Create `api/utils/metrics.py`:

- HTTP request counter (by method, path, status)
- Request latency histogram
- Active requests gauge
- LLM provider latency histogram
- Scripture search latency histogram
- Database query count and latency

```python
# Key metrics to track
http_requests_total = Counter('http_requests_total', 'Total HTTP requests', ['method', 'path', 'status'])
http_request_duration_seconds = Histogram('http_request_duration_seconds', 'HTTP request latency')
llm_request_duration_seconds = Histogram('llm_request_duration_seconds', 'LLM API latency', ['provider'])
scripture_search_duration_seconds = Histogram('scripture_search_duration_seconds', 'Scripture search latency')
active_requests = Gauge('active_requests', 'Number of requests in progress')
```

#### 2.2 Add Metrics Endpoint

Add `/metrics` endpoint:

- Expose Prometheus-compatible metrics
- Include default Python process metrics (memory, CPU, GC)

#### 2.3 Instrument Key Services

Add timing decorators/context managers to:

- `ChatService.chat()` - total, search, LLM breakdown
- `ScriptureSearchService.search()` - embedding, query times
- Database queries (via SQLAlchemy events)

### Phase 3: Health Check Enhancements (Priority: Medium)

#### 3.1 Expand Health Endpoint

Enhance `/health` endpoint:

- Database connectivity check (simple query)
- Embedding provider check (generate test embedding)
- LLM provider check (small completion)
- Memory usage check (warning threshold)
- Return detailed component status

```json
{
  "status": "healthy",
  "components": {
    "database": {"status": "healthy", "latency_ms": 5},
    "llm": {"status": "healthy", "provider": "ollama", "latency_ms": 150},
    "embedding": {"status": "healthy", "provider": "ollama", "latency_ms": 50}
  },
  "memory": {"used_mb": 256, "limit_mb": 512, "percent": 50}
}
```

#### 3.2 Add Readiness/Liveness Endpoints

- `/health/live` - Is the process running? (fast, always succeeds if app started)
- `/health/ready` - Can the app serve requests? (checks dependencies)

### Phase 4: Error Tracking (Priority: Medium)

#### 4.1 Structured Error Logging

Enhance error logging to include:

- Error type/category
- Stack trace (in development)
- Request context (request_id, path, user session)
- Environment info (version, deployment)

#### 4.2 Error Aggregation Preparation

Prepare for error tracking services:

- Create error reporting interface
- Support for Sentry, Rollbar, or Azure Application Insights
- Environment variable: `ERROR_TRACKING_DSN`

### Phase 5: Business Metrics (Priority: Low)

#### 5.1 Add Custom Application Metrics

Track business-relevant metrics:

- `chat_messages_total` - Total chat messages processed
- `feedback_submissions_total` - Feedback by rating type
- `contact_submissions_total` - Contact form submissions
- `scripture_verses_served_total` - Verses returned in responses
- `session_duration_seconds` - How long users engage

#### 5.2 Add Rate Tracking

Track rates and patterns:

- Messages per minute
- Unique sessions per hour
- Error rate over time

## Configuration

New environment variables:

```env
# Logging
LOG_FORMAT=json           # json or text (default: text for dev, json for prod)
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR

# Metrics
METRICS_ENABLED=true     # Enable Prometheus metrics endpoint
METRICS_PATH=/metrics    # Path for metrics endpoint

# Health Checks
HEALTH_CHECK_TIMEOUT=5   # Timeout for dependency checks in seconds

# Error Tracking (optional)
ERROR_TRACKING_DSN=      # Sentry/Rollbar DSN (empty = disabled)
```

## Testing Requirements

### Unit Tests

Create `api/tests/test_monitoring.py`:

- Test request ID generation and propagation
- Test JSON log formatting
- Test metrics increment correctly
- Test health check responses

### Integration Tests

- Verify `/metrics` endpoint returns valid Prometheus format
- Verify `/health` endpoint checks all dependencies
- Verify request ID flows through entire request lifecycle

## File Structure

```text
api/
├── middleware/
│   ├── __init__.py
│   └── request_id.py        # Request ID generation middleware
├── utils/
│   ├── logging_config.py    # Enhanced with JSON format
│   └── metrics.py           # Prometheus metrics (new)
├── routes/
│   └── health.py            # Enhanced health checks (new)
├── tests/
│   └── test_monitoring.py   # Monitoring tests (new)
└── main.py                  # Register middleware and routes
```

## Success Criteria

### Phase 1 (Logging) - COMPLETE

- [x] Every log message includes a request_id
- [x] JSON logging enabled with `LOG_FORMAT=json`
- [x] Request/response logged with timing
- [x] Sensitive data is redacted

### Phase 2 (Metrics) - COMPLETE

- [x] `/metrics` endpoint returns Prometheus format
- [x] HTTP request metrics collected (count, latency)
- [x] LLM and search latencies tracked
- [ ] Metrics visible in Prometheus/Grafana (requires infrastructure setup)

### Phase 3 (Health) - COMPLETE

- [x] `/health` shows component-level status
- [x] `/health/live` and `/health/ready` endpoints work
- [x] Database health verified
- [x] Memory usage included

### Phase 4 (Errors)

- [ ] Structured error logging with context
- [ ] Preparation for error tracking integration
- [ ] Instead of reporting the message straight away add an automatic retry mechanism (max 3 times
  with low delay) and post to a message like "...hold on. I had some trouble..." after 3 retries
  show the messages as you outlined.

### Phase 5 (Business)

- [ ] Custom metrics for chat, feedback, sessions
- [ ] Rate tracking capabilities

## Dependencies

Add to `api/requirements.txt`:

```text
prometheus-client>=0.17.0
python-json-logger>=2.0.0
```

## Out of Scope (Future Work)

- Distributed tracing (OpenTelemetry)
- APM integration (Datadog, New Relic)
- Custom dashboards (Grafana setup)
- Alerting rules (PagerDuty, OpsGenie)
- Log shipping configuration (Fluentd, Logstash)
- Cost tracking and attribution
