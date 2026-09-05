# Usage Tracking

## Current Implementation (Option C)

### Persistent Sessions

The frontend generates a unique session ID on first visit and stores it in
`localStorage`. This ID survives page refreshes and browser restarts, giving
us a stable "user" identifier for DAU/MAU counting without requiring sign-up.

- **`getOrCreateSessionId()`** in `frontend/src/lib/api.ts` — reads or creates
  the persistent ID.
- **"New Chat"** generates a new `conversationId` but keeps the same
  `sessionId`, so we track returning users across conversations.

### Sessions Table

Each chat request upserts a row in the `sessions` table. The table is created
by `scripts/init.sql` on fresh databases and by
`scripts/migrations/008_add_sessions_table.sql` on existing ones (production
predates the table, so only the migration creates it there). It also feeds the
weekly digest email — see [WEEKLY_REPORT.md](WEEKLY_REPORT.md). Columns:

| Column | Type | Purpose |
|--------|------|---------|
| `session_token` | `VARCHAR(64)` | Unique ID from frontend `localStorage` |
| `created_at` | `TIMESTAMPTZ` | First visit |
| `last_activity` | `TIMESTAMPTZ` | Most recent chat message |
| `message_count` | `INTEGER` | Total messages sent |
| `language` | `VARCHAR(10)` | Supported base language from the chat body, falling back to `Accept-Language` |
| `user_agent` | `TEXT` | Trimmed User-Agent header, or `NULL` when blank/missing |
| `is_mobile` | `BOOLEAN` | UA-derived device class; includes mobile browsers and explicitly identified Android clients |

`is_mobile` is a broad **mobile-device** heuristic, not an Android-app flag.
The Android app's explicit `VoxQuieta/<version> (Android <release>)` UA is in
the mobile bucket, as are Android/iPhone/iPad browsers and Dalvik clients. A
generic `okhttp/<version>` UA is not enough to infer Android because OkHttp is
also a general-purpose JVM client. The stored UA can be queried separately
when an Android-app-specific adoption number is needed.

### Custom OpenTelemetry Metrics

Defined in `api/utils/metrics.py`, recorded in route handlers:

| Metric | Type | Description |
|--------|------|-------------|
| `chat.messages.total` | Counter | Total chat messages |
| `chat.response_time_ms` | Histogram | Response latency |
| `chat.sessions.active` | Counter | Per-session activity events |
| `scripture.search.total` | Counter | Scripture searches |
| `scripture.verses.returned` | Histogram | Verses per search |

When Application Insights is connected, these appear in **Metrics Explorer**
under `customMetrics`.

### DAU/MAU Queries

**From PostgreSQL:**

```sql
-- Daily Active Users (last 30 days)
SELECT DATE(last_activity), COUNT(DISTINCT session_token)
FROM sessions
WHERE last_activity >= NOW() - INTERVAL '30 days'
GROUP BY DATE(last_activity)
ORDER BY 1;

-- Monthly Active Users
SELECT COUNT(DISTINCT session_token)
FROM sessions
WHERE last_activity >= NOW() - INTERVAL '30 days';
```

**From Application Insights (KQL):**

```kql
// Daily Active Users
customMetrics
| where name == "chat.sessions.active"
| summarize dcount(tostring(customDimensions.session_token)) by bin(timestamp, 1d)

// Monthly Active Users
customMetrics
| where name == "chat.sessions.active"
| summarize dcount(tostring(customDimensions.session_token)) by bin(timestamp, 30d)
```

---

## Future: Option D — Frontend Event Tracking

A richer analytics layer that tracks user interactions beyond chat messages.

### Proposed Endpoint

```text
POST /api/v1/analytics/event
```

```json
{
  "event": "verse_clicked",
  "session_id": "session-abc123",
  "properties": {
    "book": "John",
    "chapter": 3,
    "verse": 16
  }
}
```

### Events to Track

| Event | When | Properties |
|-------|------|------------|
| `verse_clicked` | User clicks a verse card | book, chapter, verse |
| `chapter_opened` | Chapter modal opened | book, chapter |
| `feedback_submitted` | Thumbs up/down | rating, message_id |
| `translation_changed` | User switches translation | from, to |
| `new_chat_started` | "New Chat" clicked | message_count (of ended chat) |
| `church_finder_opened` | Church finder modal opened | trigger (banner/inline) |

### Frontend Pattern

```typescript
class EventLogger {
  private sessionId: string;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  async track(event: string, properties?: Record<string, unknown>) {
    // Fire-and-forget: don't await, don't block UI
    fetch(`${API_URL}/api/v1/analytics/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event,
        session_id: this.sessionId,
        properties,
      }),
    }).catch(() => {}); // Silently ignore failures
  }
}
```

### KQL Dashboard Queries

```kql
// Most clicked verses
customEvents
| where name == "verse_clicked"
| summarize count() by tostring(customDimensions.book),
  toint(customDimensions.chapter), toint(customDimensions.verse)
| top 20 by count_

// Feature adoption: translation changes
customEvents
| where name == "translation_changed"
| summarize changes = count() by bin(timestamp, 1d)
```
