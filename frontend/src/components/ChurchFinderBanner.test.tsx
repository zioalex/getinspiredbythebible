import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChurchFinderBanner from "./ChurchFinderBanner";
import { renderWithIntl } from "@/test/i18n-helpers";

describe("ChurchFinderBanner responsive layout", () => {
  it("renders with responsive flex direction (column on mobile, row on desktop)", () => {
    const { container } = renderWithIntl(
      <ChurchFinderBanner onFindChurch={vi.fn()} onDismiss={vi.fn()} />,
    );
    const banner = container.firstChild as HTMLElement;
    expect(banner.className).toContain("flex-col");
    expect(banner.className).toContain("sm:flex-row");
  });

  it("renders with responsive alignment", () => {
    const { container } = renderWithIntl(
      <ChurchFinderBanner onFindChurch={vi.fn()} onDismiss={vi.fn()} />,
    );
    const banner = container.firstChild as HTMLElement;
    expect(banner.className).toContain("items-start");
    expect(banner.className).toContain("sm:items-center");
  });

  it("renders with responsive gap", () => {
    const { container } = renderWithIntl(
      <ChurchFinderBanner onFindChurch={vi.fn()} onDismiss={vi.fn()} />,
    );
    const banner = container.firstChild as HTMLElement;
    expect(banner.className).toContain("gap-2");
    expect(banner.className).toContain("sm:gap-3");
  });

  it("calls onFindChurch when button is clicked", () => {
    const onFindChurch = vi.fn();
    renderWithIntl(
      <ChurchFinderBanner onFindChurch={onFindChurch} onDismiss={vi.fn()} />,
    );
    fireEvent.click(screen.getByText("Find a Church"));
    expect(onFindChurch).toHaveBeenCalledOnce();
  });

  it("calls onDismiss when dismiss button is clicked", () => {
    const onDismiss = vi.fn();
    renderWithIntl(
      <ChurchFinderBanner onFindChurch={vi.fn()} onDismiss={onDismiss} />,
    );
    fireEvent.click(screen.getByLabelText("Dismiss"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
