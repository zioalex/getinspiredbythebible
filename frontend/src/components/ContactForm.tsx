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
import { submitContactForm, ContactRequest } from "@/lib/api";

const CONTACT_EMAIL = "getinspiredbythebible@ai4you.sh";

type Subject = "bug" | "feature" | "feedback" | "other";

const subjectOptions: { value: Subject; label: string }[] = [
  { value: "feedback", label: "General Feedback" },
  { value: "bug", label: "Bug Report" },
  { value: "feature", label: "Feature Request" },
  { value: "other", label: "Other" },
];

export default function ContactForm() {
  const [isExpanded, setIsExpanded] = useState(false);
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState<Subject>("feedback");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const request: ContactRequest = {
        email: email.trim() || undefined,
        subject,
        message: message.trim(),
        user_agent:
          typeof navigator !== "undefined" ? navigator.userAgent : undefined,
      };

      await submitContactForm(request);
      setSubmitted(true);
      setEmail("");
      setMessage("");
      setSubject("feedback");
    } catch (err) {
      setError(
        "Failed to send message. Please try again or email us directly.",
      );
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
          <span className="text-sm font-medium">Get in Touch</span>
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
            <span className="text-gray-500">Email us:</span>
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
                  Message sent successfully!
                </p>
                <p className="text-xs text-green-600 mt-1">
                  Thank you for reaching out. We'll review your message soon.
                </p>
              </div>
              <button
                onClick={handleReset}
                className="text-xs text-green-600 hover:text-green-700 underline"
              >
                Send another
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

              {/* Email (optional) */}
              <div>
                <label
                  htmlFor="contact-email"
                  className="block text-xs text-gray-500 mb-1"
                >
                  Your email (optional, for reply)
                </label>
                <input
                  type="email"
                  id="contact-email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  disabled={isSubmitting}
                />
              </div>

              {/* Subject */}
              <div>
                <label
                  htmlFor="contact-subject"
                  className="block text-xs text-gray-500 mb-1"
                >
                  Subject
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

              {/* Message */}
              <div>
                <label
                  htmlFor="contact-message"
                  className="block text-xs text-gray-500 mb-1"
                >
                  Message
                </label>
                <textarea
                  id="contact-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Share your thoughts, report an issue, or suggest an improvement..."
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  disabled={isSubmitting}
                  required
                />
              </div>

              {/* Privacy note */}
              <p className="text-xs text-gray-400">
                Your message will be stored to help us improve the service.
              </p>

              {/* Submit button */}
              <button
                type="submit"
                disabled={isSubmitting || !message.trim()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Send Message
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
