import { screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ContactForm from "./ContactForm";
import { renderWithIntl } from "@/test/i18n-helpers";
import { submitContactForm } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  submitContactForm: vi.fn(),
}));

const mockSubmit = vi.mocked(submitContactForm);

describe("ContactForm", () => {
  beforeEach(() => {
    mockSubmit.mockReset();
  });

  it("starts collapsed and expands when 'Get in Touch' clicked", () => {
    renderWithIntl(<ContactForm />);
    // Form should not be visible initially
    expect(screen.queryByLabelText("Message")).toBeNull();

    fireEvent.click(screen.getByText("Get in Touch"));
    expect(screen.getByLabelText("Message")).toBeDefined();
  });

  it("shows email link when expanded", () => {
    renderWithIntl(<ContactForm />);
    fireEvent.click(screen.getByText("Get in Touch"));
    expect(screen.getByText("getinspiredbythebible@ai4you.sh")).toBeDefined();
  });

  it("submit button is disabled when message is empty", () => {
    renderWithIntl(<ContactForm />);
    fireEvent.click(screen.getByText("Get in Touch"));
    const submitBtn = screen.getByText("Send Message").closest("button")!;
    expect(submitBtn.disabled).toBe(true);
  });

  it("successful submission shows success message", async () => {
    mockSubmit.mockResolvedValue({
      id: 1,
      subject: "spiritual",
      created_at: "2024-01-01",
    });

    renderWithIntl(<ContactForm />);
    fireEvent.click(screen.getByText("Get in Touch"));

    const messageInput = screen.getByLabelText("Message");
    fireEvent.change(messageInput, { target: { value: "Hello!" } });
    fireEvent.submit(messageInput.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Message sent successfully!")).toBeDefined();
    });
  });

  it("'Send another' resets the form after success", async () => {
    mockSubmit.mockResolvedValue({
      id: 1,
      subject: "spiritual",
      created_at: "2024-01-01",
    });

    renderWithIntl(<ContactForm />);
    fireEvent.click(screen.getByText("Get in Touch"));

    const messageInput = screen.getByLabelText("Message");
    fireEvent.change(messageInput, { target: { value: "Test" } });
    fireEvent.submit(messageInput.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Send another")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Send another"));
    expect(screen.getByLabelText("Message")).toBeDefined();
  });

  it("API error shows error message", async () => {
    mockSubmit.mockRejectedValue(new Error("API error"));

    renderWithIntl(<ContactForm />);
    fireEvent.click(screen.getByText("Get in Touch"));

    const messageInput = screen.getByLabelText("Message");
    fireEvent.change(messageInput, { target: { value: "Hello!" } });
    fireEvent.submit(messageInput.closest("form")!);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Failed to send message. Please try again or email us directly.",
        ),
      ).toBeDefined();
    });
  });

  it("all 5 subject options render", () => {
    renderWithIntl(<ContactForm />);
    fireEvent.click(screen.getByText("Get in Touch"));

    const select = screen.getByLabelText("Subject") as HTMLSelectElement;
    const options = select.querySelectorAll("option");
    expect(options).toHaveLength(5);
  });

  it("submits correct payload", async () => {
    mockSubmit.mockResolvedValue({
      id: 1,
      subject: "bug",
      created_at: "2024-01-01",
    });

    renderWithIntl(<ContactForm />);
    fireEvent.click(screen.getByText("Get in Touch"));

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });

    const subjectSelect = screen.getByLabelText("Subject");
    fireEvent.change(subjectSelect, { target: { value: "bug" } });

    const messageInput = screen.getByLabelText("Message");
    fireEvent.change(messageInput, { target: { value: "Found a bug" } });
    fireEvent.submit(messageInput.closest("form")!);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          email: "test@example.com",
          subject: "bug",
          message: "Found a bug",
        }),
      );
    });
  });
});
