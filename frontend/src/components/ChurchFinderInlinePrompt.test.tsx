import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChurchFinderInlinePrompt from "./ChurchFinderInlinePrompt";
import { renderWithIntl } from "@/test/i18n-helpers";

describe("ChurchFinderInlinePrompt", () => {
  it("renders inline text", () => {
    renderWithIntl(
      <ChurchFinderInlinePrompt onFindChurch={vi.fn()} onDismiss={vi.fn()} />,
    );
    expect(
      screen.getByText("Looking for a prayer community or church?"),
    ).toBeDefined();
  });

  it("renders CTA button", () => {
    renderWithIntl(
      <ChurchFinderInlinePrompt onFindChurch={vi.fn()} onDismiss={vi.fn()} />,
    );
    expect(screen.getByText("Find one nearby")).toBeDefined();
  });

  it("calls onFindChurch when CTA clicked", () => {
    const onFindChurch = vi.fn();
    renderWithIntl(
      <ChurchFinderInlinePrompt
        onFindChurch={onFindChurch}
        onDismiss={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("Find one nearby"));
    expect(onFindChurch).toHaveBeenCalledOnce();
  });

  it("calls onDismiss when dismiss button clicked", () => {
    const onDismiss = vi.fn();
    renderWithIntl(
      <ChurchFinderInlinePrompt onFindChurch={vi.fn()} onDismiss={onDismiss} />,
    );
    fireEvent.click(screen.getByLabelText("Dismiss"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
