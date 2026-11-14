---
id: BITB-011
status: todo
priority: P3
size: XL
rank: 230
---

# BITB-011: Add Frontend Testing Suite

**As a** developer,
**I want** comprehensive frontend tests,
**so that** UI changes don't break existing functionality.

**Acceptance Criteria:**

- [ ] Vitest configured for unit tests
- [ ] React Testing Library tests for all major components
- [ ] Playwright E2E tests for critical user flows (chat, verse lookup, language switching)
- [ ] CI runs frontend tests and enforces 80%+ coverage
- [ ] Documentation includes testing guidelines

**Tech Constraints:**

- Must work with Next.js App Router
- Must support i18n testing (multiple locales)
- Must mock API calls for unit tests

**Out of Scope:**

- Visual regression testing
- Performance testing

**Related:** TECHNICAL_DEBT.md #2, TASKS.md #4.2
