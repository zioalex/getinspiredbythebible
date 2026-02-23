# Product Backlog

Prioritized list of user stories and features for Get Inspired by the Bible.

**Last Updated:** 2026-02-23

---

## Legend

- **Priority:** P0 (Critical/Blocker), P1 (High), P2 (Medium), P3 (Low)
- **Status:** 🎯 Todo, 🚧 In Progress, ✅ Done, ❌ Cancelled
- **Size:** S (< 4 hrs), M (1-2 days), L (3-5 days), XL (1-2 weeks)

---

## P0 - Critical (Ship Now)

### ✅ BITB-001: Fix Turnstile 403 Errors on Example Sentences

**Status:** ✅ Done (PR #171 merged 2026-02-23, deploying to production)
**Size:** S
**Completed:** 2026-02-23

**As a** new user visiting the app for the first time,
**I want** to click example sentences and get immediate responses,
**so that** I can quickly understand what the app does without frustration.

**Acceptance Criteria:**

- [x] Example sentence buttons are disabled until Turnstile is ready
- [x] Users see "Preparing secure connection..." message while waiting
- [x] No 403 errors when clicking examples after page load
- [x] Unit tests verify buttons are disabled when `turnstileEnabled && !turnstileReady`
- [x] E2E tests verify suggested prompts are present and clickable

**Tech Constraints:**

- Must work with existing Cloudflare Turnstile integration
- Frontend-only fix (no backend changes needed)

**Out of Scope:**

- Changing Turnstile provider or configuration
- Adding retry logic for failed Turnstile challenges

**PR:** #171 (`fix/turnstile-ready-check`) - Merged
**Tracking Doc:** `docs/DONE/PR171-turnstile-ready-fix.md`

---

## P1 - High Priority (Next Sprint)

### 🚧 BITB-002: Sync Conflicted PRs with Main

**Status:** 🚧 In Progress (PR #171 merged, ready to start)
**Size:** M

**As a** developer,
**I want** all open PRs to be conflict-free and up-to-date with main,
**so that** we can review and merge them without manual intervention.

**Acceptance Criteria:**

- [ ] PR #167 (ESLint 9) rebased on latest main, conflicts resolved
- [ ] PR #168 (Secrets scan CI) rebased on latest main, conflicts resolved
- [ ] PR #169 (OWASP dependency check) rebased on latest main, conflicts resolved
- [ ] PR #170 (APK security flags) rebased on latest main, conflicts resolved
- [ ] All rebased PRs pass CI checks
- [ ] Tracking document moved to `docs/DONE/`

**Tech Constraints:**

- Must maintain git history (use rebase, not merge)
- Must preserve existing commit messages and authorship
- Must run `make pre-commit` before pushing

**Dependencies:**

- ✅ PR #171 merged (unblocked)
- PR #170 depends on PR #169

**Tracking Doc:** `docs/WIP/PR-CONFLICTS-AND-SYNC-PLAN.md`

---

### 🎯 BITB-003: Enable Turnstile Bot Protection on Android

**Status:** 🎯 Todo
**Size:** L

**As a** mobile user,
**I want** the Android app to have the same bot protection as the web app,
**so that** the backend remains secure from abuse.

**Acceptance Criteria:**

- [ ] Cloudflare Turnstile widget integrated in Android chat screen
- [ ] Widget token passed in API request headers (same as web)
- [ ] Backend validates Android tokens same as web tokens
- [ ] UI shows loading state while Turnstile initializes
- [ ] Graceful error handling if Turnstile fails to load
- [ ] E2E tests verify Turnstile flow on Android

**Tech Constraints:**

- Min SDK 26 (existing constraint)
- Must use official Cloudflare Turnstile Android SDK (if available) or WebView fallback
- Must reuse existing backend validation logic (`api/utils/turnstile.py`)

**Out of Scope:**

- Alternative bot protection methods
- Backend changes to Turnstile logic

**Dependencies:**

- Requires: Android app bootstrap (PR #156) already merged ✅

**Tracking Doc:** `docs/WIP/android-app.md`

---

### 🎯 BITB-004: Add Database Migration Framework (Alembic)

**Status:** 🎯 Todo
**Size:** L

**As a** developer,
**I want** a version-controlled database migration system,
**so that** schema changes are tracked, reversible, and safely deployed.

**Acceptance Criteria:**

- [ ] Alembic installed and configured
- [ ] Initial migration created from current schema
- [ ] Migration runs successfully on fresh database
- [ ] Rollback tested and working
- [ ] CI runs migration check before deploying
- [ ] Documentation updated with migration workflow

**Tech Constraints:**

- Must work with existing SQLAlchemy models
- Must work with asyncpg connection pool
- Must support zero-downtime deployments (future-proofing)

**Out of Scope:**

- Converting existing production database (manual one-time task)
- Auto-generated migrations from model changes (can be added later)

**Related:** TASKS.md #1.5

---

### 🎯 BITB-005: Make PostgreSQL Database Private (Azure)

**Status:** 🎯 Todo
**Size:** M

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

---

## P2 - Medium Priority (Backlog)

### 🎯 BITB-006: Add Staging Environment

**Status:** 🎯 Todo
**Size:** L

**As a** product owner,
**I want** a staging environment that mirrors production,
**so that** we can validate changes before they affect real users.

**Acceptance Criteria:**

- [ ] Terraform workspace or separate config for staging
- [ ] Staging environment deployed to Azure with same services as prod
- [ ] Staging uses separate database with test data
- [ ] CI/CD deploys to staging on merge to `main`, production on tag/release
- [ ] Staging URL accessible to team (e.g., `staging.getinspiredbythebible.ai4you.sh`)
- [ ] Documentation includes staging deployment process

**Tech Constraints:**

- Must minimize cost (use lower-tier resources than prod)
- Must share same codebase as production
- Must support Terraform state isolation

**Out of Scope:**

- Automated promotion from staging to production
- Staging database anonymization (can use fresh Bible data)

**Related:** TASKS.md #6.2

---

### 🎯 BITB-007: Improve Embedding Generation Performance

**Status:** 🎯 Todo
**Size:** M

**As a** developer running `create_embeddings.py`,
**I want** embedding generation to be parallelized,
**so that** the 30-60 minute task completes in under 10 minutes.

**Acceptance Criteria:**

- [ ] `embed_batch()` uses `asyncio.gather()` with semaphore
- [ ] Configurable concurrency limit (default: 10)
- [ ] Partial results saved if batch fails mid-way
- [ ] Progress bar shows accurate completion estimate
- [ ] Documentation updated with new timing estimates

**Tech Constraints:**

- Must not overwhelm Ollama server (hence semaphore)
- Must work with existing Ollama provider
- Must handle failures gracefully (no silent data loss)

**Out of Scope:**

- Switching embedding providers
- Caching embeddings (separate story)

**Related:** TASKS.md #1.2

---

### 🎯 BITB-008: Add Request Tracing with Correlation IDs

**Status:** 🎯 Todo
**Size:** S

**As a** developer debugging production issues,
**I want** every request to have a unique trace ID,
**so that** I can follow a single user's request through logs.

**Acceptance Criteria:**

- [ ] Middleware generates UUID for each request
- [ ] `X-Request-ID` header added to all responses
- [ ] Trace ID logged in every log entry for that request
- [ ] Trace ID propagated to database queries (as SQL comment)
- [ ] Documentation includes how to search logs by trace ID

**Tech Constraints:**

- Must work with existing logging configuration
- Must have minimal performance impact
- Must handle both sync and async endpoints

**Out of Scope:**

- Full OpenTelemetry integration (separate story)
- Distributed tracing across services

**Related:** TASKS.md #5.1

---

### 🎯 BITB-009: Refactor SQLAlchemy Models to 2.0 Syntax

**Status:** 🎯 Todo
**Size:** L

**As a** developer,
**I want** SQLAlchemy models to use `Mapped[]` annotations,
**so that** MyPy can type-check database code and we remove `# type: ignore` comments.

**Acceptance Criteria:**

- [ ] All models in `api/scripture/models.py` use `Mapped[]` syntax
- [ ] MyPy suppressions removed from `scripture/*` and `routes/*`
- [ ] All tests pass with no type errors
- [ ] Database queries still work correctly
- [ ] Documentation updated with new model syntax examples

**Tech Constraints:**

- Must maintain compatibility with existing database schema
- Must work with AsyncPG
- Must not break existing queries in `repository.py`

**Out of Scope:**

- Migrating to SQLAlchemy 2.0 declarative base (can use hybrid syntax)
- Rewriting all queries to use new-style syntax

**Related:** TASKS.md #3.3, TECHNICAL_DEBT.md #1

---

## P3 - Low Priority (Future)

### 🎯 BITB-010: Add Blue-Green Deployment

**Status:** 🎯 Todo
**Size:** XL

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

---

### 🎯 BITB-011: Add Frontend Testing Suite

**Status:** 🎯 Todo
**Size:** XL

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

---

### 🎯 BITB-012: Migrate Android App to Production

**Status:** 🎯 Todo (blocked by BITB-003)
**Size:** XL

**As a** mobile user,
**I want** to download the app from Google Play Store,
**so that** I can use it on my phone without installing from APK.

**Acceptance Criteria:**

- [ ] Turnstile bot protection enabled (BITB-003)
- [ ] App icon and branding finalized
- [ ] Privacy policy and terms of service written
- [ ] Google Play Store listing created
- [ ] APK signed with production keystore
- [ ] App submitted and approved by Google
- [ ] Post-launch monitoring (crash reports, analytics)

**Tech Constraints:**

- Must meet Google Play Store policies
- Must comply with GDPR/privacy regulations
- Must have Turnstile enabled before public release

**Out of Scope:**

- iOS app (future consideration)
- In-app purchases or monetization

**Dependencies:**

- Blocked by: BITB-003 (Turnstile on Android)

---

## Done (Recent Completions)

### ✅ BITB-000: Bootstrap Android App

**Status:** ✅ Done (PR #156 merged)
**Completed:** 2026-02-20

Basic Android app scaffold with Kotlin, Jetpack Compose, and Ollama embedding provider.
Includes chat interface, verse display, and local-first architecture.

**PR:** #156

---

## Icebox (Ideas for Future Consideration)

- **Multi-Bible Translation Support**: Allow users to select KJV, NIV, ESV, etc.
- **Daily Devotional Notifications**: Push notifications with daily verses
- **Verse Memorization Game**: Gamified scripture memorization feature
- **Community Prayer Requests**: Social feature for sharing prayer needs
- **Audio Bible Integration**: Read-along audio for verses
- **Offline Mode (Web)**: Service worker for offline scripture access
- **Dark Mode**: User preference for light/dark theme (frontend only)
- **Verse Sharing**: Generate shareable images of verses for social media

---

## Notes

- **Source of Truth**: This backlog is the canonical source for prioritized feature work
- **Technical Debt**: See `docs/TECHNICAL_DEBT.md` for engineering-focused items
- **Tasks**: See `docs/TASKS.md` for detailed technical improvements and quick wins
- **Tracking**: Active PRs tracked in `docs/WIP/PR-*.md` files
