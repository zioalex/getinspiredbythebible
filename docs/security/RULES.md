# Security Audit Rules

## Audit Scope

### In Scope

- All Python backend code (`api/`)
- All TypeScript/React frontend code (`frontend/src/`)
- Configuration files (docker-compose, .env handling)
- Database schema and queries
- API endpoints and authentication
- Scripts (`scripts/`)

### Out of Scope

- Third-party dependencies (covered by Dependabot)
- `.venv/` and `node_modules/`
- Build artifacts (`.next/`)

## OWASP Top 10 Checklist

1. **A01:2021 - Broken Access Control**
2. **A02:2021 - Cryptographic Failures**
3. **A03:2021 - Injection** (SQL, Command, XSS)
4. **A04:2021 - Insecure Design**
5. **A05:2021 - Security Misconfiguration**
6. **A06:2021 - Vulnerable Components** (Dependabot handles)
7. **A07:2021 - Authentication Failures**
8. **A08:2021 - Software/Data Integrity Failures**
9. **A09:2021 - Security Logging & Monitoring**
10. **A10:2021 - Server-Side Request Forgery (SSRF)**

## Severity Levels

- **CRITICAL**: Immediate exploitation possible, data breach risk
- **HIGH**: Significant security impact, should fix before deploy
- **MEDIUM**: Security weakness, fix in next sprint
- **LOW**: Minor issue, fix when convenient
- **INFO**: Best practice recommendation

## Code Patterns to Check

### Python (Backend)

- [ ] SQL queries - parameterized vs string interpolation
- [ ] User input validation (Pydantic models, validators)
- [ ] File operations - path traversal
- [ ] Command execution - subprocess, os.system
- [ ] Secrets handling - env vars, not hardcoded
- [ ] CORS configuration
- [ ] Rate limiting
- [ ] Error handling - no stack traces to users
- [ ] Logging - no sensitive data logged

### TypeScript (Frontend)

- [ ] XSS - dangerouslySetInnerHTML, innerHTML
- [ ] User input sanitization
- [ ] API calls - proper error handling
- [ ] Sensitive data in localStorage/sessionStorage
- [ ] HTTPS enforcement
- [ ] Content Security Policy

### Configuration

- [ ] Docker security (non-root users, secrets)
- [ ] Environment variable handling
- [ ] Database credentials
- [ ] API keys exposure
- [ ] Debug mode in production

## Tools to Use

1. **Bandit** - Python security linter (already in pre-commit)
2. **Safety** - Python dependency vulnerabilities
3. **npm audit** - Node.js vulnerabilities
4. **Manual code review** - Logic flaws, design issues

## Preconditions for Closing Issues

Before marking any security issue as FIXED:

1. **Never Push Directly to Main**: All changes must go through a Pull Request.
   Create a feature branch, push changes, and open a PR for review.
2. **CI Workflow Must Pass**: The `CI/CD - Test Application` workflow must complete
   successfully on the PR branch before merging.
3. **Create Separate PRs**: Each security fix should be in its own PR for clear tracking
   and easy rollback if needed.
4. **Merge Order**: Document any dependencies between fixes. If fix B depends on fix A,
   merge A first.
5. **Verification**: After merge, verify the fix is working in the deployed environment
   if applicable.

## Reporting Format

For each finding:

```markdown
### [SEVERITY] Title

**File:** path/to/file.py:line_number
**Category:** OWASP category
**Description:** What the issue is
**Impact:** What could happen if exploited
**Recommendation:** How to fix it
**Code:** (include vulnerable code snippet)
```
