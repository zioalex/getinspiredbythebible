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
  ColdStartError,
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
      { headers: { "Content-Type": "application/json" } },
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
      { headers: { "Content-Type": "application/json" } },
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
