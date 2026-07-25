import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/turnstile", () => ({
  TurnstileProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useTurnstile: () => ({
    token: null,
    refreshToken: () => {},
    awaitToken: async () => null,
  }),
}));
vi.mock("@/lib/api", () => ({
  setTurnstileToken: () => {},
  setOnTokenConsumed: () => {},
  setTurnstileAwaiter: () => {},
}));
vi.mock("@/lib/clientErrorReporter", () => ({ reportClientError: () => {} }));

let splashMounted = false;
vi.mock("@/components/SplashScreen", () => ({
  SplashScreen: ({ onComplete }: { onComplete: () => void }) => {
    splashMounted = true;
    return <div data-testid="splash" onClick={onComplete} />;
  },
}));

import { Providers } from "./providers";

function clearSplashCookie() {
  document.cookie = "splash_seen=; path=/; max-age=0";
}

beforeEach(() => {
  splashMounted = false;
  clearSplashCookie();
});

describe("Providers splash gating (BITB-069)", () => {
  it("first-time visitor (no cookie) shows the splash", async () => {
    render(
      <Providers>
        <div>app</div>
      </Providers>,
    );
    await act(async () => {});
    expect(screen.getByTestId("splash")).toBeTruthy();
  });

  it("returning visitor (cookie set) renders the splash on the first pass then skips it after the effect — no SSR/CSR divergence", async () => {
    document.cookie = "splash_seen=1; path=/";
    render(
      <Providers>
        <div>app</div>
      </Providers>,
    );

    expect(splashMounted).toBe(true);

    await waitFor(() => {
      expect(screen.queryByTestId("splash")).toBeNull();
    });
  });
});
