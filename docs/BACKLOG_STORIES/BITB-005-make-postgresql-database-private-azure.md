---
id: BITB-005
status: todo
priority: P1
size: M
rank: 810
---

# BITB-005: Make PostgreSQL Database Private (Azure)

**As a** security-conscious operator,
**I want** the production database to be inaccessible from the public internet,
**so that** we reduce attack surface and comply with security best practices.

**Acceptance Criteria:**

- [ ] Azure Private Endpoint configured for PostgreSQL
- [ ] `public_network_access_enabled = false` in Terraform
- [ ] Backend container can still connect via VNet
- [ ] Local development unaffected (uses localhost or Azure firewall exception)
- [ ] Terraform plan reviewed before apply
- [ ] Deployment tested in staging (if available) before production

**Tech Constraints:**

- Must work with Azure Container Apps networking
- Must not break existing CI/CD pipeline
- Requires Azure VNet integration for Container Apps

**Out of Scope:**

- Setting up staging environment (separate story)
- Database encryption at rest (already enabled)

**Related:** TASKS.md #2.1 (Critical security issue)
