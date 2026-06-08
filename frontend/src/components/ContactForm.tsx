"use client";

import React, { useState } from "react";
import {
  Mail,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Send,
  Check,
  AlertCircle,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { submitContactForm, ContactRequest } from "@/lib/api";

const CONTACT_EMAIL = "contact@voxquieta.org";

type Subject = "spiritual" | "bug" | "feature" | "feedback" | "other";

export default function ContactForm() {
  const t = useTranslations("Contact");

  const subjectOptions: { value: Subject; label: string }[] = [
    { value: "spiritual", label: t("subjectSpiritual") },
    { value: "feedback", label: t("subjectFeedback") },
    { value: "bug", label: t("subjectBug") },
    { value: "feature", label: t("subjectFeature") },
    { value: "other", label: t("subjectOther") },
  ];
  const [isExpanded, setIsExpanded] = useState(false);
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState<Subject>("spiritual");
  const [message, setMessage] = useState("");
  const [bugSteps, setBugSteps] = useState("");
  const [bugBehavior, setBugBehavior] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isBug = subject === "bug";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) return;

    if (isBug) {
      if (!bugSteps.trim() || !bugBehavior.trim()) return;
    } else if (!message.trim()) {
      return;
    }

    const messageBody = isBug
      ? `${t("bugStepsLabel")}:\n${bugSteps.trim()}\n\n${t("bugExpectedLabel")}:\n${bugBehavior.trim()}`
      : message.trim();

    setIsSubmitting(true);
    setError(null);

    try {
      const request: ContactRequest = {
        email: email.trim(),
        subject,
        message: messageBody,
        user_agent:
          typeof navigator !== "undefined" ? navigator.userAgent : undefined,
      };

      await submitContactForm(request);
      setSubmitted(true);
      setEmail("");
      setMessage("");
      setBugSteps("");
      setBugBehavior("");
      setSubject("spiritual");
    } catch (err) {
      setError(t("errorSend"));
      console.error("Failed to submit contact form:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setSubmitted(false);
    setError(null);
  };

  return (
    <div className="mt-6 border-t border-gray-200 pt-4">
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-left text-gray-600 hover:text-gray-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4" />
          <span className="text-sm font-medium">{t("getInTouch")}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
      </button>

      {/* Collapsible content */}
      {isExpanded && (
        <div className="mt-4 space-y-4">
          {/* Contact email */}
          <div className="flex items-center gap-2 text-sm">
            <Mail className="w-4 h-4 text-gray-400" />
            <span className="text-gray-500">{t("emailUs")}</span>
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              className="text-primary-600 hover:text-primary-700 hover:underline"
            >
              {CONTACT_EMAIL}
            </a>
          </div>

          {/* Success message */}
          {submitted ? (
            <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
              <Check className="w-5 h-5 text-green-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-green-800">
                  {t("successTitle")}
                </p>
                <p className="text-xs text-green-600 mt-1">
                  {t("successDescription")}
                </p>
              </div>
              <button
                onClick={handleReset}
                className="text-xs text-green-600 hover:text-green-700 underline"
              >
                {t("sendAnother")}
              </button>
            </div>
          ) : (
            /* Contact form */
            <form onSubmit={handleSubmit} className="space-y-3">
              {/* Error message */}
              {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <AlertCircle className="w-4 h-4 text-red-600" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              {/* Subject */}
              <div>
                <label
                  htmlFor="contact-subject"
                  className="block text-xs text-gray-500 mb-1"
                >
                  {t("subjectLabel")}
                </label>
                <select
                  id="contact-subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value as Subject)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white"
                  disabled={isSubmitting}
                >
                  {subjectOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Message — bug reports use two structured required fields */}
              {isBug ? (
                <>
                  <div>
                    <label
                      htmlFor="contact-bug-steps"
                      className="block text-xs text-gray-500 mb-1"
                    >
                      {t("bugStepsLabel")}
                    </label>
                    <textarea
                      id="contact-bug-steps"
                      value={bugSteps}
                      onChange={(e) => setBugSteps(e.target.value)}
                      placeholder={t("bugStepsPlaceholder")}
                      rows={3}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                      disabled={isSubmitting}
                      required
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="contact-bug-behavior"
                      className="block text-xs text-gray-500 mb-1"
                    >
                      {t("bugExpectedLabel")}
                    </label>
                    <textarea
                      id="contact-bug-behavior"
                      value={bugBehavior}
                      onChange={(e) => setBugBehavior(e.target.value)}
                      placeholder={t("bugExpectedPlaceholder")}
                      rows={3}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                      disabled={isSubmitting}
                      required
                    />
                  </div>
                </>
              ) : (
                <div>
                  <label
                    htmlFor="contact-message"
                    className="block text-xs text-gray-500 mb-1"
                  >
                    {t("messageLabel")}
                  </label>
                  <textarea
                    id="contact-message"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={t("messagePlaceholder")}
                    rows={3}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                    disabled={isSubmitting}
                    required
                  />
                </div>
              )}

              {/* Email (required) — shown last */}
              <div>
                <label
                  htmlFor="contact-email"
                  className="block text-xs text-gray-500 mb-1"
                >
                  {t("emailLabel")}
                </label>
                <input
                  type="email"
                  id="contact-email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t("emailPlaceholder")}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  disabled={isSubmitting}
                  required
                />
              </div>

              {/* Privacy note */}
              <p className="text-xs text-gray-400">{t("privacyNote")}</p>

              {/* Submit button */}
              <button
                type="submit"
                disabled={
                  isSubmitting ||
                  !email.trim() ||
                  (isBug
                    ? !bugSteps.trim() || !bugBehavior.trim()
                    : !message.trim())
                }
                className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    {t("sending")}
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    {t("sendMessage")}
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
