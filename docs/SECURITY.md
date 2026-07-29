# Security Architecture

This document describes the security measures implemented to protect the Vox Quieta API from abuse.

## Overview

The application implements a layered security approach:

```text
┌─────────────────────────────────────────────────────────────┐
│                    Cloudflare Edge                          │
│  • DDoS Protection                                          │
│  • Bot Fight Mode                                           │
│  • WAF Rules                                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Cloudflare Turnstile                        │
│  • Invisible bot detection                                  │
│  • No CAPTCHAs or puzzles                                   │
│  • Token verification on API calls                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend API                               │
│  • Rate limiting (per-IP, per-session)                      │
│  • Content filtering (profanity, spam, URLs)                │
│  • Input validation (length, format)                        │
└─────────────────────────────────────────────────────────────┘
```

## Cloudflare Turnstile

Turnstile is an invisible CAPTCHA alternative that verifies visitors are human without user friction.

### How It Works

1. **Frontend loads Turnstile widget** (invisible mode)
2. **Browser runs silent challenges** (proof-of-work, behavioral analysis)
3. **Token generated** for valid browsers
4. **Token sent with API requests** in `X-Turnstile-Token` header
5. **Backend verifies token** with Cloudflare API

### Setup Instructions

1. **Create Turnstile Widget**
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com/?to=/:account/turnstile)
   - Create a new widget with "Invisible" mode
   - Note the **Site Key** (public) and **Secret Key** (private)

2. **Configure Backend**

   ```bash
   # In api/.env
   TURNSTILE_ENABLED=true
   TURNSTILE_SECRET_KEY=0x...your-secret-key...
   TURNSTILE_SITE_KEY=0x...your-site-key...
   ```

3. **Deploy**
   - Backend will start verifying tokens on protected endpoints
   - Frontend automatically fetches site key from `/config` endpoint

### Test Keys (Development)

For local development, use Cloudflare's test keys:

| Key Type | Value | Behavior |
|----------|-------|----------|
| Site Key | `1x00000000000000000000AA` | Always passes (invisible) |
| Secret Key | `1x0000000000000000000000000000000AA` | Always passes |
| Secret Key | `2x0000000000000000000000000000000AA` | Always fails |
| Secret Key | `3x0000000000000000000000000000000AA` | Forces interactive |

### Protected Endpoints

Turnstile verification is required for:

- `POST /api/v1/chat` - Chat messages
- `POST /api/v1/chat/stream` - Streaming chat
- `POST /api/v1/feedback` - Feedback submission
- `POST /api/v1/feedback/contact` - Contact form
- `POST /api/v1/church/search` - Church finder

Skipped endpoints (no verification needed):

- `GET /health` - Health checks
- `GET /docs` - API documentation
- `GET /config` - Configuration (includes site key)
- `GET /` - Root info

### Error Responses

When Turnstile verification fails:

```json
{
  "error": "Bot verification required",
  "message": "Please complete the security check",
  "code": "TURNSTILE_REQUIRED"
}
```

```json
{
  "error": "Bot verification failed",
  "message": "Invalid token",
  "code": "TURNSTILE_FAILED"
}
```

### Fail-Open Behavior

The implementation uses **fail-open** for availability:

- If Cloudflare API times out → request allowed
- If Cloudflare API returns HTTP error → request allowed
- This prevents Cloudflare outages from breaking the app

## Rate Limiting

Rate limiting prevents abuse by restricting request frequency.

### Limits

| Scope | Default | Configuration |
|-------|---------|---------------|
| Per IP/minute | 20 | `RATE_LIMIT_REQUESTS_PER_MINUTE` |
| Per session/minute | 10 | `RATE_LIMIT_REQUESTS_PER_SESSION_MINUTE` |
| Session lifetime | 100 | `RATE_LIMIT_SESSION_MAX_REQUESTS` |

**Error Response (429):**

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

## Content Filtering

Content filtering blocks inappropriate messages.

### Filters

| Filter | Default | Configuration |
|--------|---------|---------------|
| Profanity | Enabled | `CONTENT_FILTER_BLOCK_PROFANITY` |
| Spam (repeated chars) | Enabled | `CONTENT_FILTER_BLOCK_SPAM` |
| URLs | Blocked | `CONTENT_FILTER_MAX_URLS=0` |
| Max repeated chars | 5 | `CONTENT_FILTER_MAX_REPEATED_CHARS` |

**Error Response (400):**

```json
{
  "error": "Message blocked",
  "message": "Message contains inappropriate language"
}
```

## Input Validation

All inputs are validated before processing.

### Message Limits

| Constraint | Value | Configuration |
|------------|-------|---------------|
| Max length | 500 chars | `MAX_MESSAGE_LENGTH` |
| Min length | 1 char | Hardcoded |
| Session ID format | Alphanumeric + `-_` | Regex pattern |
| Session ID max length | 64 chars | Hardcoded |

## CORS Configuration

Cross-Origin Resource Sharing is configured to only allow trusted origins.

### Allowed Origins

- `http://localhost:3000` / `http://127.0.0.1:3000` (development)
- `http://localhost:3001` / `http://127.0.0.1:3001` (development)
- `https://voxquieta.org` (production, configurable via `PRODUCTION_FRONTEND_URL`)
- Additional origins via `CORS_ORIGINS` environment variable

## Cloudflare Additional Protection

Enable these in your Cloudflare dashboard for extra protection:

1. **Bot Fight Mode** (Free)
   - Security → Bots → Bot Fight Mode → On

2. **Rate Limiting Rules** (Free tier: 1 rule)
   - Security → WAF → Rate limiting rules
   - Example: 100 requests per 10 seconds per IP

3. **Firewall Rules** (Free tier: 5 rules)
   - Block known bad actors
   - Challenge suspicious traffic

## Environment Variables Summary

```bash
# Turnstile (Bot Protection)
TURNSTILE_ENABLED=true
TURNSTILE_SECRET_KEY=0x...
TURNSTILE_SITE_KEY=0x...
TURNSTILE_SKIP_PATHS=/health,/docs,/openapi.json,/config,/

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=20
RATE_LIMIT_REQUESTS_PER_SESSION_MINUTE=10
RATE_LIMIT_SESSION_MAX_REQUESTS=100

# Content Filtering
CONTENT_FILTER_ENABLED=true
CONTENT_FILTER_BLOCK_PROFANITY=true
CONTENT_FILTER_BLOCK_SPAM=true
CONTENT_FILTER_MAX_REPEATED_CHARS=5
CONTENT_FILTER_MAX_URLS=0

# Input Limits
MAX_MESSAGE_LENGTH=500

# CORS
CORS_ORIGINS=https://custom-domain.com

# Logging
SECURITY_LOG_VIOLATIONS=true
```

## Monitoring

Security violations are logged with the following format:

```json
{
  "level": "WARNING",
  "message": "Security violation detected",
  "violation_type": "rate_limit_ip",
  "ip_address": "x.x.x.x",
  "session_id": "...",
  "details": "IP rate limit exceeded"
}
```

Monitor for high violation rates which may indicate an attack.

## Future Improvements

Documented in `docs/task.md`:

- API key authentication for additional layer
- Session-based tracking with CAPTCHA on limits
- Enhanced Cloudflare WAF rules
