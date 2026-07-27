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

// BITB-077: stub the intro modal itself — its own rendering/copy/focus
// behaviour is covered by AboutIntroModal.test.tsx. Here we only assert the
// gating: when Providers decides to mount it, and never alongside the splash.
vi.mock("@/components/AboutIntroModal", () => ({
  default: ({ onDismiss }: { onDismiss: () => void }) => (
    <div data-testid="about-intro" onClick={onDismiss} />
  ),
}));

const ABOUT_INTRO_KEY = "vq:aboutIntroSeen";

import { Providers } from "./providers";

function clearSplashCookie() {
  document.cookie = "splash_seen=; path=/; max-age=0";
}

beforeEach(() => {
  splashMounted = false;
  clearSplashCookie();
  localStorage.clear();
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

describe("Providers About intro modal gating (BITB-077)", () => {
  it("never renders the intro modal while the splash is still showing", async () => {
    render(
      <Providers>
        <div>app</div>
      </Providers>,
    );
    await act(async () => {});

    expect(screen.getByTestId("splash")).toBeTruthy();
    expect(screen.queryByTestId("about-intro")).toBeNull();
  });

  it("shows the intro modal once the splash completes for a first-time visitor", async () => {
    render(
      <Providers>
        <div>app</div>
      </Providers>,
    );
    await act(async () => {});

    await act(async () => {
      screen.getByTestId("splash").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("about-intro")).toBeTruthy();
    });
  });

  it("does not show the intro modal for a visitor who already dismissed it", async () => {
    document.cookie = "splash_seen=1; path=/";
    localStorage.setItem(ABOUT_INTRO_KEY, "1");

    render(
      <Providers>
        <div>app</div>
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("splash")).toBeNull();
    });
    expect(screen.queryByTestId("about-intro")).toBeNull();
  });

  it("shows the intro modal again once the stored version is older than current", async () => {
    document.cookie = "splash_seen=1; path=/";
    localStorage.setItem(ABOUT_INTRO_KEY, "0");

    render(
      <Providers>
        <div>app</div>
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("about-intro")).toBeTruthy();
    });
  });

  it("dismissing the intro modal persists the seen version and hides it", async () => {
    render(
      <Providers>
        <div>app</div>
      </Providers>,
    );
    await act(async () => {
      screen.getByTestId("splash").click();
    });
    await waitFor(() => {
      expect(screen.getByTestId("about-intro")).toBeTruthy();
    });

    await act(async () => {
      screen.getByTestId("about-intro").click();
    });

    expect(screen.queryByTestId("about-intro")).toBeNull();
    expect(localStorage.getItem(ABOUT_INTRO_KEY)).toBe("1");
  });
});
