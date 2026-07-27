import { screen, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AboutIntroModal from "./AboutIntroModal";
import { renderWithIntl } from "@/test/i18n-helpers";
import enMessages from "../../messages/en.json";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    children,
    href,
    onClick,
  }: React.PropsWithChildren<{ href: string; onClick?: () => void }>) => (
    <a href={href} onClick={onClick}>
      {children}
    </a>
  ),
}));

describe("AboutIntroModal", () => {
  it("renders the condensed intro copy and title", () => {
    renderWithIntl(<AboutIntroModal onDismiss={vi.fn()} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(enMessages.About.introTitle)).toBeInTheDocument();
    expect(screen.getByText(enMessages.About.introBody)).toBeInTheDocument();
  });

  it("primary action links to the localized /about page", () => {
    renderWithIntl(<AboutIntroModal onDismiss={vi.fn()} />);

    const primary = screen.getByText(enMessages.About.introPrimaryCta);
    expect(primary.closest("a")).toHaveAttribute("href", "/about");
  });

  it("calls onDismiss when the secondary action is clicked", () => {
    const onDismiss = vi.fn();
    renderWithIntl(<AboutIntroModal onDismiss={onDismiss} />);

    fireEvent.click(screen.getByText(enMessages.About.introSecondaryCta));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("calls onDismiss when the close button is clicked", () => {
    const onDismiss = vi.fn();
    renderWithIntl(<AboutIntroModal onDismiss={onDismiss} />);

    fireEvent.click(screen.getByLabelText(enMessages.About.introDismissLabel));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("calls onDismiss when clicking the backdrop", () => {
    const onDismiss = vi.fn();
    renderWithIntl(<AboutIntroModal onDismiss={onDismiss} />);

    fireEvent.click(screen.getByRole("dialog"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("does not dismiss when clicking inside the dialog panel", () => {
    const onDismiss = vi.fn();
    renderWithIntl(<AboutIntroModal onDismiss={onDismiss} />);

    fireEvent.click(screen.getByText(enMessages.About.introTitle));
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("calls onDismiss on Escape", () => {
    const onDismiss = vi.fn();
    renderWithIntl(<AboutIntroModal onDismiss={onDismiss} />);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("moves focus into the dialog on mount", async () => {
    renderWithIntl(<AboutIntroModal onDismiss={vi.fn()} />);

    await act(async () => {});
    expect(screen.getByRole("dialog").firstElementChild).toHaveFocus();
  });

  it("restores focus to the previously focused element on unmount", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    expect(trigger).toHaveFocus();

    const { unmount } = renderWithIntl(<AboutIntroModal onDismiss={vi.fn()} />);
    unmount();

    expect(trigger).toHaveFocus();
    document.body.removeChild(trigger);
  });
});
