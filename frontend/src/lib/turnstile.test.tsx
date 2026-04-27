import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, render, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { TurnstileProvider, useTurnstile } from "./turnstile";

// jsdom doesn't load <script> tags, so we never actually fetch turnstile.
// We just need the provider to mount and expose its initial state.

function wrapper(siteKeyOverride?: string) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <TurnstileProvider
        apiUrl="http://test.example"
        siteKeyOverride={siteKeyOverride}
      >
        {children}
      </TurnstileProvider>
    );
  };
}

describe("TurnstileProvider build-time site key", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("skips /config when a build-time site key is provided", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

    const { result } = renderHook(() => useTurnstile(), {
      wrapper: wrapper("test-site-key"),
    });

    // Provider should be configured synchronously: configLoaded=true,
    // isEnabled=true, no /config request.
    expect(result.current.configLoaded).toBe(true);
    expect(result.current.isEnabled).toBe(true);
    expect(result.current.isReady).toBe(false); // widget hasn't issued a token yet

    // Give any spurious effects a tick to run; still no /config call.
    await waitFor(() => {
      expect(fetchMock).not.toHaveBeenCalledWith(
        expect.stringContaining("/config"),
      );
    });
  });

  it("treats an empty-string site key as explicit build-time disable", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

    const { result } = renderHook(() => useTurnstile(), {
      wrapper: wrapper(""),
    });

    // Disabled: configLoaded=true, isEnabled=false, isReady=true.
    expect(result.current.configLoaded).toBe(true);
    expect(result.current.isEnabled).toBe(false);
    expect(result.current.isReady).toBe(true);

    await waitFor(() => {
      expect(fetchMock).not.toHaveBeenCalledWith(
        expect.stringContaining("/config"),
      );
    });
  });

  it("falls back to /config fetch when no override is supplied", async () => {
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        security: { turnstile_enabled: false },
      }),
    });

    const { result } = renderHook(() => useTurnstile(), {
      wrapper: wrapper(undefined),
    });

    // Initially configLoaded=false (waiting on /config).
    expect(result.current.configLoaded).toBe(false);

    // After /config resolves, configLoaded becomes true.
    await waitFor(() => {
      expect(result.current.configLoaded).toBe(true);
    });

    expect(fetchMock).toHaveBeenCalledWith("http://test.example/config");
  });

  it("awaitToken resolves with null immediately when build-time disabled", async () => {
    const { result } = renderHook(() => useTurnstile(), {
      wrapper: wrapper(""),
    });

    let resolved: string | null | undefined;
    await act(async () => {
      resolved = await result.current.awaitToken(50);
    });
    expect(resolved).toBeNull();
  });
});

describe("TurnstileProvider initial render", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ security: { turnstile_enabled: false } }),
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the hidden widget container only when Turnstile is enabled", () => {
    const { container } = render(
      <TurnstileProvider
        apiUrl="http://test.example"
        siteKeyOverride="test-site-key"
      >
        <div>app</div>
      </TurnstileProvider>,
    );
    // Hidden container is the only direct fixed-position div in our tree.
    const hidden = container.querySelector('div[aria-hidden="true"]');
    expect(hidden).not.toBeNull();
  });

  it("does not render the widget container when build-time disabled", () => {
    const { container } = render(
      <TurnstileProvider apiUrl="http://test.example" siteKeyOverride="">
        <div>app</div>
      </TurnstileProvider>,
    );
    const hidden = container.querySelector('div[aria-hidden="true"]');
    expect(hidden).toBeNull();
  });
});
