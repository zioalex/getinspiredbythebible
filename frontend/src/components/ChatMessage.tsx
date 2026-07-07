"use client";

import React, { useState } from "react";
import { User, BookOpen, Copy, Check } from "lucide-react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import { Message } from "@/lib/api";
import ShareMenu from "./ShareMenu";
import FeedbackControls from "./FeedbackControls";
import {
  createVersePattern,
  createVersePatternGlobal,
} from "@/lib/versePatterns";
import { isKnownBook } from "@/lib/verseExtraction";
import {
  linkifyVerses,
  parseVerseHref,
  VERSE_SCHEME,
} from "@/lib/linkifyVerses";

/** Recursively extract the plain-text content of a React node (e.g. link children). */
function getNodeText(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(getNodeText).join("");
  if (React.isValidElement(node)) {
    return getNodeText((node.props as { children?: React.ReactNode }).children);
  }
  return "";
}

interface ChatMessageProps {
  message: Message;
  messageId?: string;
  userMessage?: string;
  onVerseClick?: (book: string, chapter: number, verse: number) => void;
  onSubmitFeedback?: (
    rating: "positive" | "negative",
    comment: string,
    reason?: string,
  ) => void;
  feedbackGiven?: "positive" | "negative" | null;
  feedbackDisabled?: boolean;
}

export default function ChatMessage({
  message,
  messageId,
  userMessage,
  onVerseClick,
  onSubmitFeedback,
  feedbackGiven,
  feedbackDisabled = false,
}: ChatMessageProps) {
  const isUser = message.role === "user";

  const [copied, setCopied] = useState(false);

  const handleCopyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = message.content;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Parse verse references like "John 3:16", "Genesis 1:1", "Giovanni 3:16", "1. Mose 1:1"
  const handleTextClick = (e: React.MouseEvent) => {
    if (!onVerseClick) return;

    const target = e.target as HTMLElement;
    const text = target.textContent || "";

    // Use shared pattern auto-generated from all known localized book names.
    const versePattern = createVersePattern();
    const match = text.match(versePattern);

    if (match) {
      const book = match[1].trim();

      // Only act on real Bible books — ignore prose/times/conjunctions that
      // happen to match the "Word digit:digit" shape (e.g. "um 14:30").
      if (!isKnownBook(book)) {
        return;
      }

      const chapter = parseInt(match[2]);
      const verse = parseInt(match[3]);
      onVerseClick(book, chapter, verse);
    }
  };

  // Helper function to highlight ALL verse references and quoted text in a string
  const highlightText = (text: string, key: number): React.ReactNode => {
    // Use shared pattern auto-generated from all known localized book names.
    // Always create a fresh global instance (mutable lastIndex state).
    const verseRefPattern = createVersePatternGlobal();

    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;
    let partKey = 0;

    while ((match = verseRefPattern.exec(text)) !== null) {
      const book = match[1].trim();

      // Only mark real Bible books.  The verse regex intentionally accepts any
      // "Word digit:digit" shape, so without this check prose like
      // "Trost der Hoffnung 5:5", clock times ("um 14:30") and greedy
      // over-matches would be swallowed into clickable spans.
      //
      // Rewind on rejection: a greedy alternative can swallow the words *before*
      // a real reference (e.g. "you of Psalm 56:9" → book "you of Psalm"), so a
      // rejected match may still hide a valid reference inside it.  Reset the
      // scanner to one character past the start of the rejected match so the
      // embedded reference ("Psalm 56:9") gets its own chance to match.  The
      // local `lastIndex` (text-slice cursor) is untouched, so the skipped
      // prefix is emitted as before-text of the recovered span and no text is
      // lost.  `lastIndex` only ever advances, so this cannot loop forever.
      if (!isKnownBook(book)) {
        verseRefPattern.lastIndex = match.index + 1;
        continue;
      }

      // Add text before the verse reference
      if (match.index > lastIndex) {
        const beforeText = text.slice(lastIndex, match.index);
        parts.push(highlightQuotes(beforeText, key + partKey++));
      }

      // Add the clickable verse reference
      const fullMatch = match[0];
      parts.push(
        <span
          key={`${key}-verse-${partKey++}`}
          className="text-amber-800 font-semibold cursor-pointer hover:underline"
          onClick={handleTextClick}
        >
          {fullMatch}
        </span>,
      );

      lastIndex = match.index + fullMatch.length;
    }

    // Add remaining text after the last match
    if (lastIndex < text.length) {
      parts.push(highlightQuotes(text.slice(lastIndex), key + partKey++));
    }

    // If no matches found, just process quotes
    if (parts.length === 0) {
      return highlightQuotes(text, key);
    }

    return <React.Fragment key={key}>{parts}</React.Fragment>;
  };

  // Helper function to highlight quoted scripture text
  const highlightQuotes = (text: string, key: number): React.ReactNode => {
    const parts: React.ReactNode[] = [];
    const quotePattern = /"([^"]+)"/g;
    let lastIndex = 0;
    let match;
    let partKey = 0;

    while ((match = quotePattern.exec(text)) !== null) {
      // Add text before the quote
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      // Add the quoted text with highlighting
      parts.push(
        <span
          key={`${key}-quote-${partKey++}`}
          className="bg-amber-50 text-amber-900 px-1 py-0.5 rounded italic font-serif border-l-2 border-amber-400"
        >
          &ldquo;{match[1]}&rdquo;
        </span>,
      );
      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? (
      <React.Fragment key={key}>{parts}</React.Fragment>
    ) : (
      text
    );
  };

  return (
    <div
      data-testid={isUser ? "user-message" : "assistant-message"}
      className={`flex gap-2 sm:gap-4 message-enter ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-primary-100 flex items-center justify-center">
          <BookOpen className="w-4 h-4 sm:w-5 sm:h-5 text-primary-600" />
        </div>
      )}

      <div
        className={`max-w-[90%] sm:max-w-[80%] rounded-2xl px-4 py-3 sm:px-5 sm:py-4 ${
          isUser
            ? "bg-primary-600 text-white rounded-br-md"
            : "bg-white border border-gray-200 text-gray-800 rounded-bl-md shadow-sm"
        }`}
      >
        {isUser ? (
          <>
            <p className="whitespace-pre-wrap">{message.content}</p>
            <div className="flex justify-end mt-1.5">
              <button
                onClick={handleCopyPrompt}
                aria-label={copied ? "Copied" : "Copy message"}
                className="p-1 rounded text-white/60 hover:text-white transition-colors"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="prose prose-sm max-w-none prose-p:my-2 prose-headings:mt-4 prose-headings:mb-2">
              <ReactMarkdown
                // Preserve our in-app verse:// links; sanitize everything else
                // as usual. Without this, react-markdown's defaultUrlTransform
                // strips the unknown verse:// scheme and the links go dead.
                urlTransform={(url) =>
                  url.startsWith(VERSE_SCHEME) ? url : defaultUrlTransform(url)
                }
                components={{
                  // Custom paragraph renderer to highlight verse references
                  p: ({ children }) => {
                    const processedChildren = React.Children.map(
                      children,
                      (child, idx) => {
                        if (typeof child === "string") {
                          return highlightText(child, idx);
                        }
                        return child;
                      },
                    );
                    return (
                      <p className="my-2 leading-relaxed">
                        {processedChildren}
                      </p>
                    );
                  },
                  // List items need the same string processing as paragraphs —
                  // a tight markdown list puts text directly in <li> (not in a
                  // <p>), so without this, quotes in bullets go unstyled. Verse
                  // references are already pre-linked by linkifyVerses(), so
                  // they arrive as <a> children and pass straight through.
                  li: ({ children }) => {
                    const processedChildren = React.Children.map(
                      children,
                      (child, idx) => {
                        if (typeof child === "string") {
                          return highlightText(child, idx);
                        }
                        return child;
                      },
                    );
                    return <li>{processedChildren}</li>;
                  },
                  // Style bold text (often verse references) - make them clickable
                  strong: ({ children }) => (
                    <strong
                      className="text-amber-800 font-bold cursor-pointer hover:underline transition-colors"
                      onClick={handleTextClick}
                    >
                      {children}
                    </strong>
                  ),
                  // Style blockquotes as scripture
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-amber-500 pl-4 pr-3 py-3 my-3 bg-amber-50 rounded-r-lg italic font-serif text-amber-900">
                      {children}
                    </blockquote>
                  ),
                  // Style inline code as verse references - make them clickable
                  code: ({ children }) => (
                    <code
                      className="px-2 py-1 bg-amber-100 text-amber-900 rounded font-semibold not-italic cursor-pointer hover:bg-amber-200 transition-colors"
                      onClick={handleTextClick}
                    >
                      {children}
                    </code>
                  ),
                  // Verse references the model emits as markdown links
                  // (e.g. "[Hiob 7:3](url)") should behave like every other
                  // inline verse marking — amber, clickable, opening the
                  // in-app verse view — not a default blue external link.
                  a: ({ href, children }) => {
                    // In-app verse:// links injected by linkifyVerses(): parse
                    // the reference straight from the href so it works anywhere
                    // (paragraphs, list items, headings, …).
                    const verse = parseVerseHref(href);
                    if (verse) {
                      return (
                        <span
                          className="text-amber-800 font-semibold cursor-pointer hover:underline"
                          onClick={() =>
                            onVerseClick?.(
                              verse.book,
                              verse.chapter,
                              verse.verse,
                            )
                          }
                        >
                          {children}
                        </span>
                      );
                    }
                    const linkText = getNodeText(children);
                    const match = linkText.match(createVersePattern());
                    if (match && isKnownBook(match[1].trim())) {
                      return (
                        <span
                          className="text-amber-800 font-semibold cursor-pointer hover:underline"
                          onClick={handleTextClick}
                        >
                          {linkText}
                        </span>
                      );
                    }
                    // Non-verse links render as normal styled links.
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-600 hover:underline"
                      >
                        {children}
                      </a>
                    );
                  },
                  // Ensure lists look good
                  ul: ({ children }) => (
                    <ul className="list-disc pl-5 space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal pl-5 space-y-1">{children}</ol>
                  ),
                }}
              >
                {linkifyVerses(message.content)}
              </ReactMarkdown>
            </div>

            {/* Feedback and share controls for assistant messages */}
            {messageId && onSubmitFeedback && (
              <div className="mt-3 pt-3 border-t border-gray-100">
                <FeedbackControls
                  given={feedbackGiven ?? null}
                  disabled={feedbackDisabled}
                  onSubmit={onSubmitFeedback}
                  trailing={
                    <ShareMenu
                      question={userMessage || ""}
                      answer={message.content}
                    />
                  }
                />
              </div>
            )}
          </>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-primary-600 flex items-center justify-center">
          <User className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
        </div>
      )}
    </div>
  );
}
