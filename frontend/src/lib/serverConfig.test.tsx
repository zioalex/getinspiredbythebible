import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { ServerConfigProvider, useServerConfig } from "./serverConfig";

// BITB-075: the effective chat message limit is published by the backend via
// GET /config -> chat.max_message_length, with the compiled-in
// MAX_MESSAGE_LENGTH constant (currently 500) used only as a pre-fetch /
// fail-open fallback.

function wrapper(apiUrl = "http://test.example") {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <ServerConfigProvider apiUrl={apiUrl}>{children}</ServerConfigProvider>
    );
  };
}

describe("ServerConfigProvider", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts with the compiled-in fallback before /config resolves", () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockReturnValue(new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useServerConfig(), {
      wrapper: wrapper(),
    });

    expect(result.current.maxMessageLength).toBe(500);
  });

  it("adopts the server value when /config succeeds", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ chat: { max_message_length: 500 } }),
    });

    const { result } = renderHook(() => useServerConfig(), {
      wrapper: wrapper(),
    });

    await waitFor(() => {
      expect(result.current.maxMessageLength).toBe(500);
    });
    expect(fetchMock).toHaveBeenCalledWith("http://test.example/config");
  });

  it("adopts a different server value when the backend disagrees with the fallback", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ chat: { max_message_length: 800 } }),
    });

    const { result } = renderHook(() => useServerConfig(), {
      wrapper: wrapper(),
    });

    await waitFor(() => {
      expect(result.current.maxMessageLength).toBe(800);
    });
  });

  it("keeps the fallback when the fetch rejects (network error)", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockRejectedValue(new Error("network down"));

    const { result } = renderHook(() => useServerConfig(), {
      wrapper: wrapper(),
    });

    // Give the failed fetch a tick to settle.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(result.current.maxMessageLength).toBe(500);
  });

  it("keeps the fallback when the response is not ok", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useServerConfig(), {
      wrapper: wrapper(),
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(result.current.maxMessageLength).toBe(500);
  });

  it("keeps the fallback when chat is missing from the response", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    const { result } = renderHook(() => useServerConfig(), {
      wrapper: wrapper(),
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(result.current.maxMessageLength).toBe(500);
  });

  it.each([0, -5, 12.5, "500", null, undefined])(
    "keeps the fallback when max_message_length is invalid (%p)",
    async (invalidValue) => {
      const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ chat: { max_message_length: invalidValue } }),
      });

      const { result } = renderHook(() => useServerConfig(), {
        wrapper: wrapper(),
      });

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalled();
      });
      expect(result.current.maxMessageLength).toBe(500);
    },
  );

  it("fetches /config unconditionally, regardless of Turnstile build-time site-key state", async () => {
    // Regression test for the prod-skip trap: TurnstileProvider skips its own
    // /config fetch whenever NEXT_PUBLIC_TURNSTILE_SITE_KEY is set at build
    // time (always true in production, see frontend/Dockerfile). This
    // provider must NOT inherit that behaviour — it has no build-time
    // shortcut and always fetches, so the message-limit config is never
    // silently dead in prod.
    const originalSiteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = "prod-build-time-site-key";

    try {
      const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ chat: { max_message_length: 500 } }),
      });

      renderHook(() => useServerConfig(), { wrapper: wrapper() });

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith("http://test.example/config");
      });
    } finally {
      if (originalSiteKey === undefined) {
        delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
      } else {
        process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = originalSiteKey;
      }
    }
  });

  it("uses the NEXT_PUBLIC_API_URL default when no apiUrl prop is supplied", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ chat: { max_message_length: 500 } }),
    });

    renderHook(() => useServerConfig(), {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <ServerConfigProvider>{children}</ServerConfigProvider>
      ),
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/config"),
      );
    });
  });
});
