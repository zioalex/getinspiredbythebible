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

// Default base (NEXT_PUBLIC_DONATE_URL unset in tests) plus the chat-footer ref
// (see donateUrl.ts, BITB-168).
const DONATE_URL = "https://ko-fi.com/voxquieta?ref=web-chat-footer";

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

  it("adds a decorative heart to the support link without raising its visual weight", () => {
    renderWithIntl(<ChatFooterLinks />);

    const supportLink = screen.getByText(enMessages.Footer.supportUs);
    expect(supportLink.querySelector("svg[aria-hidden='true']")).not.toBeNull();
    expect(supportLink.className).not.toMatch(
      /font-semibold|font-bold|text-base/,
    );
    const parent = supportLink.parentElement as HTMLElement;
    expect(parent.className).toContain("text-[11px]");
    expect(parent.className).toContain("text-gray-400");
  });

  it("renders no icon on internal links", () => {
    renderWithIntl(<ChatFooterLinks />);
    const internal = screen.getByText(enMessages.Footer.getApp).closest("a");
    expect(internal?.querySelector("svg")).toBeNull();
  });
});
