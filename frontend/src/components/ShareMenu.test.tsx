import { describe, it, expect } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import ShareMenu, { shouldOpenUpward } from "./ShareMenu";
import { renderWithIntl } from "@/test/i18n-helpers";

describe("shouldOpenUpward (BITB-205)", () => {
  it("opens downward by default when there is room below", () => {
    expect(shouldOpenUpward(200, 160, 250, 800)).toBe(false);
  });

  it("flips upward when it does not fit below but fits above", () => {
    expect(shouldOpenUpward(700, 660, 250, 800)).toBe(true);
  });

  it("stays downward when neither side fits and below is larger", () => {
    expect(shouldOpenUpward(100, 60, 900, 800)).toBe(false);
  });
});

describe("ShareMenu", () => {
  it("has a 44px touch target and stacks above neighbours while open", () => {
    const { container } = renderWithIntl(<ShareMenu question="q" answer="a" />);
    const button = screen.getByRole("button", { name: /share/i });
    expect(button).toHaveClass("min-w-[44px]", "min-h-[44px]");
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper).not.toHaveClass("z-20");
    fireEvent.click(button);
    expect(wrapper).toHaveClass("z-20");
  });
});
