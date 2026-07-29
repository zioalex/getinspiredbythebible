import { screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChatFooterLinks from "./ChatFooterLinks";
import { renderWithIntl } from "@/test/i18n-helpers";
import enMessages from "../../messages/en.json";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href }: React.PropsWithChildren<{ href: string }>) => (
    <a href={href}>{children}</a>
  ),
}));

describe("ChatFooterLinks", () => {
  it("renders the same five links as the page-level Footer", () => {
    renderWithIntl(<ChatFooterLinks />);

    const nav = screen.getByTestId("chat-footer-links");
    const hrefs = Array.from(nav.querySelectorAll("a")).map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toEqual([
      "/app",
      "/about",
      "/privacy",
      "/terms",
      "/changelog",
    ]);
  });

  it("labels each link with the translated Footer/Legal copy", () => {
    renderWithIntl(<ChatFooterLinks />);

    expect(screen.getByText(enMessages.Footer.getApp)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Footer.about)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Legal.navPrivacy)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Legal.navTerms)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Footer.changelog)).toBeInTheDocument();
  });

  it("renders as a nav, not a second <footer>", () => {
    renderWithIntl(<ChatFooterLinks />);
    expect(document.querySelector("footer")).not.toBeInTheDocument();
  });
});
