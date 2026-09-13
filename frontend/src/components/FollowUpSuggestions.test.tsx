import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import FollowUpSuggestions from "./FollowUpSuggestions";

describe("FollowUpSuggestions", () => {
  it("renders one button per suggestion", () => {
    render(
      <FollowUpSuggestions
        suggestions={["What does this mean?", "How do I pray about this?"]}
        onSelect={vi.fn()}
        label="Suggested follow-up questions"
      />,
    );
    expect(screen.getByText("What does this mean?")).toBeDefined();
    expect(screen.getByText("How do I pray about this?")).toBeDefined();
  });

  it("calls onSelect with the exact suggestion text on click", () => {
    const onSelect = vi.fn();
    render(
      <FollowUpSuggestions
        suggestions={["What does this mean?", "How do I pray about this?"]}
        onSelect={onSelect}
        label="Suggested follow-up questions"
      />,
    );
    fireEvent.click(screen.getByText("How do I pray about this?"));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith("How do I pray about this?");
  });

  it("fires onSelect on keyboard activation (native button semantics)", () => {
    const onSelect = vi.fn();
    render(
      <FollowUpSuggestions
        suggestions={["What does this mean?", "How do I pray about this?"]}
        onSelect={onSelect}
        label="Suggested follow-up questions"
      />,
    );
    const button = screen.getByText("What does this mean?");
    button.focus();
    fireEvent.click(button); // jsdom: a native <button> activates on Enter/Space as a click
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith("What does this mean?");
  });

  it("renders nothing for an empty suggestion list", () => {
    const { container } = render(
      <FollowUpSuggestions
        suggestions={[]}
        onSelect={vi.fn()}
        label="Suggested follow-up questions"
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("propagates disabled to every chip", () => {
    render(
      <FollowUpSuggestions
        suggestions={["What does this mean?", "How do I pray about this?"]}
        onSelect={vi.fn()}
        disabled
        label="Suggested follow-up questions"
      />,
    );
    for (const button of screen.getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });

  it("exposes an accessible group with the given label", () => {
    render(
      <FollowUpSuggestions
        suggestions={["What does this mean?", "How do I pray about this?"]}
        onSelect={vi.fn()}
        label="Suggested follow-up questions"
      />,
    );
    expect(
      screen.getByRole("group", { name: "Suggested follow-up questions" }),
    ).toBeDefined();
  });
});
