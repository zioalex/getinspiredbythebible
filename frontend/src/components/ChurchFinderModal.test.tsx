import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChurchFinderModal from "./ChurchFinderModal";

// Mock the API
vi.mock("@/lib/api", () => ({
  searchChurches: vi.fn(),
}));

describe("ChurchFinderModal responsive layout", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  it("renders modal with responsive rounded corners (full screen on mobile)", () => {
    const { container } = render(<ChurchFinderModal {...defaultProps} />);
    const modal = container.querySelector('[class*="shadow-2xl"]');
    expect(modal).not.toBeNull();
    expect(modal!.className).toContain("sm:rounded-2xl");
    // Should not have standalone rounded-2xl (only sm: prefixed)
    const classes = modal!.className.split(" ");
    expect(classes).not.toContain("rounded-2xl");
  });

  it("renders modal with responsive max-height", () => {
    const { container } = render(<ChurchFinderModal {...defaultProps} />);
    const modal = container.querySelector('[class*="shadow-2xl"]');
    expect(modal!.className).toContain("max-h-screen");
    expect(modal!.className).toContain("sm:max-h-[85vh]");
  });

  it("renders search form with responsive flex direction", () => {
    const { container } = render(<ChurchFinderModal {...defaultProps} />);
    const form = container.querySelector("form");
    expect(form).not.toBeNull();
    expect(form!.className).toContain("flex-col");
    expect(form!.className).toContain("sm:flex-row");
  });

  it("renders header with responsive text sizes", () => {
    render(<ChurchFinderModal {...defaultProps} />);
    const heading = screen.getByText("Find a Church");
    expect(heading.className).toContain("text-xl");
    expect(heading.className).toContain("sm:text-2xl");
  });

  it("does not render when isOpen is false", () => {
    const { container } = render(
      <ChurchFinderModal isOpen={false} onClose={vi.fn()} />,
    );
    expect(container.innerHTML).toBe("");
  });
});
