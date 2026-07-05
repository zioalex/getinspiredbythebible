/**
 * API client for Bible Chat backend
 */

// In production builds, NEXT_PUBLIC_API_URL must be set at build time.
// The fallback is only for local development.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Validate API URL in production (this check is tree-shaken in dev builds)
if (
  process.env.NODE_ENV === "production" &&
  (!process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_URL === "http://localhost:8000")
) {
  console.error(
    "WARNING: NEXT_PUBLIC_API_URL is not set or is set to localhost in production build",
  );
}

/**
 * Error thrown when the backend is warming up (cold start)
 */
export class ColdStartError extends Error {
  constructor(message: string = "Backend is warming up") {
    super(message);
    this.name = "ColdStartError";
  }
}

/**
 * Error thrown when session lifetime limit is reached (10 messages)
 */
export class SessionLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SessionLimitError";
  }
}

/**
 * Error thrown when the safety system blocks a message.
 * UI should render a warm, reassuring notification and invite the user to
 * rephrase or contact support — not a generic API error.
 */
export class ContentBlockedError extends Error {
  constructor(message: string = "Message blocked by safety filter") {
    super(message);
    this.name = "ContentBlockedError";
  }
}

/**
 * Error thrown when a streaming response stalls — no data arrives within
 * STREAM_INACTIVITY_TIMEOUT_MS, either before the first byte (the connection
 * never produces output) or mid-stream (a backend/network glitch). UI should
 * surface a clear "interrupted, please try again" message instead of leaving
 * the user waiting on an empty bubble forever.
 */
export class StreamTimeoutError extends Error {
  constructor(message: string = "The response stalled and timed out") {
    super(message);
    this.name = "StreamTimeoutError";
  }
}

/**
 * Error thrown when the chat message exceeds the backend length limit
 * (HTTP 422). The UI guards against this client-side, but the server is the
 * source of truth — surface a clear "too long" message rather than a generic
 * connection error so the user knows to shorten their message.
 */
export class MessageTooLongError extends Error {
  constructor(message: string = "Message exceeds the maximum length") {
    super(message);
    this.name = "MessageTooLongError";
  }
}

/**
 * Error thrown when Cloudflare Turnstile rejects a request (HTTP 403:
 * TURNSTILE_REQUIRED — no token reached the server — or TURNSTILE_FAILED —
 * token stale/duplicate). The gated POST already retries once with a fresh
 * token before this is thrown, so reaching here means recovery didn't land in
 * time. UI should surface a "couldn't verify your device, please retry"
 * message rather than a generic connection error.
 */
export class VerificationError extends Error {
  constructor(
    message: string = "We couldn't verify your device. Please wait a moment and try again.",
  ) {
    super(message);
    this.name = "VerificationError";
  }
}

/**
 * Max characters allowed in a single chat message. MUST stay in sync with the
 * backend's `max_message_length` setting (api/config.py); the server rejects
 * anything longer with HTTP 422.
 */
export const MAX_MESSAGE_LENGTH = 300;

/**
 * Max time to wait for the next chunk from the streaming endpoint before
 * declaring the stream stalled. Reset on every chunk (heartbeat-style), so a
 * normal streaming response that keeps producing tokens never trips it.
 */
const STREAM_INACTIVITY_TIMEOUT_MS = 30_000;

/**
 * Check if the backend is ready
 */
export async function checkBackendReady(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(`${API_URL}/health/ready`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response.ok;
  } catch {
    return false;
  }
}

// Turnstile token for bot protection
let turnstileToken: string | null = null;
let onTokenConsumed: (() => void) | null = null;
type TurnstileAwaiter = (timeoutMs?: number) => Promise<string | null>;
let turnstileAwaiter: TurnstileAwaiter | null = null;

// Default wait for Turnstile-gated POSTs. Mirrors the Android client (PR #439):
// before firing a POST we briefly wait for the widget to issue a token so the
// first send after page load (config still loading) doesn't race past it and
// get bounced as 403 TURNSTILE_REQUIRED.
const DEFAULT_TURNSTILE_WAIT_MS = 5000;

/**
 * Set the Turnstile token for API requests
 */
export function setTurnstileToken(token: string | null): void {
  turnstileToken = token;
}

/**
 * Register a callback that fires after a token is used in an API request.
 * This allows the Turnstile widget to refresh and generate a new token.
 */
export function setOnTokenConsumed(callback: (() => void) | null): void {
  onTokenConsumed = callback;
}

/**
 * Register a function that resolves with the current Turnstile token,
 * waiting briefly if config / widget is still loading. Called before
 * Turnstile-gated POSTs.
 */
export function setTurnstileAwaiter(awaiter: TurnstileAwaiter | null): void {
  turnstileAwaiter = awaiter;
}

/**
 * Consume the current token (use it once then trigger refresh).
 * Turnstile tokens are single-use — Cloudflare rejects reused tokens
 * with "timeout-or-duplicate".
 */
function consumeToken(): void {
  if (turnstileToken) {
    turnstileToken = null;
    onTokenConsumed?.();
  }
}

/**
 * Wait briefly for a Turnstile token to be available before sending a
 * gated POST. No-op if no awaiter is registered (e.g. server-side or
 * before the React provider mounts).
 */
async function ensureTurnstileToken(
  timeoutMs: number = DEFAULT_TURNSTILE_WAIT_MS,
): Promise<void> {
  if (turnstileToken || !turnstileAwaiter) return;
  const awaited = await turnstileAwaiter(timeoutMs);
  if (awaited && !turnstileToken) {
    turnstileToken = awaited;
  }
}

/**
 * Get headers with optional Turnstile token
 */
function getHeaders(): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (turnstileToken) {
    headers["X-Turnstile-Token"] = turnstileToken;
  }
  return headers;
}

// Longer wait used only on the 403 retry: a 403 means the token was missing or
// stale, so we give the widget's refresh (kicked by consumeToken below) time to
// produce a fresh token — mirrors the Android TurnstileInterceptor retry path.
const TURNSTILE_RETRY_WAIT_MS = 8000;

/**
 * Perform a Turnstile-gated POST: wait briefly for a token, attach it, consume
 * it (single-use), then fire the request. On a 403 (Turnstile required/failed)
 * the consumed token has already triggered a widget refresh, so we wait for the
 * fresh token and retry exactly once before giving up. This keeps a single
 * stale token or a transient widget hiccup from surfacing as a hard failure,
 * and — together with the self-healing widget — prevents the wedge where every
 * gated POST 403s for the rest of the session.
 *
 * Returns the raw Response (including a final 403) so each caller can map
 * status codes to its own typed errors.
 */
async function turnstilePost(
  url: string,
  body: unknown,
  init?: { signal?: AbortSignal },
): Promise<Response> {
  await ensureTurnstileToken();
  const headers = getHeaders();
  consumeToken();

  let response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: init?.signal,
  });

  if (response.status === 403) {
    // Wait for the refreshed token (consumeToken kicked the widget) and retry
    // once. If no fresh token arrives in time, fall through with the 403 so the
    // caller surfaces a clear verification error.
    await ensureTurnstileToken(TURNSTILE_RETRY_WAIT_MS);
    if (turnstileToken) {
      const retryHeaders = getHeaders();
      consumeToken();
      response = await fetch(url, {
        method: "POST",
        headers: retryHeaders,
        body: JSON.stringify(body),
        signal: init?.signal,
      });
    }
  }

  return response;
}

/**
 * Generate a unique session ID for tracking user interactions
 */
export function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

const SESSION_STORAGE_KEY = "bible-chat-session-id";

/**
 * Get or create a persistent session ID stored in localStorage.
 * Returns the same ID across page refreshes for DAU/MAU tracking.
 * Use generateSessionId() for per-conversation IDs.
 */
export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") {
    return generateSessionId();
  }
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) return stored;
  } catch {
    // localStorage unavailable (SSR, privacy mode)
  }
  const id = generateSessionId();
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, id);
  } catch {
    // ignore write failures
  }
  return id;
}

/**
 * Clear the stored session ID and generate + store a new one.
 * Call this when the user explicitly starts a new session after hitting the limit.
 * Returns the new session ID.
 */
export function resetSessionId(): string {
  const newId = generateSessionId();
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, newId);
  } catch {
    // ignore write failures (privacy mode etc.)
  }
  return newId;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface Verse {
  reference: string;
  text: string;
  book: string;
  localized_book?: string;
  chapter: number;
  verse: number;
  translation?: string;
  similarity?: number;
}

export interface Passage {
  title: string;
  reference: string;
  text: string;
  topics?: string[];
  similarity?: number;
}

export interface ScriptureContext {
  query: string;
  verses: Verse[];
  passages: Passage[];
}

export interface TranslationInfo {
  code: string;
  name: string;
  short_name: string;
  language: string;
  language_code: string;
}

export interface ChatResponse {
  message_id: string;
  message: string;
  scripture_context?: ScriptureContext;
  provider: string;
  model: string;
  detected_translation?: string;
  translation_info?: TranslationInfo;
}

export interface FeedbackRequest {
  message_id: string;
  rating: "positive" | "negative";
  comment?: string;
  user_message: string;
  assistant_response: string;
  verses_cited?: string[];
  model_used?: string;
  response_time_ms?: number;
  session_id?: string;
  reason?: string;
}

export interface FeedbackResponse {
  id: number;
  message_id: string;
  rating: string;
  created_at: string;
}

export interface ContactRequest {
  email?: string;
  subject: "spiritual" | "bug" | "feature" | "feedback" | "other";
  message: string;
  session_id?: string;
  user_agent?: string;
}

export interface ContactResponse {
  id: number;
  subject: string;
  created_at: string;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  providers: {
    llm: { provider: string; healthy: boolean };
    embedding: { provider: string; healthy: boolean };
  };
}

export interface Church {
  name: string;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  website: string | null;
  phone: string | null;
  email: string | null;
}

export interface ChurchSearchResponse {
  churches: Church[];
  total: number;
  location: string;
}

/**
 * Pre-warm the backend by polling /health/ready.
 * Calls onReady when the backend responds, or onWaiting on first failed check.
 */
export async function warmupBackend(
  onReady: () => void,
  onWaiting?: () => void,
  maxWaitMs: number = 60000,
): Promise<void> {
  const start = Date.now();
  const interval = 3000;

  const ready = await checkBackendReady();
  if (ready) {
    onReady();
    return;
  }

  onWaiting?.();

  while (Date.now() - start < maxWaitMs) {
    await new Promise((r) => setTimeout(r, interval));
    if (await checkBackendReady()) {
      onReady();
      return;
    }
  }
}

/**
 * Send a chat message and get a response
 */
export async function sendMessage(
  message: string,
  history: Message[] = [],
  preferredTranslation?: string,
  sessionId?: string,
  timeoutMs: number = 60000,
): Promise<ChatResponse> {
  try {
    // Set a timeout for cold start detection
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const response = await turnstilePost(
      `${API_URL}/api/v1/chat`,
      {
        message,
        conversation_history: history,
        include_search: true,
        preferred_translation: preferredTranslation,
        session_id: sessionId,
      },
      { signal: controller.signal },
    );

    clearTimeout(timeoutId);

    if (!response.ok) {
      // Handle 429 rate limit errors
      if (response.status === 429) {
        const data = await response.json().catch(() => ({}));
        if (data.detail?.error === "session_lifetime_limit") {
          throw new SessionLimitError(
            data.detail?.message ||
              "Session limit reached. Start a new session to continue.",
          );
        }
      }
      // 400 from the content filter: surface a warm notification, not a raw error.
      if (response.status === 400) {
        const data = await response.json().catch(() => ({}));
        if (data.detail?.error === "content_blocked") {
          throw new ContentBlockedError(data.detail?.message);
        }
      }
      // 403: Turnstile rejected the request even after one retry with a fresh
      // token — surface a clear verification message, not a connection error.
      if (response.status === 403) {
        throw new VerificationError();
      }
      // 503 Service Unavailable often indicates cold start
      if (response.status === 503 || response.status === 502) {
        throw new ColdStartError("Backend is starting up");
      }
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  } catch (error) {
    // Network errors or timeouts during cold start
    if (error instanceof ColdStartError) {
      throw error;
    }
    if (
      error instanceof TypeError ||
      (error instanceof DOMException && error.name === "AbortError")
    ) {
      throw new ColdStartError("Backend is warming up, please wait...");
    }
    throw error;
  }
}

export interface StreamMetadata {
  message_id: string;
  scripture_context?: ScriptureContext;
  provider: string;
  model: string;
  detected_translation?: string;
  translation_info?: TranslationInfo;
  /** Detected language code when it differs from the requested `language`. */
  language_suggestion?: string | null;
}

export interface StreamChunk {
  type: "metadata" | "content" | "error" | "completion";
  // For metadata type:
  message_id?: string;
  scripture_context?: ScriptureContext;
  provider?: string;
  model?: string;
  detected_translation?: string;
  translation_info?: TranslationInfo;
  language_suggestion?: string | null;
  // For content type:
  content?: string;
  // For error type:
  error?: string;
  // For completion type:
  // Raw citation reference strings (range form preserved); drives the
  // intersection "Cited" filter.
  verses_cited?: string[];
  // The same citations resolved against the DB (ranges expanded, with text);
  // merged into the verse pool so the filter has cards to match for verses
  // outside the semantic search results.
  resolved_verses?: Verse[];
  // Set only when post-generation grounding rewrote a fabricated/mismatched
  // inline verse quote to the canonical scripture text. When present, it is the
  // authoritative full message body and should replace the streamed content.
  corrected_message?: string;
  corrections?: { reference: string; reason: string }[];
}

/**
 * Stream a chat response with metadata
 */
export interface StreamMessageOptions {
  preferredTranslation?: string;
  sessionId?: string;
  /**
   * Explicit language override (e.g. when the user picks one in a language
   * picker). Omit to let the backend auto-detect from the message text.
   */
  language?: string;
  signal?: AbortSignal;
}

export async function* streamMessage(
  message: string,
  history: Message[] = [],
  {
    preferredTranslation,
    sessionId,
    language,
    signal,
  }: StreamMessageOptions = {},
): AsyncGenerator<StreamChunk> {
  await ensureTurnstileToken();
  const headers = getHeaders();
  consumeToken();

  let response = await fetch(`${API_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message,
      conversation_history: history,
      include_search: true,
      preferred_translation: preferredTranslation,
      session_id: sessionId,
      language,
    }),
    signal,
  });

  // 403: token missing/stale. consumeToken() kicked a widget refresh; wait for
  // the fresh token and retry once before surfacing a verification error.
  if (response.status === 403) {
    await ensureTurnstileToken(TURNSTILE_RETRY_WAIT_MS);
    if (turnstileToken) {
      const retryHeaders = getHeaders();
      consumeToken();
      response = await fetch(`${API_URL}/api/v1/chat/stream`, {
        method: "POST",
        headers: retryHeaders,
        body: JSON.stringify({
          message,
          conversation_history: history,
          include_search: true,
          preferred_translation: preferredTranslation,
          session_id: sessionId,
          language,
        }),
        signal,
      });
    }
  }

  if (!response.ok) {
    // Handle 429 rate limit errors
    if (response.status === 429) {
      const data = await response.json().catch(() => ({}));
      if (data.detail?.error === "session_lifetime_limit") {
        throw new SessionLimitError(
          data.detail?.message ||
            "Session limit reached. Start a new session to continue.",
        );
      }
    }
    // 400 from the content filter: surface a warm notification, not a raw error.
    if (response.status === 400) {
      const data = await response.json().catch(() => ({}));
      if (data.detail?.error === "content_blocked") {
        throw new ContentBlockedError(data.detail?.message);
      }
    }
    // 403: Turnstile rejected the request even after one retry with a fresh
    // token — surface a clear verification message, not a connection error.
    if (response.status === 403) {
      throw new VerificationError();
    }
    // 422 request validation: the realistic client-controllable cause is an
    // over-long message. Detect the message-length error and surface a clear
    // "too long" notice rather than a generic connection failure.
    if (response.status === 422) {
      const data = await response.json().catch(() => ({}));
      const detail = data?.detail;
      const messageTooLong =
        Array.isArray(detail) &&
        detail.some(
          (d) =>
            (typeof d?.type === "string" && d.type.includes("too_long")) ||
            (Array.isArray(d?.loc) && d.loc.includes("message")),
        );
      if (messageTooLong) {
        throw new MessageTooLongError();
      }
    }
    throw new Error(`API error: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  // Buffer holding bytes decoded so far that haven't yet formed a complete
  // line. SSE events ("data: {...}\n\n") can be split across read() boundaries
  // on real networks; without buffering, JSON.parse fails on each half and the
  // chunk — possibly a content or even an error event — is silently dropped.
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel().catch(() => {});
        return;
      }

      // Race the read against an inactivity timeout. If no chunk arrives within
      // the window (stalled backend, dropped connection), cancel the reader and
      // raise StreamTimeoutError so the caller can show a clear message rather
      // than hanging on an empty bubble forever. The timer is recreated on each
      // iteration, so it effectively resets on every chunk (heartbeat).
      let timeoutId: ReturnType<typeof setTimeout> | undefined;
      const timeoutPromise = new Promise<never>((_, reject) => {
        timeoutId = setTimeout(
          () => reject(new StreamTimeoutError()),
          STREAM_INACTIVITY_TIMEOUT_MS,
        );
      });

      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await Promise.race([reader.read(), timeoutPromise]);
      } catch (err) {
        if (err instanceof StreamTimeoutError) {
          await reader.cancel().catch(() => {});
        }
        throw err;
      } finally {
        if (timeoutId !== undefined) clearTimeout(timeoutId);
      }

      const { done, value } = result;
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process only complete lines; retain the trailing partial line (if any)
      // in the buffer for the next read.
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "") continue;
          if (data === "[DONE]") return;

          try {
            const parsed: StreamChunk = JSON.parse(data);
            yield parsed;
          } catch {
            // A complete line that still fails to parse is genuinely malformed;
            // skip it rather than aborting the whole stream.
            if (process.env.NODE_ENV !== "production") {
              console.warn("Skipping malformed SSE line:", data);
            }
          }
        }
      }
    }
  } finally {
    reader.cancel().catch(() => {});
  }
}

/**
 * Search scripture
 */
export async function searchScripture(
  query: string,
  maxVerses: number = 5,
): Promise<ScriptureContext> {
  const params = new URLSearchParams({
    q: query,
    max_verses: maxVerses.toString(),
  });

  const headers = getHeaders();

  const response = await fetch(`${API_URL}/api/v1/scripture/search?${params}`, {
    headers,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Get a specific verse
 */
export async function getVerse(
  book: string,
  chapter: number,
  verse: number,
): Promise<Verse> {
  const headers = getHeaders();

  const response = await fetch(
    `${API_URL}/api/v1/scripture/verse/${encodeURIComponent(book)}/${chapter}/${verse}`,
    { headers },
  );

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Get all verses in a chapter
 */
export async function getChapter(
  book: string,
  chapter: number,
  translation?: string,
  lang?: string,
): Promise<{
  book: string;
  localized_book?: string;
  chapter: number;
  verses: Verse[];
  translation?: string;
  translation_name?: string;
}> {
  const query = new URLSearchParams();
  if (translation) query.set("translation", translation);
  // Send the active UI language so that, when no explicit translation is chosen,
  // the backend defaults to the version for the language the user is reading
  // rather than guessing from the browser's Accept-Language header.
  if (lang) query.set("lang", lang);
  const params = query.toString() ? `?${query.toString()}` : "";
  const headers = getHeaders();

  const response = await fetch(
    `${API_URL}/api/v1/scripture/chapter/${encodeURIComponent(book)}/${chapter}${params}`,
    { headers },
  );

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Get verse with context
 */
export async function getVerseContext(
  book: string,
  chapter: number,
  verse: number,
): Promise<{ target_verse: number; verses: Verse[] }> {
  const response = await fetch(
    `${API_URL}/api/v1/chat/verse/${encodeURIComponent(book)}/${chapter}/${verse}`,
    { headers: { "Content-Type": "application/json" } },
  );

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Check API health
 */
export async function checkHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_URL}/health`);

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Get book name mappings from the backend
 */
export async function getBookNames(): Promise<{
  localized_to_english: Record<string, string>;
  multi_word_names: string[];
}> {
  const response = await fetch(`${API_URL}/api/v1/scripture/book-names`, {
    cache: "force-cache", // leverage the 24h cache-control header
  });
  if (!response.ok) {
    throw new Error("Failed to fetch book names");
  }
  const data = await response.json();
  return data;
}

/**
 * Get available translations
 */
export async function getTranslations(): Promise<TranslationInfo[]> {
  const response = await fetch(`${API_URL}/api/v1/scripture/translations`, {
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();
  return data.translations;
}

/**
 * Search for churches near a location
 */
export async function searchChurches(
  location: string,
): Promise<ChurchSearchResponse> {
  const response = await turnstilePost(`${API_URL}/api/v1/church/search`, {
    location,
  });

  if (!response.ok) {
    if (response.status === 403) {
      throw new VerificationError();
    }
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Submit feedback for a chat message (thumbs up/down)
 */
export async function submitFeedback(
  feedback: FeedbackRequest,
): Promise<FeedbackResponse> {
  const response = await turnstilePost(`${API_URL}/api/v1/feedback`, feedback);

  if (!response.ok) {
    if (response.status === 403) {
      throw new VerificationError();
    }
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Submit a contact form message
 */
export async function submitContactForm(
  contact: ContactRequest,
): Promise<ContactResponse> {
  const response = await turnstilePost(
    `${API_URL}/api/v1/feedback/contact`,
    contact,
  );

  if (!response.ok) {
    if (response.status === 403) {
      throw new VerificationError();
    }
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}
