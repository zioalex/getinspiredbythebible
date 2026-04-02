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

    const headers = getHeaders();
    consumeToken();

    const response = await fetch(`${API_URL}/api/v1/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        message,
        conversation_history: history,
        include_search: true,
        preferred_translation: preferredTranslation,
        session_id: sessionId,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      // Handle 429 rate limit errors
      if (response.status === 429) {
        const data = await response.json().catch(() => ({}));
        if (data.error === "session_lifetime_limit") {
          throw new SessionLimitError(
            data.message ||
              "Session limit reached. Start a new session to continue.",
          );
        }
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
  // For content type:
  content?: string;
  // For error type:
  error?: string;
  // For completion type:
  verses_cited?: string[];
}

/**
 * Stream a chat response with metadata
 */
export async function* streamMessage(
  message: string,
  history: Message[] = [],
  preferredTranslation?: string,
  sessionId?: string,
): AsyncGenerator<StreamChunk> {
  const headers = getHeaders();
  consumeToken();

  const response = await fetch(`${API_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message,
      conversation_history: history,
      include_search: true,
      preferred_translation: preferredTranslation,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    // Handle 429 rate limit errors
    if (response.status === 429) {
      const data = await response.json().catch(() => ({}));
      if (data.error === "session_lifetime_limit") {
        throw new SessionLimitError(
          data.message ||
            "Session limit reached. Start a new session to continue.",
        );
      }
    }
    throw new Error(`API error: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data === "[DONE]") return;

        try {
          const parsed: StreamChunk = JSON.parse(data);
          yield parsed;
        } catch {
          // Skip invalid JSON
        }
      }
    }
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
): Promise<{
  book: string;
  localized_book?: string;
  chapter: number;
  verses: Verse[];
  translation?: string;
  translation_name?: string;
}> {
  const params = translation
    ? `?translation=${encodeURIComponent(translation)}`
    : "";
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
  const headers = getHeaders();
  consumeToken();

  const response = await fetch(`${API_URL}/api/v1/church/search`, {
    method: "POST",
    headers,
    body: JSON.stringify({ location }),
  });

  if (!response.ok) {
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
  const headers = getHeaders();
  consumeToken();

  const response = await fetch(`${API_URL}/api/v1/feedback`, {
    method: "POST",
    headers,
    body: JSON.stringify(feedback),
  });

  if (!response.ok) {
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
  const headers = getHeaders();
  consumeToken();

  const response = await fetch(`${API_URL}/api/v1/feedback/contact`, {
    method: "POST",
    headers,
    body: JSON.stringify(contact),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}
