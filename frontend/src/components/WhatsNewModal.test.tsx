import { screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import WhatsNewModal from "./WhatsNewModal";
import { renderWithIntl } from "@/test/i18n-helpers";
import { useAboutIntroGate } from "@/lib/aboutIntroGate";

// Mock @/i18n/navigation Link
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// BITB-077: default to "clear" (no About intro modal pending) so the
// pre-existing behaviour below is unaffected; the deferral itself is
// covered by the tests at the bottom of this file.
vi.mock("@/lib/aboutIntroGate", () => ({
  useAboutIntroGate: vi.fn(() => "clear"),
}));

const STORAGE_KEY = "vq:lastSeenVersion";

function mockFetch(payload: object) {
  vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok: true,
    json: async () => payload,
  } as Response);
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  // restoreAllMocks() wipes the factory-level default implementation above —
  // re-establish it so every test starts from "gate clear" unless it
  // explicitly overrides this (see the gate-specific describe block below).
  vi.mocked(useAboutIntroGate).mockReturnValue("clear");
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("WhatsNewModal", () => {
  it("renders nothing when version is null", async () => {
    mockFetch({ version: null });
    const { container } = renderWithIntl(<WhatsNewModal />);
    // wait for effect
    await act(async () => {});
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing on first visit and silently stores version", async () => {
    mockFetch({ version: "1.0.0", body: "Initial release" });
    const { container } = renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    // No modal shown — first-ever visit
    expect(container.innerHTML).toBe("");
    // Version silently stored
    expect(localStorage.getItem(STORAGE_KEY)).toBe("1.0.0");
  });

  it("renders nothing when stored version matches current", async () => {
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    mockFetch({ version: "1.0.0", body: "Nothing new" });
    const { container } = renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    expect(container.innerHTML).toBe("");
  });

  it("renders modal when stored version differs from current", async () => {
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    mockFetch({ version: "1.1.0", body: "Something new in 1.1.0" });
    renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    expect(screen.getByRole("dialog")).toBeDefined();
    expect(screen.getByText(/Something new in 1\.1\.0/i)).toBeDefined();
  });

  it("dismisses modal and stores new version on dismiss click", async () => {
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    mockFetch({ version: "1.1.0", body: "New features" });
    renderWithIntl(<WhatsNewModal />);
    await act(async () => {});

    const dismissBtn = screen.getAllByText("Got it")[0];
    await act(async () => {
      dismissBtn.click();
    });

    expect(localStorage.getItem(STORAGE_KEY)).toBe("1.1.0");
  });

  it("renders nothing when fetch fails", async () => {
    vi.spyOn(global, "fetch").mockRejectedValueOnce(new Error("network error"));
    const { container } = renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    expect(container.innerHTML).toBe("");
  });
});

// BITB-077: the About intro modal takes priority — WhatsNewModal must not
// fetch/show while the gate is unresolved or while the intro modal owns
// this session's one interruption.
describe("WhatsNewModal — About intro modal gate", () => {
  it("does not fetch while the gate is still pending", async () => {
    vi.mocked(useAboutIntroGate).mockReturnValue("pending");
    const fetchSpy = vi.spyOn(global, "fetch");

    renderWithIntl(<WhatsNewModal />);
    await act(async () => {});

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("does not fetch or show when the intro modal owns this session", async () => {
    vi.mocked(useAboutIntroGate).mockReturnValue("show-intro");
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    const fetchSpy = vi.spyOn(global, "fetch");

    const { container } = renderWithIntl(<WhatsNewModal />);
    await act(async () => {});

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(container.innerHTML).toBe("");
  });

  it("fetches and can show once the gate clears", async () => {
    vi.mocked(useAboutIntroGate).mockReturnValue("clear");
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    mockFetch({ version: "1.1.0", body: "Something new" });

    renderWithIntl(<WhatsNewModal />);
    await act(async () => {});

    expect(screen.getByRole("dialog")).toBeDefined();
  });
});
