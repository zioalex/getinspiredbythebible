import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import MainMenu from "./MainMenu";
import { renderWithIntl } from "@/test/i18n-helpers";
import enMessages from "../../messages/en.json";

vi.mock("@/components/LanguageSwitcher", () => ({
  default: () => <div data-testid="language-switcher" />,
}));
vi.mock("@/components/TranslationSwitcher", () => ({
  default: () => <div data-testid="translation-switcher" />,
}));
vi.mock("@/i18n/navigation", () => ({
  Link: ({
    children,
    href,
    onClick,
  }: React.PropsWithChildren<{ href: string; onClick?: () => void }>) => (
    <a href={href} onClick={onClick}>
      {children}
    </a>
  ),
}));

function renderMenu() {
  return renderWithIntl(
    <MainMenu
      onOpenHistory={vi.fn()}
      onOpenChurchFinder={vi.fn()}
      translations={[]}
      activeTranslationCode="KJV"
      onSelectTranslation={vi.fn()}
    />,
  );
}

function openMenu() {
  fireEvent.click(
    screen.getByRole("button", { name: enMessages.Chat.mainMenuLabel }),
  );
}

describe("MainMenu support entry", () => {
  it("is absent until the menu is opened", () => {
    renderMenu();
    expect(screen.queryByText(enMessages.Footer.supportUs)).toBeNull();
  });

  it("renders an external link with ref, rel, target and a heart icon", () => {
    renderMenu();
    openMenu();

    const link = screen.getByText(enMessages.Footer.supportUs).closest("a");
    expect(link).toHaveAttribute(
      "href",
      "https://ko-fi.com/voxquieta?ref=web-menu",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link?.querySelector("svg")).not.toBeNull();
  });

  it("is the last link in the menu", () => {
    renderMenu();
    openMenu();

    const links = screen.getAllByRole("link");
    expect(links[links.length - 1]).toHaveTextContent(
      enMessages.Footer.supportUs,
    );
  });

  it("closes the menu when clicked", () => {
    renderMenu();
    openMenu();

    fireEvent.click(screen.getByText(enMessages.Footer.supportUs));
    expect(screen.queryByText(enMessages.Footer.supportUs)).toBeNull();
  });
});
