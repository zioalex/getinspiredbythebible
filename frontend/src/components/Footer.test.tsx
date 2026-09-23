import { screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Footer from "./Footer";
import { renderWithIntl } from "@/test/i18n-helpers";
import enMessages from "../../messages/en.json";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href }: React.PropsWithChildren<{ href: string }>) => (
    <a href={href}>{children}</a>
  ),
}));

describe("Footer", () => {
  it("renders six links, the last one being the external Support us link", () => {
    renderWithIntl(<Footer />);

    const footer = screen.getByRole("contentinfo");
    const hrefs = Array.from(footer.querySelectorAll("a")).map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toEqual([
      "/app",
      "/about",
      "/privacy",
      "/terms",
      "/changelog",
      "https://ko-fi.com/voxquieta",
    ]);
  });

  it("labels the Support us link with the translated Footer.supportUs copy", () => {
    renderWithIntl(<Footer />);
    expect(screen.getByText(enMessages.Footer.supportUs)).toBeInTheDocument();
  });

  it("opens the Support us link in a new tab without leaking a referrer/opener", () => {
    renderWithIntl(<Footer />);

    const supportLink = screen
      .getByText(enMessages.Footer.supportUs)
      .closest("a");
    expect(supportLink).not.toBeNull();
    expect(supportLink).toHaveAttribute("target", "_blank");
    expect(supportLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders the other five links as internal (no target/rel attributes)", () => {
    renderWithIntl(<Footer />);

    const internalLink = screen
      .getByText(enMessages.Footer.getApp)
      .closest("a");
    expect(internalLink).not.toBeNull();
    expect(internalLink).not.toHaveAttribute("target");
    expect(internalLink).not.toHaveAttribute("rel");
  });
});
