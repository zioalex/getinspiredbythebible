---
id: BITB-010
status: todo
priority: P3
size: XL
rank: 220
---

# BITB-010: Add Blue-Green Deployment

**As a** product owner,
**I want** zero-downtime deployments with instant rollback,
**so that** users never experience service interruptions during updates.

**Acceptance Criteria:**

- [ ] Azure Container Apps revisions configured for traffic splitting
- [ ] Deployment creates new revision, tests it, then switches traffic
- [ ] Rollback script can instantly revert to previous revision
- [ ] Health checks validate new revision before traffic switch
- [ ] Documentation includes deployment and rollback procedures

**Tech Constraints:**

- Must work with existing Azure Container Apps setup
- Must support database migrations (may require multi-step deployments)
- Must handle stateful sessions gracefully

**Out of Scope:**

- Canary deployments (can be added later)
- Multi-region deployments

**Related:** TASKS.md #6.1
