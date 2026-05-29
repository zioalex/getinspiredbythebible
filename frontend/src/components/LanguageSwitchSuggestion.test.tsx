import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import LanguageSwitchSuggestion from "./LanguageSwitchSuggestion";
import { renderWithIntl } from "@/test/i18n-helpers";

// LanguageSwitcher.tsx uses Next.js navigation hooks — mock them so the
// imported localeLabels constant doesn't pull in Next.js at test-time.
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
  redirect: vi.fn(),
  usePathname: vi.fn().mockReturnValue("/"),
  useRouter: vi.fn().mockReturnValue({ replace: vi.fn() }),
}));

describe("LanguageSwitchSuggestion", () => {
  it("shows the human-readable language name for a known locale", () => {
    renderWithIntl(
      <LanguageSwitchSuggestion
        suggestedLocale="it"
        onSwitch={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText(/Italiano/)).toBeInTheDocument();
  });

  it("calls onSwitch when Switch button is clicked", () => {
    const onSwitch = vi.fn();
    renderWithIntl(
      <LanguageSwitchSuggestion
        suggestedLocale="it"
        onSwitch={onSwitch}
        onDismiss={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Switch" }));
    expect(onSwitch).toHaveBeenCalledOnce();
  });

  it("calls onDismiss when dismiss button is clicked", () => {
    const onDismiss = vi.fn();
    renderWithIntl(
      <LanguageSwitchSuggestion
        suggestedLocale="it"
        onSwitch={vi.fn()}
        onDismiss={onDismiss}
      />,
    );
    fireEvent.click(screen.getByLabelText("Dismiss"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("falls back to the raw locale code for unknown locales", () => {
    renderWithIntl(
      <LanguageSwitchSuggestion
        suggestedLocale="xx"
        onSwitch={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText(/xx/)).toBeInTheDocument();
  });

  it("has responsive flex layout", () => {
    const { container } = renderWithIntl(
      <LanguageSwitchSuggestion
        suggestedLocale="de"
        onSwitch={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    const banner = container.firstChild as HTMLElement;
    expect(banner.className).toContain("flex-col");
    expect(banner.className).toContain("sm:flex-row");
  });
});
