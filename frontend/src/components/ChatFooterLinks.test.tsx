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

// Same fallback the component falls back to when NEXT_PUBLIC_DONATE_URL is
// unset, which is the case in the test environment (see Footer.tsx).
const DONATE_URL = "https://ko-fi.com/voxquieta";

describe("ChatFooterLinks", () => {
  it("renders the same six links as the page-level Footer", () => {
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
      DONATE_URL,
    ]);
  });

  it("labels each link with the translated Footer/Legal copy", () => {
    renderWithIntl(<ChatFooterLinks />);

    expect(screen.getByText(enMessages.Footer.getApp)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Footer.about)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Legal.navPrivacy)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Legal.navTerms)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Footer.changelog)).toBeInTheDocument();
    expect(screen.getByText(enMessages.Footer.supportUs)).toBeInTheDocument();
  });

  it("renders as a nav, not a second <footer>", () => {
    renderWithIntl(<ChatFooterLinks />);
    expect(document.querySelector("footer")).not.toBeInTheDocument();
  });

  it("renders the support-us link as an external link with target=_blank and rel=noopener noreferrer", () => {
    // The @/i18n/navigation mock above only stubs the internal <Link>; the
    // support-us link is a plain <a> rendered directly by the component, so
    // its real attributes (target/rel) are present and assertable here.
    renderWithIntl(<ChatFooterLinks />);

    const supportLink = screen.getByText(enMessages.Footer.supportUs);
    expect(supportLink.tagName).toBe("A");
    expect(supportLink).toHaveAttribute("href", DONATE_URL);
    expect(supportLink).toHaveAttribute("target", "_blank");
    expect(supportLink).toHaveAttribute("rel", "noopener noreferrer");
  });
});
