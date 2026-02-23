# Product Roadmap

High-level planning for Get Inspired by the Bible - organized into Now / Next / Later / Icebox.

**Last Updated:** 2026-02-23

---

## Vision

Get Inspired by the Bible helps people find spiritual encouragement and relevant
scripture based on their life situations through:

- **Natural conversation**: Ask questions in your own words, get biblically-grounded responses
- **Semantic scripture search**: Find verses by meaning, not just keywords
- **Multi-platform access**: Web app (live), Android app (in development)
- **Privacy-first**: No user tracking, minimal data collection, open source

---

## Now (Current Focus - Feb 2026)

### Theme: Stability & Security

Focus on fixing critical bugs, securing the platform, and cleaning up technical debt
from the initial launch.

### M1–M2 Milestones

#### 🚀 M1: Production Stability (In Progress)

**Target:** End of Feb 2026

**Goals:**

- ✅ Fix Turnstile 403 errors on web app (PR #171)
- 🚧 Sync all open PRs with main (PR #167, #168, #169, #170)
- 🎯 Enable Turnstile on Android app (BITB-003)
- 🎯 Secure database from public internet (BITB-005)

**Success Metrics:**

- Zero user-reported 403 errors on web app
- All open PRs merged or closed
- Android app ready for internal testing with bot protection
- PostgreSQL accessible only via Azure VNet

**User Value:**

- Web users get immediate, error-free responses
- Mobile users get secure, bot-protected experience
- Infrastructure hardened against attacks

---

#### 🔧 M2: Developer Experience (Next Up)

**Target:** Mid-March 2026

**Goals:**

- 🎯 Add database migration framework (BITB-004)
- 🎯 Add request tracing with correlation IDs (BITB-008)
- 🎯 Improve embedding generation performance (BITB-007)

**Success Metrics:**

- Schema changes deployed via Alembic migrations
- All logs include request trace IDs
- Embedding generation completes in <10 minutes (down from 30-60 min)

**User Value:**

- Faster feature delivery (easier database changes)
- Better support (can trace user issues through logs)
- Faster data updates (improved embedding script)

---

## Next (Upcoming Quarter - Q2 2026)

### Theme: Quality & Testing

Build confidence in the codebase with comprehensive testing and improve code quality.

### M3–M4 Milestones

#### 🧪 M3: Testing & Quality

**Target:** End of Q2 2026

**Goals:**

- 🎯 Add frontend testing suite (BITB-011)
- 🎯 Refactor SQLAlchemy models to 2.0 syntax (BITB-009)
- 🎯 Add staging environment (BITB-006)

**Success Metrics:**

- 80%+ frontend test coverage
- Zero MyPy suppressions in scripture/*and routes/*
- Staging environment deployed and used for all pre-production validation

**User Value:**

- Fewer UI bugs in production
- Faster, safer feature releases
- More reliable service

---

#### 📱 M4: Android Production Launch

**Target:** End of Q2 2026

**Goals:**

- 🎯 Complete Android app (BITB-012)
- 🎯 Submit to Google Play Store
- 🎯 Public beta launch

**Dependencies:**

- M1 must be complete (Turnstile on Android)
- Privacy policy and terms of service written
- App icon and branding finalized

**Success Metrics:**

- App approved by Google Play Store
- 100+ beta users onboarded
- <5% crash rate in production
- 4+ star rating on Play Store

**User Value:**

- Mobile-native experience for Android users
- Offline-capable scripture search (Ollama embeddings on-device)
- Faster, more responsive than web app

---

## Later (Future - Q3 2026 and Beyond)

### Theme: Scale & Features

Expand capabilities, improve performance, and add user-requested features.

### M5–M6 Milestones

#### 🚀 M5: Scale & Performance

**Timeframe:** Q3 2026

**Goals:**

- 🎯 Add blue-green deployment (BITB-010)
- 🎯 Add OpenTelemetry metrics and APM (TASKS.md #5.2)
- 🎯 Add alerting for operational metrics (TASKS.md #5.3)
- 🎯 Optimize API response times (target: <500ms p95)

**Success Metrics:**

- Zero-downtime deployments
- Comprehensive dashboards for all services
- Alerts catch issues before users report them
- p95 API latency <500ms (down from current ~1-2s)

**User Value:**

- Uninterrupted service during updates
- Proactive issue detection and resolution
- Faster responses

---

#### 🌍 M6: Multi-Bible Translation Support

**Timeframe:** Q4 2026

**Goals:**

- Support multiple English translations (KJV, NIV, ESV, NKJV)
- User preference for default translation
- Parallel verse display (compare translations)

**Success Metrics:**

- 3+ translations available
- User can switch translation in <2 clicks
- Semantic search works across all translations

**User Value:**

- Read scripture in their preferred translation
- Compare translations side-by-side
- Deeper biblical study

---

## Icebox (Ideas - No Timeline)

Features and ideas worth considering but not yet prioritized:

### User Features

- **Daily Devotional Notifications**: Push notifications with daily verses
- **Verse Memorization Game**: Gamified scripture memorization
- **Community Prayer Requests**: Social feature for sharing prayer needs
- **Audio Bible Integration**: Read-along audio for verses
- **Offline Mode (Web)**: Service worker for offline scripture access
- **Dark Mode**: User preference for light/dark theme
- **Verse Sharing**: Generate shareable images of verses for social media
- **Bookmarks & Favorites**: Save verses for later
- **Reading Plans**: Guided plans (e.g., "Read the Bible in a Year")

### Platform Expansion

- **iOS App**: Native iOS app with same features as Android
- **Desktop App**: Electron or Tauri app for Windows/Mac/Linux
- **Browser Extension**: Quick scripture lookup from any webpage
- **API for Third Parties**: Public API for scripture search

### Infrastructure

- **Multi-Region Deployment**: Deploy to Europe, Asia for lower latency
- **CDN for Static Assets**: Cloudflare CDN for frontend
- **Database Read Replicas**: Scale read-heavy workloads
- **Elasticsearch for Full-Text Search**: Faster, more powerful text search

### Monetization (Future Consideration)

- **Premium Features**: Advanced search, unlimited history, ad-free
- **Church Partnerships**: White-label version for churches
- **API Licensing**: Charge for API access beyond free tier

---

## Dependencies & Blockers

### Current Blockers

- **M1 (Production Stability)**: PR #171 awaiting human approval and merge
- **M4 (Android Launch)**: Blocked by M1 (Turnstile requirement)

### Technical Debt Preventing Scale

See `docs/TECHNICAL_DEBT.md` for full list. Key items:

- SQLAlchemy models (blocks type-safe database code)
- Frontend testing (blocks confident UI changes)
- Database migration framework (blocks schema evolution)

### Infrastructure Limitations

- **Ollama Dependency**: Embedding generation requires Ollama, limiting deployment options
  - **Mitigation**: Implement OpenAI embeddings provider (tracked in TECHNICAL_DEBT.md)
- **Single Region**: All infrastructure in one Azure region (no failover)
  - **Mitigation**: M6 (multi-region deployment)

---

## Release Strategy

### Web App (Live Production)

- **Deployment**: Automatic on merge to `main` via GitHub Actions
- **Rollback**: Manual via Azure Portal (revert to previous container revision)
- **Versioning**: Not yet formalized (tracked by git commits)

### Android App (Pre-Production)

- **Current State**: Bootstrap merged (PR #156), not yet on Play Store
- **Target**: Public beta in Q2 2026 (M4)
- **Versioning**: Semantic versioning (1.0.0 for first Play Store release)

---

## Success Metrics (Product-Level)

### User Engagement

- **Target:** 1000+ weekly active users by end of Q2 2026
- **Target:** 70%+ user retention (return within 7 days)
- **Target:** Average 3+ messages per session

### Quality

- **Target:** 99.9% uptime (web app)
- **Target:** <1% error rate on API endpoints
- **Target:** <5% crash rate (Android app)

### Performance

- **Target:** <2s time to first response
- **Target:** <500ms p95 API latency

### User Satisfaction

- **Target:** 4+ star rating on Play Store
- **Target:** <10% bounce rate on web app
- **Target:** Positive user feedback (qualitative)

---

## How This Roadmap Is Maintained

1. **Product Owner** updates this roadmap monthly
2. **Backlog** (`docs/BACKLOG.md`) contains detailed user stories
3. **Technical Debt** (`docs/TECHNICAL_DEBT.md`) tracks engineering improvements
4. **Tasks** (`docs/TASKS.md`) contains tactical to-do items
5. **WIP Tracking** (`docs/WIP/`) tracks active PR work

**Next Review:** End of March 2026
