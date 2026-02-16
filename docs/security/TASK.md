# Security Audit Task Tracker

**Started:** 2026-01-29
**Status:** COMPLETE
**Last Updated:** 2026-01-29 (after anti-abuse merge)

## Merge Status

- ✅ `feature/monitoring-phase3-health` - MERGED to main
- ✅ `feature/anti-abuse-security` - MERGED to main

## Progress Overview

| Category | Status | Findings |
|----------|--------|----------|
| Input Validation | ✅ COMPLETE | 0 (fixed by anti-abuse merge) |
| SQL Injection | ✅ COMPLETE | 0 (ORM used) |
| Authentication/Authorization | ✅ COMPLETE | 1 Info |
| XSS Prevention | ✅ COMPLETE | 0 (ReactMarkdown safe) |
| SSRF | ✅ COMPLETE | 1 Low (mitigated) |
| Secrets Management | ✅ COMPLETE | 1 Medium |
| Rate Limiting | ✅ COMPLETE | 0 (fixed by anti-abuse merge) |
| CORS Configuration | ✅ COMPLETE | 1 Low |
| Error Handling | ✅ COMPLETE | 0 (fixed) |
| Logging Security | ✅ COMPLETE | 1 Low (PII in logs) |
| Docker Security | ✅ COMPLETE | 0 (good) |
| Dependency Vulnerabilities | ⚠️ ACTION NEEDED | 1 High (Next.js), 1 Critical (dev-only) |

**Legend:** ⬜ PENDING | 🔄 IN PROGRESS | ✅ COMPLETE | ⚠️ ISSUES FOUND

---

## Findings

### Critical (Dev-only)

#### [DEP-CRIT-001] Vitest Remote Code Execution

**Package:** vitest
**Severity:** CRITICAL (but dev-only)
**Alert:** #67
**Description:** Vitest allows Remote Code Execution when accessing a malicious website while Vitest API server is listening
**Impact:** Development environment only - not a production risk
**Recommendation:** Update vitest when fix available
**Status:** ⚠️ OPEN - Dev dependency only

---

### High

#### ~~[HIGH-001] Missing Rate Limiting on API Endpoints~~ ✅ FIXED

**Status:** ✅ FIXED by `feature/anti-abuse-security` merge
**Solution:** `api/utils/rate_limiter.py` implements per-IP and per-session rate limiting

#### ~~[DEP-HIGH-001] python-multipart Arbitrary File Write~~ ✅ FIXED

**Package:** python-multipart
**Severity:** HIGH
**Alert:** #69
**Description:** Arbitrary file write via non-default configuration
**Impact:** Could allow file system writes if multipart parsing is misconfigured
**Solution:** Updated python-multipart 0.0.18 -> 0.0.22 in requirements.txt
**Status:** ✅ FIXED

#### [DEP-HIGH-002] Next.js DoS via Server Components

**Package:** next
**Severity:** HIGH
**Alerts:** #71
**Description:** HTTP request deserialization can lead to DoS when using insecure React Server Components
**Impact:** Frontend denial of service
**Recommendation:** Update Next.js to latest version
**Action:** Run `npm update next` in frontend/
**Status:** ⚠️ OPEN

#### [DEP-HIGH-003] glob CLI Command Injection

**Package:** glob
**Severity:** HIGH
**Alert:** #64
**Description:** Command injection via -c/--cmd with shell:true
**Impact:** Build-time only, not runtime
**Recommendation:** Wait for transitive dependency update or update manually
**Status:** ⚠️ OPEN - Build-time only

---

### Medium

#### ~~[MED-001] Exception Details Exposed to Users~~ ✅ FIXED

**File:** `api/routes/chat.py`, `api/routes/feedback.py`
**Category:** A05:2021 - Security Misconfiguration
**Description:** Exception messages were directly returned to users via `detail=str(e)`,
potentially exposing internal implementation details.
**Solution:** Replaced with generic error messages. Detailed errors are now logged server-side only.
**Status:** ✅ FIXED

#### [MED-002] Debug Mode Enabled by Default

**File:** `api/config.py:18`
**Category:** A05:2021 - Security Misconfiguration
**Description:** `debug: bool = True` is the default setting
**Impact:** Debug mode in production could expose sensitive information through verbose error messages
**Recommendation:** Set `debug: bool = False` as default, require explicit opt-in for development
**Status:** ⚠️ OPEN

#### ~~[MED-003] Missing Input Validation on ChatRequest~~ ✅ FIXED

**Status:** ✅ FIXED by `feature/anti-abuse-security` merge
**Solution:** `api/chat/service.py` now validates message length with `max_length=settings.max_message_length`

#### [MED-004] Hardcoded Default Database Credentials

**File:** `api/config.py:57-59`
**Category:** A07:2021 - Authentication Failures
**Description:** Default database URL contains credentials `bible:bible123`
**Impact:** If .env is not configured, app runs with known default credentials
**Recommendation:**

- Remove default or use placeholder that clearly won't work
- Fail fast if DATABASE_URL not configured
**Status:** ⚠️ OPEN

#### [DEP-MED-001] Next.js Image Optimizer DoS

**Package:** next
**Severity:** MEDIUM
**Alert:** #70
**Description:** Self-hosted applications vulnerable to DoS via Image Optimizer remotePatterns configuration
**Impact:** Frontend denial of service
**Recommendation:** Update Next.js
**Status:** ⚠️ OPEN

#### [DEP-MED-002] esbuild Dev Server Request Spoofing

**Package:** esbuild
**Severity:** MEDIUM
**Alert:** #68
**Description:** Enables any website to send requests to dev server and read response
**Impact:** Development only
**Status:** ⚠️ OPEN - Dev dependency only

---

### Low

#### [LOW-001] CORS Allows HTTP Origins

**File:** `api/main.py:128-140`
**Category:** A05:2021 - Security Misconfiguration
**Description:** CORS configuration includes `http://getinspiredbythebible.ai4you.sh` alongside HTTPS
**Impact:** Allows connections from non-HTTPS origins, potentially enabling MitM attacks
**Recommendation:** Remove HTTP origins, keep only HTTPS for production

```python
allow_origins=[
    "http://localhost:3000",  # OK for dev
    "https://getinspiredbythebible.ai4you.sh",  # Production - HTTPS only
]
```

**Status:** ⚠️ OPEN

#### [LOW-002] Church Finder SSRF Potential (Mitigated)

**File:** `api/routes/church.py:61`
**Category:** A10:2021 - SSRF
**Description:** External API call to `disciplestoday.org` - URL is hardcoded so not user-controllable
**Impact:** Low - URL cannot be changed by users, but external dependency could be compromised
**Status:** ✅ MITIGATED - URL hardcoded, not user-controllable

#### [LOW-003] User Location Logged at INFO Level

**File:** `api/routes/church.py:55,66`
**Category:** Privacy / PII Exposure
**Description:** User-submitted location is logged at INFO level, which may appear in production logs
**Impact:** PII (user location) may be stored in logs
**Recommendation:** Log at DEBUG level only, or hash/anonymize location data
**Status:** ⚠️ OPEN

---

### Info

#### [INFO-001] No Authentication Required

**File:** All API endpoints
**Category:** A01:2021 - Broken Access Control
**Description:** API is publicly accessible without authentication
**Impact:** By design for this application - it's a public Bible chat service
**Recommendation:** Document this as intentional. Consider adding optional API keys for future monetization or abuse tracking
**Status:** ✅ Acceptable - matches application design

---

## Task List

### 1. Input Validation & Injection Prevention

- [x] **1.1** Review `api/routes/chat.py` - chat endpoint input validation ✅ Fixed
- [x] **1.2** Review `api/routes/scripture.py` - scripture search params ✅ OK (uses ORM)
- [x] **1.3** Review `api/routes/feedback.py` - feedback form inputs ⚠️ MED-001
- [x] **1.4** Review `api/routes/church.py` - church finder inputs ✅ OK
- [x] **1.5** Review `api/chat/service.py` - ChatRequest validation ✅ Fixed
- [x] **1.6** Check Pydantic models for proper constraints ✅ Fixed

### 2. SQL Injection

- [x] **2.1** Review `api/scripture/repository.py` - all database queries ✅ Uses SQLAlchemy ORM
- [x] **2.2** Review `api/feedback/repository.py` - feedback queries ✅ Uses SQLAlchemy ORM
- [x] **2.3** Review `scripts/load_bible.py` - raw SQL usage ✅ Parameterized queries
- [x] **2.4** Review `scripts/create_embeddings.py` - raw SQL usage ✅ Parameterized queries
- [x] **2.5** Check SQLAlchemy ORM usage vs raw queries ✅ ORM preferred, raw uses params

### 3. Authentication & Authorization

- [x] **3.1** Check if any endpoints require auth ℹ️ INFO-001 - By design
- [x] **3.2** Review session handling (if any) ✅ No sessions, stateless API
- [x] **3.3** Check API key protection ✅ API keys in env vars
- [x] **3.4** Review rate limiting implementation ✅ Implemented in anti-abuse

### 4. XSS Prevention (Frontend)

- [x] **4.1** Review `frontend/src/app/page.tsx` - user input rendering ✅
- [x] **4.2** Review `frontend/src/components/ChatMessage.tsx` - message rendering ✅ ReactMarkdown
- [x] **4.3** Review `frontend/src/components/VerseCard.tsx` - verse text ✅
- [x] **4.4** Review `frontend/src/components/ContactForm.tsx` - form handling ✅
- [x] **4.5** Check for dangerouslySetInnerHTML usage ✅ Not used

### 5. SSRF (Server-Side Request Forgery)

- [x] **5.1** Review `api/providers/ollama.py` - external HTTP calls ✅ Configurable host
- [x] **5.2** Review `api/providers/openrouter.py` - API calls ✅ Fixed base URL
- [x] **5.3** Review `api/providers/claude.py` - API calls ✅ SDK handles
- [x] **5.4** Review `api/utils/email_service.py` - external calls ✅ Fixed SMTP2GO API
- [x] **5.5** Check if user input controls any URLs ✅ LOW-002 - Mitigated

### 6. Secrets Management

- [x] **6.1** Review `api/config.py` - secrets handling ⚠️ MED-004
- [x] **6.2** Check `.env` files for sensitive defaults ✅ .env.example is clean
- [x] **6.3** Review docker-compose files for secrets ✅ Uses env vars
- [x] **6.4** Check for hardcoded credentials in code ⚠️ MED-004 default DB URL
- [x] **6.5** Verify `.gitignore` excludes sensitive files ✅ .env excluded
- [x] **6.6** Review `.secrets.baseline` for false negatives ✅ In place

### 7. Rate Limiting & DoS Prevention

- [x] **7.1** Review rate limiting config in `api/config.py` ✅ Implemented
- [x] **7.2** Check rate limiting middleware implementation ✅ `api/utils/rate_limiter.py`
- [x] **7.3** Review message length limits ✅ `max_message_length=200`
- [x] **7.4** Check for resource exhaustion vectors ✅ Rate limits in place
- [x] **7.5** Review timeout configurations ✅ Timeouts in place

### 8. CORS Configuration

- [x] **8.1** Review `api/main.py` CORS settings ⚠️ LOW-001
- [x] **8.2** Check allowed origins configuration ✅ Explicit list
- [x] **8.3** Verify credentials handling ✅ allow_credentials=True appropriate

### 9. Error Handling & Information Disclosure

- [x] **9.1** Review error handlers in `api/main.py` ⚠️ MED-001
- [x] **9.2** Check for stack trace exposure ⚠️ MED-001 - str(e) exposed
- [x] **9.3** Review debug mode settings ⚠️ MED-002 - Default True
- [x] **9.4** Check error responses for sensitive info ⚠️ Exception messages exposed

### 10. Logging Security

- [x] **10.1** Review `api/utils/logging_config.py` ✅ Clean config
- [x] **10.2** Check for sensitive data in logs ⚠️ LOW-003 - Location logged
- [x] **10.3** Review log levels for production ✅ Configurable via LOG_LEVEL

### 11. Docker & Infrastructure Security

- [x] **11.1** Review `Dockerfile` for API ✅ Multi-stage, non-root user
- [x] **11.2** Review `Dockerfile` for Frontend ✅ Multi-stage build
- [x] **11.3** Check for non-root users ✅ appuser:appgroup
- [x] **11.4** Review volume mounts ✅ Appropriate
- [x] **11.5** Check network exposure ✅ Explicit port bindings

### 12. Dependency Vulnerabilities

- [x] **12.1** Run `safety check` on Python deps ✅ 0 vulnerabilities
- [x] **12.2** Run `npm audit` on frontend deps ⚠️ See DEP findings
- [x] **12.3** Check Dependabot alerts ⚠️ 6 open (1 critical, 3 high, 2 medium)
- [x] **12.4** Review pinned versions ✅ Versions pinned in requirements.txt

---

## Open Dependabot Alerts Summary

| Alert | Package | Severity | Production Impact | Status |
|-------|---------|----------|-------------------|--------|
| #67 | vitest | CRITICAL | ❌ Dev-only | Open |
| #69 | python-multipart | HIGH | ✅ **Production** | ✅ FIXED |
| #71 | next | HIGH | ✅ **Production** | Open (14.2.35 is latest 14.x) |
| #64 | glob | HIGH | ❌ Build-only | Open |
| #70 | next | MEDIUM | ✅ **Production** | Open (14.2.35 is latest 14.x) |
| #68 | esbuild | MEDIUM | ❌ Dev-only | Open |

**Remaining Action:**

1. ~~Update `python-multipart`~~ ✅ Done
2. Next.js 14.2.35 is already latest patched version in 14.2.x line. Consider upgrade to 15.x for additional fixes.

---

## Files Reviewed

| File | Status | Notes |
|------|--------|-------|
| `api/routes/chat.py` | ⚠️ | Exception details exposed |
| `api/routes/feedback.py` | ⚠️ | Exception details exposed |
| `api/routes/church.py` | ⚠️ | Location logged at INFO level |
| `api/routes/scripture.py` | ✅ | Uses ORM |
| `api/config.py` | ⚠️ | Debug=True default, hardcoded DB creds |
| `api/main.py` | ⚠️ | CORS allows HTTP |
| `api/chat/service.py` | ✅ | Input validation added |
| `api/scripture/repository.py` | ✅ | SQLAlchemy ORM, parameterized |
| `api/feedback/models.py` | ✅ | Pydantic validation present |
| `api/providers/*.py` | ✅ | Good timeout handling |
| `api/utils/security.py` | ✅ | Good - message preview truncated |
| `api/utils/rate_limiter.py` | ✅ | Proper rate limiting |
| `api/utils/logging_config.py` | ✅ | Clean logging config |
| `api/Dockerfile` | ✅ | Multi-stage, non-root user |
| `frontend/src/components/*.tsx` | ✅ | ReactMarkdown (safe) |
| `scripts/load_bible.py` | ✅ | Parameterized SQL |
| `scripts/create_embeddings.py` | ✅ | Parameterized SQL |

---

## Priority Remediation Order

### Immediate (Production Risk)

1. ~~**DEP-HIGH-001** - Update python-multipart~~ ✅ FIXED
2. **DEP-HIGH-002** - Next.js (14.2.35 is latest 14.x; consider 15.x upgrade)
3. ~~**MED-001** - Fix exception detail exposure~~ ✅ FIXED

### Short-term

1. **MED-002** - Change debug default to False
2. **MED-004** - Remove hardcoded default credentials
3. **LOW-001** - Remove HTTP from CORS origins

### Optional/Low Priority

1. **LOW-003** - Move location logging to DEBUG level
2. **DEP-HIGH-003** - glob (build-only, wait for upstream)
3. **DEP-CRIT-001** - vitest (dev-only)
4. **DEP-MED-002** - esbuild (dev-only)

---

## Audit Complete

All code sections have been reviewed. The audit identified:

- **0 Critical** production vulnerabilities in code
- **2 High** priority fixes - ✅ BOTH FIXED (MED-001, DEP-HIGH-001)
- **2 Medium** priority fixes remaining (MED-002, MED-004)
- **3 Low** priority fixes remaining
- **5 Dependabot alerts** remaining (1 production: Next.js)

### Fixed in This Audit

1. ✅ **HIGH-001** - Rate limiting (merged from anti-abuse branch)
2. ✅ **MED-001** - Exception detail exposure (generic error messages)
3. ✅ **MED-003** - Input validation (merged from anti-abuse branch)
4. ✅ **DEP-HIGH-001** - python-multipart updated to 0.0.22
