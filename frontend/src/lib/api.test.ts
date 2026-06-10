import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  sendMessage,
  searchScripture,
  getVerse,
  getChapter,
  getVerseContext,
  checkHealth,
  searchChurches,
  checkBackendReady,
  warmupBackend,
  setTurnstileToken,
  setOnTokenConsumed,
  setTurnstileAwaiter,
  submitFeedback,
  streamMessage,
  ColdStartError,
  StreamTimeoutError,
  type ChatResponse,
  type ScriptureContext,
  type Verse,
  type HealthStatus,
  type ChurchSearchResponse,
} from "./api";

// Mock fetch globally
global.fetch = vi.fn();

beforeEach(() => {
  vi.resetAllMocks();
});

describe("sendMessage", () => {
  it("should send a message and return a response", async () => {
    const mockResponse: ChatResponse = {
      message: "For God so loved the world...",
      scripture_context: {
        query: "love",
        verses: [
          {
            reference: "John 3:16",
            text: "For God so loved the world...",
            book: "John",
            chapter: 3,
            verse: 16,
          },
        ],
        passages: [],
      },
      provider: "ollama",
      model: "llama3",
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await sendMessage("Tell me about love");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/chat",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: "Tell me about love",
          conversation_history: [],
          include_search: true,
        }),
        signal: expect.any(AbortSignal),
      }),
    );

    expect(result).toEqual(mockResponse);
  });

  it("should include conversation history", async () => {
    const history = [
      { role: "user" as const, content: "Hello" },
      { role: "assistant" as const, content: "Hi there!" },
    ];

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "Response",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Follow-up question", history);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({
          message: "Follow-up question",
          conversation_history: history,
          include_search: true,
        }),
      }),
    );
  });

  it("should throw error on API failure", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(sendMessage("Test")).rejects.toThrow("API error: 500");
  });

  it("should include preferred translation when provided", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "Response",
        provider: "ollama",
        model: "llama3",
        detected_translation: "ita1927",
      }),
    });

    await sendMessage("Dimmi dell'amore", [], "ita1927");

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({
          message: "Dimmi dell'amore",
          conversation_history: [],
          include_search: true,
          preferred_translation: "ita1927",
        }),
      }),
    );
  });
});

describe("searchScripture", () => {
  it("should search scripture with query", async () => {
    const mockContext: ScriptureContext = {
      query: "peace",
      verses: [
        {
          reference: "John 14:27",
          text: "Peace I leave with you...",
          book: "John",
          chapter: 14,
          verse: 27,
        },
      ],
      passages: [],
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockContext,
    });

    const result = await searchScripture("peace", 5);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/scripture/search?q=peace&max_verses=5",
      { headers: { "Content-Type": "application/json" } },
    );
    expect(result).toEqual(mockContext);
  });

  it("should use default max_verses", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ query: "test", verses: [], passages: [] }),
    });

    await searchScripture("test");

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("max_verses=5"),
      {
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("should throw error on API failure", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    await expect(searchScripture("nonexistent")).rejects.toThrow(
      "API error: 404",
    );
  });
});

describe("getVerse", () => {
  it("should fetch a specific verse", async () => {
    const mockVerse: Verse = {
      reference: "John 3:16",
      text: "For God so loved the world...",
      book: "John",
      chapter: 3,
      verse: 16,
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockVerse,
    });

    const result = await getVerse("John", 3, 16);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/scripture/verse/John/3/16",
      { headers: { "Content-Type": "application/json" } },
    );
    expect(result).toEqual(mockVerse);
  });

  it("should encode book names with spaces", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        reference: "Song of Solomon 1:1",
        text: "The song of songs...",
        book: "Song of Solomon",
        chapter: 1,
        verse: 1,
      }),
    });

    await getVerse("Song of Solomon", 1, 1);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/scripture/verse/Song%20of%20Solomon/1/1",
      { headers: { "Content-Type": "application/json" } },
    );
  });

  it("should throw error on API failure", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    await expect(getVerse("Invalid", 999, 999)).rejects.toThrow(
      "API error: 404",
    );
  });
});

describe("getChapter", () => {
  it("should fetch all verses in a chapter", async () => {
    const mockChapter = {
      book: "Psalm",
      chapter: 23,
      verses: [
        {
          reference: "Psalm 23:1",
          text: "The Lord is my shepherd...",
          book: "Psalm",
          chapter: 23,
          verse: 1,
        },
        {
          reference: "Psalm 23:2",
          text: "He makes me lie down in green pastures...",
          book: "Psalm",
          chapter: 23,
          verse: 2,
        },
      ],
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockChapter,
    });

    const result = await getChapter("Psalm", 23);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/scripture/chapter/Psalm/23",
      { headers: { "Content-Type": "application/json" } },
    );
    expect(result).toEqual(mockChapter);
    expect(result.verses).toHaveLength(2);
  });

  it("passes the translation as a query param when provided", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ book: "Psalm", chapter: 23, verses: [] }),
    });

    await getChapter("Psalm", 23, "kjv");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/scripture/chapter/Psalm/23?translation=kjv",
      { headers: { "Content-Type": "application/json" } },
    );
  });

  it("sends the UI language as lang so the default version matches the locale", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ book: "Psalm", chapter: 23, verses: [] }),
    });

    // No explicit translation (inline verse tap), German UI.
    await getChapter("Psalm", 23, undefined, "de");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/scripture/chapter/Psalm/23?lang=de",
      { headers: { "Content-Type": "application/json" } },
    );
  });

  it("should throw error on API failure", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    await expect(getChapter("Invalid", 999)).rejects.toThrow("API error: 404");
  });
});

describe("getVerseContext", () => {
  it("should fetch verse with surrounding context", async () => {
    const mockContext = {
      target_verse: 16,
      verses: [
        {
          reference: "John 3:15",
          text: "that whoever believes...",
          book: "John",
          chapter: 3,
          verse: 15,
        },
        {
          reference: "John 3:16",
          text: "For God so loved the world...",
          book: "John",
          chapter: 3,
          verse: 16,
        },
        {
          reference: "John 3:17",
          text: "For God did not send his Son...",
          book: "John",
          chapter: 3,
          verse: 17,
        },
      ],
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockContext,
    });

    const result = await getVerseContext("John", 3, 16);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/chat/verse/John/3/16",
      {
        headers: { "Content-Type": "application/json" },
      },
    );
    expect(result).toEqual(mockContext);
    expect(result.target_verse).toBe(16);
  });
});

describe("checkHealth", () => {
  it("should fetch health status", async () => {
    const mockHealth: HealthStatus = {
      status: "healthy",
      providers: {
        llm: { provider: "ollama", healthy: true },
        embedding: { provider: "ollama", healthy: true },
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealth,
    });

    const result = await checkHealth();

    expect(global.fetch).toHaveBeenCalledWith("http://localhost:8000/health");
    expect(result).toEqual(mockHealth);
  });

  it("should handle degraded status", async () => {
    const mockHealth: HealthStatus = {
      status: "degraded",
      providers: {
        llm: { provider: "ollama", healthy: true },
        embedding: { provider: "ollama", healthy: false },
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealth,
    });

    const result = await checkHealth();

    expect(result.status).toBe("degraded");
    expect(result.providers.embedding.healthy).toBe(false);
  });

  it("should throw error on API failure", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 503,
    });

    await expect(checkHealth()).rejects.toThrow("API error: 503");
  });
});

describe("searchChurches", () => {
  it("should search for churches by location", async () => {
    const mockResponse: ChurchSearchResponse = {
      churches: [
        {
          name: "Zurich Church of Christ",
          address: null,
          city: "Zurich",
          state: null,
          country: "Switzerland",
          website: "http://www.church.ch",
          phone: "+41 78 123 4567",
          email: "info@church.ch",
        },
      ],
      total: 1,
      location: "Switzerland",
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await searchChurches("Switzerland");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/church/search",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ location: "Switzerland" }),
      },
    );

    expect(result).toEqual(mockResponse);
    expect(result.churches).toHaveLength(1);
    expect(result.churches[0].name).toBe("Zurich Church of Christ");
  });

  it("should handle empty results", async () => {
    const mockResponse: ChurchSearchResponse = {
      churches: [],
      total: 0,
      location: "Nonexistent Place",
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await searchChurches("Nonexistent Place");

    expect(result.churches).toHaveLength(0);
    expect(result.total).toBe(0);
  });

  it("should throw error on API failure", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 502,
    });

    await expect(searchChurches("Switzerland")).rejects.toThrow(
      "API error: 502",
    );
  });

  it("should throw error on timeout (504)", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 504,
    });

    await expect(searchChurches("Switzerland")).rejects.toThrow(
      "API error: 504",
    );
  });
});

describe("checkBackendReady", () => {
  it("should return true when backend responds ok", async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: true });

    const result = await checkBackendReady();
    expect(result).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/health/ready",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("should return false when backend responds not ok", async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false });

    const result = await checkBackendReady();
    expect(result).toBe(false);
  });

  it("should return false when fetch throws (network error)", async () => {
    (global.fetch as any).mockRejectedValueOnce(new TypeError("fetch failed"));

    const result = await checkBackendReady();
    expect(result).toBe(false);
  });
});

describe("warmupBackend", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should call onReady immediately when backend is already up", async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: true });

    const onReady = vi.fn();
    const onWaiting = vi.fn();

    await warmupBackend(onReady, onWaiting);

    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onWaiting).not.toHaveBeenCalled();
  });

  it("should call onWaiting then poll until ready", async () => {
    // First check fails, second succeeds
    (global.fetch as any)
      .mockResolvedValueOnce({ ok: false }) // initial check
      .mockResolvedValueOnce({ ok: true }); // first poll

    const onReady = vi.fn();
    const onWaiting = vi.fn();

    const promise = warmupBackend(onReady, onWaiting, 30000);

    // After initial check, onWaiting should be called
    await vi.advanceTimersByTimeAsync(0);
    expect(onWaiting).toHaveBeenCalledTimes(1);
    expect(onReady).not.toHaveBeenCalled();

    // Advance past the 3s polling interval
    await vi.advanceTimersByTimeAsync(3000);

    await promise;

    expect(onReady).toHaveBeenCalledTimes(1);
  });

  it("should stop polling after maxWaitMs without calling onReady", async () => {
    // All checks fail
    (global.fetch as any).mockResolvedValue({ ok: false });

    const onReady = vi.fn();
    const onWaiting = vi.fn();

    // Use a short maxWaitMs for the test
    const promise = warmupBackend(onReady, onWaiting, 5000);

    // Advance through the entire wait period
    await vi.advanceTimersByTimeAsync(6000);

    await promise;

    expect(onWaiting).toHaveBeenCalledTimes(1);
    expect(onReady).not.toHaveBeenCalled();
  });

  it("should work without onWaiting callback", async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({ ok: true });

    const onReady = vi.fn();

    const promise = warmupBackend(onReady);

    await vi.advanceTimersByTimeAsync(3000);
    await promise;

    expect(onReady).toHaveBeenCalledTimes(1);
  });
});

describe("sendMessage with timeoutMs", () => {
  it("should use custom timeout when provided", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "Response",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Hello", [], undefined, undefined, 8000);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("should throw ColdStartError on 503 response", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 503,
    });

    await expect(sendMessage("Test")).rejects.toThrow(ColdStartError);
  });

  it("should throw ColdStartError on 502 response", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 502,
    });

    await expect(sendMessage("Test")).rejects.toThrow(ColdStartError);
  });

  it("should throw ColdStartError on AbortError (timeout)", async () => {
    const abortError = new DOMException(
      "The operation was aborted",
      "AbortError",
    );
    (global.fetch as any).mockRejectedValueOnce(abortError);

    await expect(sendMessage("Test")).rejects.toThrow(ColdStartError);
  });

  it("should throw ColdStartError on TypeError (network failure)", async () => {
    (global.fetch as any).mockRejectedValueOnce(
      new TypeError("Failed to fetch"),
    );

    await expect(sendMessage("Test")).rejects.toThrow(ColdStartError);
  });
});

describe("Turnstile token consumption", () => {
  afterEach(() => {
    setTurnstileToken(null);
    setOnTokenConsumed(null);
  });

  it("should include Turnstile token in request headers when set", async () => {
    setTurnstileToken("test-token-123");

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "Response",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Hello");

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Turnstile-Token": "test-token-123",
        }),
      }),
    );
  });

  it("should consume token after API call (not reuse it)", async () => {
    setTurnstileToken("single-use-token");

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        message: "Response",
        provider: "ollama",
        model: "llama3",
      }),
    });

    // First call should include the token
    await sendMessage("First message");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Turnstile-Token": "single-use-token",
        }),
      }),
    );

    // Second call should NOT include the token (it was consumed)
    await sendMessage("Second message");
    const secondCallHeaders = (global.fetch as any).mock.calls[1][1].headers;
    expect(secondCallHeaders["X-Turnstile-Token"]).toBeUndefined();
  });

  it("should call onTokenConsumed callback after using a token", async () => {
    const onConsumed = vi.fn();
    setTurnstileToken("token-to-consume");
    setOnTokenConsumed(onConsumed);

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "Response",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Hello");

    expect(onConsumed).toHaveBeenCalledTimes(1);
  });

  it("should not call onTokenConsumed when no token is set", async () => {
    const onConsumed = vi.fn();
    setTurnstileToken(null);
    setOnTokenConsumed(onConsumed);

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "Response",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Hello");

    expect(onConsumed).not.toHaveBeenCalled();
  });

  it("should consume token for all protected endpoints", async () => {
    const onConsumed = vi.fn();
    setOnTokenConsumed(onConsumed);

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    // Each call sets a fresh token and verifies consumption
    // Only endpoints with require_turnstile on the backend should consume tokens
    setTurnstileToken("token-chat");
    await sendMessage("msg");
    expect(onConsumed).toHaveBeenCalledTimes(1);

    setTurnstileToken("token-church");
    await searchChurches("Zurich");
    expect(onConsumed).toHaveBeenCalledTimes(2);

    setTurnstileToken("token-feedback");
    await submitFeedback({
      message_id: "test",
      rating: "positive",
      user_message: "q",
      assistant_response: "a",
    });
    expect(onConsumed).toHaveBeenCalledTimes(3);
  });

  it("should not consume token for unprotected scripture endpoints", async () => {
    const onConsumed = vi.fn();
    setOnTokenConsumed(onConsumed);
    setTurnstileToken("shared-token");

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ verses: [], passages: [], query: "" }),
    });

    // Scripture endpoints do not require Turnstile — token must not be consumed
    await searchScripture("peace");
    expect(onConsumed).not.toHaveBeenCalled();

    await getVerse("John", 3, 16);
    expect(onConsumed).not.toHaveBeenCalled();

    await getChapter("Psalm", 23);
    expect(onConsumed).not.toHaveBeenCalled();
  });

  it("should not send token for unprotected endpoints", async () => {
    setTurnstileToken("should-not-be-sent");

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        target_verse: 16,
        verses: [],
      }),
    });

    await getVerseContext("John", 3, 16);

    const headers = (global.fetch as any).mock.calls[0][1].headers;
    expect(headers["X-Turnstile-Token"]).toBeUndefined();

    // Token should still be available (not consumed by unprotected endpoint)
    expect(
      (global.fetch as any).mock.calls[0][1].headers["X-Turnstile-Token"],
    ).toBeUndefined();
  });
});

describe("Turnstile awaiter (ensureTurnstileToken)", () => {
  afterEach(() => {
    setTurnstileToken(null);
    setOnTokenConsumed(null);
    setTurnstileAwaiter(null);
  });

  it("waits for the awaiter when no cached token is set, then attaches header", async () => {
    const awaiter = vi.fn().mockResolvedValue("late-token");
    setTurnstileAwaiter(awaiter);

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "ok",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Hello");

    expect(awaiter).toHaveBeenCalledTimes(1);
    expect((global.fetch as any).mock.calls[0][1].headers).toEqual(
      expect.objectContaining({ "X-Turnstile-Token": "late-token" }),
    );
  });

  it("skips the awaiter when a token is already cached", async () => {
    const awaiter = vi.fn().mockResolvedValue("late-token");
    setTurnstileAwaiter(awaiter);
    setTurnstileToken("cached-token");

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "ok",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Hello");

    expect(awaiter).not.toHaveBeenCalled();
    expect((global.fetch as any).mock.calls[0][1].headers).toEqual(
      expect.objectContaining({ "X-Turnstile-Token": "cached-token" }),
    );
  });

  it("falls open when the awaiter resolves with null (Turnstile disabled)", async () => {
    const awaiter = vi.fn().mockResolvedValue(null);
    setTurnstileAwaiter(awaiter);

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "ok",
        provider: "ollama",
        model: "llama3",
      }),
    });

    await sendMessage("Hello");

    expect(awaiter).toHaveBeenCalledTimes(1);
    const headers = (global.fetch as any).mock.calls[0][1].headers;
    expect(headers["X-Turnstile-Token"]).toBeUndefined();
  });

  it("invokes the awaiter on each Turnstile-gated POST", async () => {
    const awaiter = vi.fn().mockResolvedValue(null);
    setTurnstileAwaiter(awaiter);

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    await sendMessage("msg");
    await searchChurches("Zurich");
    await submitFeedback({
      message_id: "test",
      rating: "positive",
      user_message: "q",
      assistant_response: "a",
    });

    expect(awaiter).toHaveBeenCalledTimes(3);
  });
});

/**
 * Build a mock streaming Response whose body yields the given string chunks in
 * order. Lets us simulate SSE framing — including events deliberately split
 * across read() boundaries the way real networks deliver them.
 */
function streamResponseFromChunks(chunks: string[]) {
  const encoder = new TextEncoder();
  let i = 0;
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () =>
          i < chunks.length
            ? { done: false, value: encoder.encode(chunks[i++]) }
            : { done: true, value: undefined },
        cancel: vi.fn().mockResolvedValue(undefined),
      }),
    },
  };
}

describe("streamMessage", () => {
  it("parses an SSE event that is split across read boundaries", async () => {
    // The JSON object is cut mid-key between two reads — naive per-read parsing
    // would drop it silently. With buffering it must arrive intact.
    (global.fetch as any).mockResolvedValueOnce(
      streamResponseFromChunks([
        'data: {"type":"content","con',
        'tent":"Hello"}\n\ndata: [DONE]\n\n',
      ]),
    );

    const received = [];
    for await (const chunk of streamMessage("hi")) {
      received.push(chunk);
    }

    expect(received).toEqual([{ type: "content", content: "Hello" }]);
  });

  it("yields multiple events delivered in a single read", async () => {
    (global.fetch as any).mockResolvedValueOnce(
      streamResponseFromChunks([
        'data: {"type":"metadata","message_id":"m1"}\n\n' +
          'data: {"type":"content","content":"Peace"}\n\n' +
          "data: [DONE]\n\n",
      ]),
    );

    const received = [];
    for await (const chunk of streamMessage("hi")) {
      received.push(chunk);
    }

    expect(received).toEqual([
      { type: "metadata", message_id: "m1" },
      { type: "content", content: "Peace" },
    ]);
  });

  describe("inactivity timeout", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    it("throws StreamTimeoutError when no chunk arrives in time", async () => {
      const cancel = vi.fn().mockResolvedValue(undefined);
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            // A stalled stream: read() never resolves.
            read: () => new Promise(() => {}),
            cancel,
          }),
        },
      });

      const gen = streamMessage("hi");
      // Attach the rejection handler before advancing timers so the settled
      // promise is never momentarily flagged as an unhandled rejection.
      const assertion = expect(gen.next()).rejects.toBeInstanceOf(
        StreamTimeoutError,
      );

      // Advance past the inactivity window to fire the timeout.
      await vi.advanceTimersByTimeAsync(30_000);

      await assertion;
      // The stalled reader must be released so the connection isn't leaked.
      expect(cancel).toHaveBeenCalled();
    });
  });
});
