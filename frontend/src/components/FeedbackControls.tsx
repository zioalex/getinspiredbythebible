"use client";

import React, { useEffect, useRef, useState } from "react";
import { ThumbsUp, ThumbsDown, Undo2, AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * Length of the "rethink" window after a thumb is tapped, before the rating is
 * actually sent. Kept as a single named constant so it is easy to tune.
 */
export const FEEDBACK_RETHINK_MS = 10_000;

type Rating = "positive" | "negative";

interface FeedbackControlsProps {
  /** Called exactly once per rating, when the feedback is actually committed. */
  onSubmit: (rating: Rating, comment: string, reason?: string) => void;
  /** Rating already recorded for this message (locks the controls). */
  given?: Rating | null;
  disabled?: boolean;
  /** Rendered at the trailing edge of the thumbs row (e.g. the share menu). */
  trailing?: React.ReactNode;
}

/**
 * Inline, non-blocking feedback controls.
 *
 * Tapping a thumb does not send immediately: a single panel opens with the
 * comment field, a quiet progress bar, Undo and Send. The rating auto-commits
 * after ~10s (`FEEDBACK_RETHINK_MS`) if untouched; focusing the comment field
 * pauses the countdown so the user is never cut off mid-sentence, and Send
 * commits immediately. A `committedRef` guard ensures exactly one request per
 * rating — never a "rating now, comment later" double-send.
 */
export default function FeedbackControls({
  onSubmit,
  given = null,
  disabled = false,
  trailing,
}: FeedbackControlsProps) {
  const t = useTranslations("Feedback");

  const [pending, setPending] = useState<Rating | null>(null);
  const [comment, setComment] = useState("");
  const [reason, setReason] = useState<string | null>(null);
  const [commentOpen, setCommentOpen] = useState(false);
  const [barShrunk, setBarShrunk] = useState(false);
  const [localGiven, setLocalGiven] = useState<Rating | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const committedRef = useRef(false);
  // Keep a mutable ref in sync with reason state so the auto-commit timer
  // callback can read the current value even after state updates.
  const reasonRef = useRef<string | null>(null);

  // The recorded rating drives the final UI; until the parent confirms we show
  // an optimistic local copy so the "thanks" state appears instantly.
  const effectiveGiven = given ?? localGiven;

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  // Clean up the pending timer on unmount.
  useEffect(() => clearTimer, []);

  // Animate the progress bar shrinking once a countdown is active. The commit
  // itself is driven by the timer below, not by this animation, so disabling
  // motion (reduced-motion / fake timers in tests) does not affect timing.
  useEffect(() => {
    if (pending && !commentOpen) {
      const id = requestAnimationFrame(() => setBarShrunk(true));
      return () => cancelAnimationFrame(id);
    }
    setBarShrunk(false);
  }, [pending, commentOpen]);

  // Wrapper that keeps reasonRef in sync whenever reason state changes.
  const updateReason = (value: string | null) => {
    reasonRef.current = value;
    setReason(value);
  };

  const commit = (rating: Rating, text: string) => {
    if (committedRef.current) return;
    committedRef.current = true;
    clearTimer();
    const committedReason =
      rating === "negative" ? (reasonRef.current ?? undefined) : undefined;
    setLocalGiven(rating);
    setPending(null);
    setCommentOpen(false);
    onSubmit(rating, text.trim(), committedReason);
  };

  const startPending = (rating: Rating) => {
    clearTimer();
    committedRef.current = false;
    setComment("");
    updateReason(null);
    setCommentOpen(false);
    setPending(rating);
    timerRef.current = setTimeout(
      () => commit(rating, ""),
      FEEDBACK_RETHINK_MS,
    );
  };

  const cancel = () => {
    clearTimer();
    committedRef.current = false;
    setPending(null);
    setComment("");
    updateReason(null);
    setCommentOpen(false);
  };

  const handleThumb = (rating: Rating) => {
    if (effectiveGiven || disabled) return;
    // Re-tapping the pending thumb undoes it; otherwise (re)start the window.
    if (pending === rating) {
      cancel();
    } else {
      startPending(rating);
    }
  };

  const pauseCountdown = () => {
    // Focusing the comment field pauses the countdown — we never auto-send out
    // from under someone who is mid-sentence. (Ignore the field and the rating
    // still auto-commits when the window elapses.)
    clearTimer();
    setCommentOpen(true);
  };

  // Static class strings only — Tailwind purges dynamically-built class names.
  const thumbClass = (rating: Rating) => {
    const active = effectiveGiven === rating || pending === rating;
    if (active) {
      return rating === "positive"
        ? "bg-green-100 text-green-600"
        : "bg-red-100 text-red-600";
    }
    if (effectiveGiven) {
      return "text-gray-300 cursor-not-allowed";
    }
    return rating === "positive"
      ? "text-gray-400 hover:text-green-600 hover:bg-green-50"
      : "text-gray-400 hover:text-red-600 hover:bg-red-50";
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-400 mr-1">{t("wasHelpful")}</span>
        <button
          onClick={() => handleThumb("positive")}
          disabled={disabled || effectiveGiven !== null}
          className={`p-1.5 rounded-lg transition-colors ${thumbClass("positive")}`}
          aria-label={t("thumbsUp")}
          aria-pressed={effectiveGiven === "positive" || pending === "positive"}
          title={t("helpfulTitle")}
        >
          <ThumbsUp
            className={`w-4 h-4 ${
              effectiveGiven === "positive" || pending === "positive"
                ? "fill-current"
                : ""
            }`}
          />
        </button>
        <button
          onClick={() => handleThumb("negative")}
          disabled={disabled || effectiveGiven !== null}
          className={`p-1.5 rounded-lg transition-colors ${thumbClass("negative")}`}
          aria-label={t("thumbsDown")}
          aria-pressed={effectiveGiven === "negative" || pending === "negative"}
          title={t("improveTitle")}
        >
          <ThumbsDown
            className={`w-4 h-4 ${
              effectiveGiven === "negative" || pending === "negative"
                ? "fill-current"
                : ""
            }`}
          />
        </button>
        {effectiveGiven && (
          <span className="text-xs text-gray-400 ml-1">{t("thanks")}</span>
        )}
        {trailing && <div className="ml-auto">{trailing}</div>}
      </div>

      {pending && !effectiveGiven && (
        <div className="mt-2 rounded-lg border border-gray-200 bg-gray-50 p-2 sm:p-3">
          {/* Maintainer-sharing notice is always shown on thumbs-down, even
              before a comment is written. */}
          {pending === "negative" && (
            <p className="flex items-start gap-1.5 text-xs text-amber-800 mb-2">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-600" />
              <span>{t("maintainerNotice")}</span>
            </p>
          )}

          {/* "What went wrong?" reason chips — thumbs-down only, optional */}
          {pending === "negative" && (
            <div className="mb-2">
              <p className="text-xs text-gray-500 mb-1.5">
                {t("reasonPrompt")}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(
                  [
                    ["inaccurate", t("reasonInaccurate")],
                    ["unhelpful", t("reasonUnhelpful")],
                    ["wrong_verse", t("reasonWrongVerse")],
                    ["tone", t("reasonTone")],
                    ["other", t("reasonOther")],
                  ] as [string, string][]
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() =>
                      updateReason(reason === value ? null : value)
                    }
                    className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                      reason === value
                        ? "bg-red-100 text-red-700 border-red-300"
                        : "bg-white text-gray-600 border-gray-300 hover:border-red-300 hover:text-red-600"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Single panel: the comment field is shown immediately. Focusing it
              pauses the countdown (see pauseCountdown); ignore it and the rating
              auto-commits when the window elapses. */}
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onFocus={pauseCountdown}
            placeholder={
              pending === "positive"
                ? t("positivePlaceholder")
                : t("negativePlaceholder")
            }
            rows={3}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
          />
          <p className="text-[11px] text-gray-400 mt-1">{t("privacyNotice")}</p>

          <div className="flex items-center gap-3 mt-2">
            {/* Countdown bar — visible only while the rethink window is running,
                i.e. before the user focuses the comment to pause it. */}
            {!commentOpen ? (
              <div
                className="flex-1 h-1 rounded bg-gray-200 overflow-hidden"
                role="progressbar"
                aria-hidden="true"
              >
                <div
                  className="h-full bg-primary-500 ease-linear transition-[width] motion-reduce:transition-none"
                  style={{
                    width: barShrunk ? "0%" : "100%",
                    transitionDuration: `${FEEDBACK_RETHINK_MS}ms`,
                  }}
                />
              </div>
            ) : (
              <div className="flex-1" />
            )}
            <button
              type="button"
              onClick={cancel}
              className="inline-flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-800 whitespace-nowrap"
            >
              <Undo2 className="w-3.5 h-3.5" />
              {t("undo")}
            </button>
            <button
              type="button"
              onClick={() => commit(pending, comment)}
              className="px-4 py-1.5 text-xs text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
            >
              {t("send")}
            </button>
            {!commentOpen && (
              <span className="sr-only" role="status" aria-live="polite">
                {t("sending")}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
