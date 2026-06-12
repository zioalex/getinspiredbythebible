import { screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import FeedbackControls, { FEEDBACK_RETHINK_MS } from "./FeedbackControls";
import { renderWithIntl } from "@/test/i18n-helpers";

describe("FeedbackControls", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms));

  it("does not submit immediately when a thumb is tapped", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs up"));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Undo")).toBeDefined();
  });

  it("commits the rating once the rethink window elapses", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs up"));
    advance(FEEDBACK_RETHINK_MS);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("positive", "", undefined);
  });

  it("Undo cancels the pending feedback — nothing is sent", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));
    fireEvent.click(screen.getByText("Undo"));
    advance(FEEDBACK_RETHINK_MS * 2);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("re-tapping the same thumb undoes it", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    const up = screen.getByLabelText("Thumbs up");
    fireEvent.click(up);
    fireEvent.click(up);
    advance(FEEDBACK_RETHINK_MS * 2);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows the maintainer-sharing notice on thumbs-down only", () => {
    const onSubmit = vi.fn();
    const { rerender } = renderWithIntl(
      <FeedbackControls onSubmit={onSubmit} />,
    );
    fireEvent.click(screen.getByLabelText("Thumbs up"));
    expect(
      screen.queryByText(
        "Your message will be shared with the app's maintainer.",
      ),
    ).toBeNull();

    rerender(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));
    expect(
      screen.getByText(
        "Your message will be shared with the app's maintainer.",
      ),
    ).toBeDefined();
  });

  it("shows the comment field immediately — no separate 'Add a comment' step", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));

    expect(
      screen.getByPlaceholderText(
        "The response didn't address my specific concern...",
      ),
    ).toBeDefined();
    expect(screen.queryByText("Add a comment (optional)")).toBeNull();
    expect(screen.getByText("Send")).toBeDefined();
  });

  it("pauses the countdown when the comment field is focused and sends on Send", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));

    const textarea = screen.getByPlaceholderText(
      "The response didn't address my specific concern...",
    );
    // Focusing the field pauses the countdown: advancing time must not auto-submit.
    fireEvent.focus(textarea);
    advance(FEEDBACK_RETHINK_MS * 2);
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(textarea, { target: { value: "Wrong verse" } });
    fireEvent.click(screen.getByText("Send"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("negative", "Wrong verse", undefined);
  });

  it("submits exactly once even if the timer fires after a Send", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs up"));
    advance(FEEDBACK_RETHINK_MS);
    advance(FEEDBACK_RETHINK_MS);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("shows the thanks state and locks the thumbs when feedback is given", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} given="positive" />);
    expect(screen.getByText("Thanks for your feedback!")).toBeDefined();
    expect(screen.getByLabelText("Thumbs up")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Thumbs down")).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("renders reason chips on thumbs-down but NOT on thumbs-up", () => {
    const onSubmit = vi.fn();
    const { rerender } = renderWithIntl(
      <FeedbackControls onSubmit={onSubmit} />,
    );

    // thumbs-up: no reason prompt
    fireEvent.click(screen.getByLabelText("Thumbs up"));
    expect(screen.queryByText("What went wrong?")).toBeNull();

    rerender(<FeedbackControls onSubmit={onSubmit} />);

    // thumbs-down: reason prompt and chip labels present
    fireEvent.click(screen.getByLabelText("Thumbs down"));
    expect(screen.getByText("What went wrong?")).toBeDefined();
    expect(screen.getByText("Inaccurate")).toBeDefined();
    expect(screen.getByText("Unhelpful")).toBeDefined();
    expect(screen.getByText("Wrong verse")).toBeDefined();
    expect(screen.getByText("Tone")).toBeDefined();
    expect(screen.getAllByText("Other")).toBeDefined();
  });

  it("selecting a reason chip and clicking Send passes the reason to onSubmit", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));

    // Select the "Inaccurate" chip
    fireEvent.click(screen.getByText("Inaccurate"));

    fireEvent.click(screen.getByText("Send"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("negative", "", "inaccurate");
  });

  it("de-selecting a chip sends undefined reason", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));

    // Select then deselect
    fireEvent.click(screen.getByText("Inaccurate"));
    fireEvent.click(screen.getByText("Inaccurate"));

    fireEvent.click(screen.getByText("Send"));
    expect(onSubmit).toHaveBeenCalledWith("negative", "", undefined);
  });

  it("auto-commit on thumbs-down still works without selecting a chip", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));
    advance(FEEDBACK_RETHINK_MS);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("negative", "", undefined);
  });

  it("reason is passed with comment when both are set", () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackControls onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Thumbs down"));

    fireEvent.click(screen.getByText("Tone"));

    const textarea = screen.getByPlaceholderText(
      "The response didn't address my specific concern...",
    );
    fireEvent.focus(textarea);
    fireEvent.change(textarea, { target: { value: "Too formal" } });
    fireEvent.click(screen.getByText("Send"));
    expect(onSubmit).toHaveBeenCalledWith("negative", "Too formal", "tone");
  });
});
