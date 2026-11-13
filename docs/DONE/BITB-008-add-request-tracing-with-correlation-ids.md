---
id: BITB-008
status: done
priority: P2
size: S
rank: 990
---

# BITB-008: Add Request Tracing with Correlation IDs

**As a** developer debugging production issues,
**I want** every request to have a unique trace ID,
**so that** I can follow a single user's request through logs.

**Acceptance Criteria:**

- [x] Middleware generates UUID for each request (`api/middleware/correlation_id.py`)
- [x] `X-Request-ID` header added to all responses, including error responses
- [x] Trace ID logged in every log entry for that request (`api/utils/logging_config.py`)
- [x] Trace ID propagated to database queries as a SQL comment (`before_cursor_execute` listener
      in `api/scripture/database.py`)
- [x] Documentation includes how to search logs by trace ID (`docs/TROUBLESHOOTING.md`,
      "Tracing a single request by its correlation ID")

**Tech Constraints:**

- Must work with existing logging configuration
- Must have minimal performance impact
- Must handle both sync and async endpoints

**Out of Scope:**

- Full OpenTelemetry integration (separate story)
- Distributed tracing across services

**Related:** TASKS.md #5.1
