import { describe, it, expect, vi } from "vitest";
import FooterGate from "./FooterGate";
import { renderWithIntl } from "@/test/i18n-helpers";

const mockPathname = vi.fn();

vi.mock("@/i18n/navigation", () => ({
  usePathname: () => mockPathname(),
  Link: ({
    children,
    href,
  }: React.PropsWithChildren<{ href: string }>) => (
    <a href={href}>{children}</a>
  ),
}));

describe("FooterGate", () => {
  it("renders nothing on the chat page (root path)", () => {
    mockPathname.mockReturnValue("/");
    const { container } = renderWithIntl(<FooterGate />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the page-level Footer on every other route", () => {
    mockPathname.mockReturnValue("/privacy");
    const { container } = renderWithIntl(<FooterGate />);
    expect(container.querySelector("footer")).not.toBeNull();
  });
});
