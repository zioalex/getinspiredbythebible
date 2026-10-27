import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ContactModal from "./ContactModal";
import { renderWithIntl } from "@/test/i18n-helpers";
import enMessages from "../../messages/en.json";

vi.mock("@/lib/api", () => ({
  submitContactForm: vi.fn(),
  InvalidContactEmailError: class InvalidContactEmailError extends Error {},
}));

// #1224: the menu's "Get in Touch" entry opens the contact form in a dialog.
describe("ContactModal", () => {
  it("renders nothing when closed", () => {
    renderWithIntl(<ContactModal isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows the form already expanded, without the collapsible toggle", () => {
    renderWithIntl(<ContactModal isOpen onClose={vi.fn()} />);
    const dialog = screen.getByRole("dialog", {
      name: enMessages.Contact.getInTouch,
    });
    expect(dialog).toBeInTheDocument();
    expect(
      screen.getByLabelText(enMessages.Contact.messageLabel),
    ).toBeInTheDocument();
    // Only the heading carries the title; no expand/collapse button.
    expect(
      screen.queryByRole("button", { name: enMessages.Contact.getInTouch }),
    ).toBeNull();
  });

  it("closes via the close button and Escape", () => {
    const onClose = vi.fn();
    renderWithIntl(<ContactModal isOpen onClose={onClose} />);
    fireEvent.click(
      screen.getByRole("button", { name: enMessages.Contact.close }),
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
