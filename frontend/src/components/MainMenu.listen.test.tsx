import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import MainMenu from "./MainMenu";
import { renderWithIntl } from "@/test/i18n-helpers";
import { getShowListen, setShowListen } from "@/lib/ttsPreference";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...rest }: { children: React.ReactNode }) => (
    <a {...rest}>{children}</a>
  ),
}));
vi.mock("@/components/LanguageSwitcher", () => ({ default: () => null }));
vi.mock("@/components/TranslationSwitcher", () => ({ default: () => null }));

function renderMenu() {
  renderWithIntl(
    <MainMenu
      onOpenHistory={() => {}}
      onOpenChurchFinder={() => {}}
      translations={[]}
      activeTranslationCode="KJV"
      onSelectTranslation={() => {}}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /menu/i }));
}

beforeEach(() => localStorage.clear());

describe("MainMenu — Show Listen button toggle (BITB-119)", () => {
  it("is on by default and exposes switch semantics", () => {
    renderMenu();
    const toggle = screen.getByRole("switch", { name: /show listen button/i });
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("toggles off and persists, then back on", () => {
    renderMenu();
    const toggle = screen.getByRole("switch", { name: /show listen button/i });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(getShowListen()).toBe(false);
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(getShowListen()).toBe(true);
  });

  it("reflects a previously stored 'off' preference", () => {
    setShowListen(false);
    renderMenu();
    expect(
      screen.getByRole("switch", { name: /show listen button/i }),
    ).toHaveAttribute("aria-checked", "false");
  });
});
