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
    className,
  }: React.PropsWithChildren<{
    href: string;
    onClick?: () => void;
    className?: string;
  }>) => (
    <a href={href} onClick={onClick} className={className}>
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

// #1224: below lg the chat page drops its footer link row and inline contact
// form, so the menu carries them next to About / Support us.
describe("MainMenu entries moved from the chat footer", () => {
  function renderWithContact(onOpenContact = vi.fn()) {
    renderWithIntl(
      <MainMenu
        onOpenHistory={vi.fn()}
        onOpenChurchFinder={vi.fn()}
        translations={[]}
        activeTranslationCode="KJV"
        onSelectTranslation={vi.fn()}
        onOpenContact={onOpenContact}
      />,
    );
    openMenu();
    return onOpenContact;
  }

  it("links to app, privacy, terms and changelog, mobile/tablet only", () => {
    renderWithContact();
    for (const [href, label] of [
      ["/app", enMessages.Footer.getApp],
      ["/privacy", enMessages.Legal.navPrivacy],
      ["/terms", enMessages.Legal.navTerms],
      ["/changelog", enMessages.Footer.changelog],
    ]) {
      const link = screen.getByText(label).closest("a");
      expect(link).toHaveAttribute("href", href);
      expect(link).toHaveClass("lg:hidden");
    }
    // About and Support us stay visible at every breakpoint.
    expect(
      screen.getByText(enMessages.Footer.about).closest("a"),
    ).not.toHaveClass("lg:hidden");
  });

  it("places the moved entries between About and Support us", () => {
    renderWithContact();
    const panel = screen.getByTestId("main-menu-panel");
    const labels = Array.from(panel.querySelectorAll("a, button")).map(
      (el) => el.textContent,
    );
    const about = labels.indexOf(enMessages.Footer.about);
    const contact = labels.indexOf(enMessages.Contact.getInTouch);
    const privacy = labels.indexOf(enMessages.Legal.navPrivacy);
    const support = labels.indexOf(enMessages.Footer.supportUs);
    expect(about).toBeGreaterThan(-1);
    expect(contact).toBeGreaterThan(about);
    expect(privacy).toBeGreaterThan(contact);
    expect(support).toBeGreaterThan(privacy);
  });

  it("opens the contact form and closes the menu", () => {
    const onOpenContact = renderWithContact();
    const btn = screen.getByRole("button", {
      name: enMessages.Contact.getInTouch,
    });
    expect(btn).toHaveClass("lg:hidden");
    fireEvent.click(btn);
    expect(onOpenContact).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("main-menu-panel")).toBeNull();
  });

  it("omits Get in Touch when no handler is provided", () => {
    renderMenu();
    openMenu();
    expect(screen.queryByText(enMessages.Contact.getInTouch)).toBeNull();
  });

  it("panel is bounded to the viewport so its content cannot overflow (#1223)", () => {
    renderMenu();
    openMenu();
    const panel = screen.getByTestId("main-menu-panel");
    expect(panel.className).toContain("max-w-[calc(100vw-1.5rem)]");
    expect(panel).toHaveClass("overflow-x-hidden", "overflow-y-auto");
  });
});
