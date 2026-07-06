"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import {
  Send,
  Book,
  Loader2,
  RefreshCw,
  Filter,
  BookOpen,
  X,
  ChevronDown,
  Square,
  FlaskConical,
  ArrowRight,
} from "lucide-react";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import ChatMessage from "@/components/ChatMessage";
import VerseCard from "@/components/VerseCard";
import ChapterModal from "@/components/ChapterModal";
import ChurchFinderBanner from "@/components/ChurchFinderBanner";
import ChurchFinderInlinePrompt from "@/components/ChurchFinderInlinePrompt";
import ChurchFinderModal from "@/components/ChurchFinderModal";
import ContactForm from "@/components/ContactForm";
import LanguageSwitcher, { localeLabels } from "@/components/LanguageSwitcher";
import LanguageSwitchSuggestion from "@/components/LanguageSwitchSuggestion";
import {
  streamMessage,
  Message,
  Verse,
  getChapter,
  getTranslations,
  getBookNames,
  TranslationInfo,
  submitFeedback,
  FeedbackRequest,
  generateSessionId,
  getOrCreateSessionId,
  resetSessionId,
  ColdStartError,
  ContentBlockedError,
  SessionLimitError,
  StreamTimeoutError,
  MessageTooLongError,
  VerificationError,
  MAX_MESSAGE_LENGTH,
  checkBackendReady,
  warmupBackend,
  StreamChunk,
  StreamMetadata,
} from "@/lib/api";

import {
  extractVerseReferences,
  isVerseReferenced,
  updateBookNames,
} from "@/lib/verseExtraction";
import { updateMultiWordNames } from "@/lib/versePatterns";
import { mergeVerses } from "@/lib/mergeVerses";
import { useTurnstile } from "@/lib/turnstile";
import { useRouter, usePathname } from "@/i18n/navigation";

// Extended message type with message_id for feedback tracking
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  messageId?: string; // Only present for assistant messages
  userMessage?: string; // User message that prompted this response
  versesCited?: string[];
  model?: string;
}

export default function ChatIsland({
  heroContent,
}: {
  heroContent?: React.ReactNode;
}) {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const tHeader = useTranslations("Header");
  const tWelcome = useTranslations("Welcome");
  const tChat = useTranslations("Chat");
  const tVerses = useTranslations("Verses");
  const tFeedback = useTranslations("Feedback");
  const {
    isReady: turnstileReady,
    isEnabled: turnstileEnabled,
    configLoaded: turnstileConfigLoaded,
  } = useTurnstile();
  // Block submissions until /config has resolved: until then we don't yet
  // know whether Turnstile is enabled, and a fast click could fire a POST
  // without an X-Turnstile-Token header and get bounced as 403.
  const turnstileBlocked =
    !turnstileConfigLoaded || (turnstileEnabled && !turnstileReady);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isWarmingUp, setIsWarmingUp] = useState(false);
  // null = checking, true = ready, false = warming up
  const [backendReady, setBackendReady] = useState<boolean | null>(null);
  const [relevantVerses, setRelevantVerses] = useState<Verse[]>([]);
  const [showOnlyReferenced, setShowOnlyReferenced] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const versesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Smart auto-scroll state
  const [isUserNearBottom, setIsUserNearBottom] = useState(true);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const SCROLL_THRESHOLD = 100; // px from bottom to consider "near bottom"

  // Feedback state
  const [feedbackGiven, setFeedbackGiven] = useState<
    Record<string, "positive" | "negative">
  >({});
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalChapter, setModalChapter] = useState<{
    book: string;
    localized_book?: string;
    chapter: number;
    verses: Verse[];
    highlightVerse?: number;
    translation?: string;
    translationName?: string;
  } | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(false);

  // Track detected translation from chat
  const [detectedTranslation, setDetectedTranslation] = useState<string | null>(
    null,
  );

  // Language-mismatch suggestion (backend detected a different language than
  // the active UI locale). null = no suggestion.
  const [languageSuggestion, setLanguageSuggestion] = useState<string | null>(
    null,
  );
  const [languageSuggestionDismissed, setLanguageSuggestionDismissed] =
    useState(false);

  // Church finder state
  const [interactionCount, setInteractionCount] = useState(0);
  const [churchFinderDismissed, setChurchFinderDismissed] = useState(false);
  const [churchFinderModalOpen, setChurchFinderModalOpen] = useState(false);
  const [inlinePromptShown, setInlinePromptShown] = useState(false);
  const [inlinePromptDismissed, setInlinePromptDismissed] = useState(false);
  // Track at which message index the inline prompt should appear (randomly decided)
  const [inlinePromptIndex, setInlinePromptIndex] = useState<number | null>(
    null,
  );

  // Mobile verses panel
  const [mobileVersesOpen, setMobileVersesOpen] = useState(false);

  // Session limit state
  const [showSessionLimitButton, setShowSessionLimitButton] = useState(false);

  // Persistent session ID for DAU/MAU tracking (survives page refreshes)
  const [sessionId, setSessionId] = useState<string>(() =>
    getOrCreateSessionId(),
  );
  // Conversation ID resets on "New Chat" for per-conversation tracking
  const [conversationId, setConversationId] = useState<string>(() =>
    generateSessionId(),
  );

  // Show church finder banner after 3+ messages and not dismissed
  const showChurchFinderBanner =
    interactionCount >= 3 && !churchFinderDismissed && messages.length > 0;

  // Translation preference
  const [translations, setTranslations] = useState<TranslationInfo[]>([]);
  const [selectedTranslation, setSelectedTranslation] = useState<string>("");

  // Active translation code (manual selection wins over auto-detected)
  const activeTranslationCode =
    selectedTranslation ||
    (translations.some((t) => t.code === detectedTranslation)
      ? (detectedTranslation as string)
      : "");

  const activeTranslation = useMemo(
    () => translations.find((t) => t.code === activeTranslationCode),
    [translations, activeTranslationCode],
  );

  // Load translations and saved preference on mount
  useEffect(() => {
    const loadTranslations = async () => {
      try {
        const availableTranslations = await getTranslations();
        setTranslations(availableTranslations);

        // Load saved preference from localStorage
        const saved = localStorage.getItem("preferredTranslation");
        if (saved && availableTranslations.some((t) => t.code === saved)) {
          setSelectedTranslation(saved);
        }
      } catch (error) {
        console.error("Failed to load translations:", error);
      }
    };

    const loadBookNames = async () => {
      try {
        const data = await getBookNames();
        updateBookNames(data.localized_to_english);
        updateMultiWordNames(data.multi_word_names);
      } catch (error) {
        // Silently fail — bundled fallback data is sufficient
        console.error("Failed to load book names:", error);
      }
    };

    loadTranslations();
    loadBookNames();
  }, []);

  // Pre-warm backend on mount so cold-start scaling begins immediately
  useEffect(() => {
    warmupBackend(
      () => setBackendReady(true),
      () => setBackendReady(false),
    );
  }, []);

  // Rehydrate a conversation preserved across a language switch. The switch
  // triggers router.replace which remounts this page, so we stash messages in
  // sessionStorage before navigating and restore them here exactly once.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("preservedConversation");
      if (!raw) return;
      sessionStorage.removeItem("preservedConversation");
      const saved = JSON.parse(raw) as {
        messages?: ChatMessage[];
        conversationId?: string;
      };
      if (saved.messages && saved.messages.length > 0) {
        setMessages(saved.messages);
      }
      if (saved.conversationId) {
        setConversationId(saved.conversationId);
      }
    } catch {
      // Corrupt/blocked storage: ignore and start fresh.
    }
  }, []);

  // Save preference to localStorage when changed
  const handleTranslationChange = (code: string) => {
    setSelectedTranslation(code);
    if (code) {
      localStorage.setItem("preferredTranslation", code);
    } else {
      localStorage.removeItem("preferredTranslation");
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleScrollToBottomClick = () => {
    setIsUserNearBottom(true);
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollVersesToBottom = () => {
    versesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Scroll detection - track if user is near bottom
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      setIsUserNearBottom(distanceFromBottom < SCROLL_THRESHOLD);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (isUserNearBottom) {
      scrollToBottom();
    }
  }, [messages, isUserNearBottom]);

  useEffect(() => {
    scrollVersesToBottom();
  }, [relevantVerses]);

  // Extract verse references mentioned in chat messages
  // Use the pre-computed versesCited field if available (set after streaming completes),
  // otherwise fall back to extracting from content for backwards compatibility
  const referencedVerses = useMemo(() => {
    const allRefs = messages
      .filter((m) => m.role === "assistant")
      .flatMap((m) => {
        // Prefer pre-computed versesCited (more reliable after streaming)
        if (m.versesCited && m.versesCited.length > 0) {
          return m.versesCited;
        }
        // Fallback: extract from content (for older messages or non-streaming)
        return Array.from(extractVerseReferences(m.content));
      });

    return new Set(allRefs);
  }, [messages]);

  // Filter verses based on the toggle
  const displayedVerses = useMemo(() => {
    if (!showOnlyReferenced) {
      return relevantVerses;
    }

    return relevantVerses.filter((verse) =>
      isVerseReferenced(verse, referencedVerses),
    );
  }, [relevantVerses, referencedVerses, showOnlyReferenced]);

  const handleVerseClick = async (
    book: string,
    chapter: number,
    verse: number,
    translation?: string,
  ) => {
    // Priority: provided > user preference > detected > auto
    const useTranslation =
      translation || selectedTranslation || detectedTranslation || undefined;

    setModalError(false);
    setModalOpen(true);
    setModalLoading(true);
    setModalChapter({ book, chapter, verses: [], highlightVerse: verse });

    try {
      const chapterData = await getChapter(
        book,
        chapter,
        useTranslation,
        locale,
      );
      setModalChapter({
        book: chapterData.book,
        localized_book: chapterData.localized_book,
        chapter: chapterData.chapter,
        verses: chapterData.verses,
        highlightVerse: verse,
        translation: chapterData.translation,
        translationName: chapterData.translation_name,
      });
    } catch (error) {
      console.error("Failed to fetch chapter:", error);
      setModalError(true);
    } finally {
      setModalLoading(false);
    }
  };

  const handleCloseModal = () => {
    setModalOpen(false);
    setModalChapter(null);
    setModalError(false);
  };

  const submitMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessageContent = content.trim();
    const userMessage: ChatMessage = {
      role: "user",
      content: userMessageContent,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsUserNearBottom(true); // Reset auto-scroll when user sends a new message
    setInput("");
    setIsLoading(true);
    setIsWarmingUp(false);
    setBackendReady(true); // Streaming doesn't have cold start issues with min_replicas=1

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Hoisted out of the try so the catch block can replace the placeholder
    // assistant bubble in place (e.g. on a stall timeout) instead of appending
    // a second bubble next to an empty one.
    let streamedContent = "";
    let assistantMessageIndex = -1;

    try {
      // Convert messages to the API format (without extra fields)
      const apiMessages: Message[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      // Streaming metadata and content
      let metadata: StreamMetadata | null = null;
      let receivedCompletion = false;

      // Create a placeholder assistant message that will be updated as content streams
      const placeholderMessage: ChatMessage = {
        role: "assistant",
        content: "",
        userMessage: userMessageContent,
      };

      // Add placeholder to messages immediately
      setMessages((prev) => {
        assistantMessageIndex = prev.length; // Will be the index of the new message
        return [...prev, placeholderMessage];
      });

      // Send the active UI locale so the backend replies in it. If the user
      // types in a different language the backend returns a language_suggestion
      // and we surface a dismissible switch banner.
      for await (const chunk of streamMessage(userMessageContent, apiMessages, {
        preferredTranslation: selectedTranslation || undefined,
        sessionId,
        language: locale,
        signal: controller.signal,
      })) {
        if (controller.signal.aborted) break;
        if (chunk.type === "error") {
          throw new Error(chunk.error || "Stream error");
        }

        if (chunk.type === "metadata") {
          // Received metadata - update state with verses and message_id
          metadata = {
            message_id: chunk.message_id!,
            scripture_context: chunk.scripture_context,
            provider: chunk.provider!,
            model: chunk.model!,
            detected_translation: chunk.detected_translation,
            translation_info: chunk.translation_info,
            language_suggestion: chunk.language_suggestion ?? null,
          };

          // Surface a language-switch suggestion when the backend detected a
          // different (and supported) language than the active UI locale.
          if (
            chunk.language_suggestion &&
            chunk.language_suggestion !== locale &&
            localeLabels[chunk.language_suggestion]
          ) {
            setLanguageSuggestion(chunk.language_suggestion);
            setLanguageSuggestionDismissed(false);
          }

          // Update detected translation
          if (chunk.detected_translation) {
            setDetectedTranslation(chunk.detected_translation);
          }

          // Append relevant verses immediately (verses appear before text starts)
          if (chunk.scripture_context?.verses) {
            setRelevantVerses((prev) => [
              ...prev,
              ...(chunk.scripture_context?.verses || []),
            ]);
          }

          // Update the placeholder message with metadata (immutable update)
          setMessages((prev) => {
            const updated = [...prev];
            const msg = updated[assistantMessageIndex];
            if (msg && msg.role === "assistant") {
              updated[assistantMessageIndex] = {
                ...msg,
                messageId: metadata!.message_id,
                model: metadata!.model,
              };
            }
            return updated;
          });
        } else if (chunk.type === "content") {
          // Received content chunk - append to streaming message
          streamedContent += chunk.content || "";

          // Update the message content in real-time using immutable update
          // so React detects the change and referencedVerses useMemo re-runs
          setMessages((prev) => {
            const updated = [...prev];
            const msg = updated[assistantMessageIndex];
            if (msg && msg.role === "assistant") {
              updated[assistantMessageIndex] = {
                ...msg,
                content: streamedContent,
              };
            }
            return updated;
          });
        } else if (chunk.type === "completion") {
          // Server-provided verse citations (dual-source: LLM structured + regex)
          receivedCompletion = true;
          // If grounding rewrote a fabricated/mismatched verse quote, swap the
          // streamed text for the authoritative corrected body.
          if (chunk.corrected_message) {
            streamedContent = chunk.corrected_message;
            setMessages((prev) => {
              const updated = [...prev];
              const msg = updated[assistantMessageIndex];
              if (msg && msg.role === "assistant") {
                updated[assistantMessageIndex] = {
                  ...msg,
                  content: streamedContent,
                };
              }
              return updated;
            });
          }
          if (chunk.verses_cited) {
            const serverCited = (chunk.verses_cited as string[]).map(
              (v: string) => v.toLowerCase(),
            );
            setMessages((prev) => {
              const updated = [...prev];
              const msg = updated[assistantMessageIndex];
              if (msg && msg.role === "assistant") {
                updated[assistantMessageIndex] = {
                  ...msg,
                  versesCited: serverCited,
                };
              }
              return updated;
            });
          }
          // Merge the backend-resolved cited verses into the pool so the
          // "Cited" filter surfaces them even when they fell outside the
          // semantic search (common on follow-up questions).
          if (chunk.resolved_verses?.length) {
            setRelevantVerses((prev) =>
              mergeVerses(prev, chunk.resolved_verses),
            );
          }
        }
      }

      // Resilience guard: the stream completed without error but no content
      // arrived (empty LLM output, or chunks lost upstream). Don't leave the
      // user staring at a blank assistant bubble — replace it with a clear,
      // warm message inviting them to try again. A user-initiated stop is
      // excluded: that keeps whatever (possibly empty) partial text silently.
      if (!controller.signal.aborted && streamedContent.trim() === "") {
        setMessages((prev) => {
          const updated = [...prev];
          const msg = updated[assistantMessageIndex];
          if (msg && msg.role === "assistant") {
            updated[assistantMessageIndex] = {
              ...msg,
              content: tChat("errorConnection"),
            };
          }
          return updated;
        });
        abortControllerRef.current = null;
        setIsLoading(false);
        return;
      }

      // Fallback: if no completion event received, extract client-side
      if (!receivedCompletion) {
        const citedRefs = Array.from(extractVerseReferences(streamedContent));
        setMessages((prev) => {
          const updated = [...prev];
          const msg = updated[assistantMessageIndex];
          if (msg && msg.role === "assistant") {
            updated[assistantMessageIndex] = { ...msg, versesCited: citedRefs };
          }
          return updated;
        });
      }

      // Stream complete - increment interaction count for church finder
      setInteractionCount((prev) => {
        const newCount = prev + 1;
        // After 3-5 exchanges, randomly decide to show inline prompt
        if (
          !inlinePromptShown &&
          !inlinePromptDismissed &&
          newCount >= 3 &&
          inlinePromptIndex === null
        ) {
          const chance = Math.min(0.4 + (newCount - 3) * 0.2, 0.8);
          if (Math.random() < chance) {
            setInlinePromptIndex(messages.length + 1);
            setInlinePromptShown(true);
          }
        }
        return newCount;
      });

      abortControllerRef.current = null;
      setIsLoading(false);
    } catch (error) {
      abortControllerRef.current = null;
      // User-initiated cancellation: keep partial content, don't show an error.
      if (
        controller.signal.aborted ||
        (error instanceof DOMException && error.name === "AbortError")
      ) {
        setIsWarmingUp(false);
        setIsLoading(false);
        return;
      }
      console.error("Failed to send message:", error);
      setIsWarmingUp(false);

      // Surface an error to the user. If an empty placeholder assistant bubble
      // is already on screen (the common case — the error fires before or
      // mid-stream), replace it in place so the user never sees a blank bubble
      // sitting next to an error bubble; otherwise append a fresh message.
      const showError = (content: string) => {
        setMessages((prev) => {
          const existing = prev[assistantMessageIndex];
          if (
            existing &&
            existing.role === "assistant" &&
            existing.content === ""
          ) {
            const updated = [...prev];
            updated[assistantMessageIndex] = { ...existing, content };
            return updated;
          }
          return [...prev, { role: "assistant", content }];
        });
      };

      // Handle session limit error specifically
      if (error instanceof SessionLimitError) {
        showError(tChat("sessionLimitMessage"));
        setShowSessionLimitButton(true);
        setIsLoading(false);
        return;
      }

      // Safety system blocked the message — show a warm notification
      // inviting the user to rephrase and to get in touch if something feels wrong.
      if (error instanceof ContentBlockedError) {
        showError(tChat("contentBlockedMessage"));
        setIsLoading(false);
        return;
      }

      // Stream stalled (no data within the inactivity window) — tell the user
      // it was interrupted rather than leaving them on a silent empty bubble.
      if (error instanceof StreamTimeoutError) {
        showError(tChat("errorTimeout"));
        setIsLoading(false);
        return;
      }

      // Backend rejected an over-long message (422) — tell the user to shorten
      // it instead of showing a misleading connection error.
      if (error instanceof MessageTooLongError) {
        showError(tChat("messageTooLong", { max: MAX_MESSAGE_LENGTH }));
        setIsLoading(false);
        return;
      }

      // Turnstile couldn't verify the request (403) even after a retry — tell
      // the user it's a verification hiccup that a quick retry usually fixes,
      // rather than a generic connection failure.
      if (error instanceof VerificationError) {
        showError(tChat("errorVerification"));
        setIsLoading(false);
        return;
      }

      showError(tChat("errorConnection"));
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitMessage(input);
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  // Auto-resize the chat textarea up to a cap so multi-line input grows
  // naturally as the user types and shrinks back when content is removed.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = 160; // ~8 lines
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  }, [input]);

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter inserts a newline. Don't interfere while the IME
    // is composing (e.g. CJK input) — that Enter is for the composer to commit.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (!isLoading) {
        void submitMessage(input);
      }
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setRelevantVerses([]);
    setDetectedTranslation(null);
    setLanguageSuggestion(null);
    setLanguageSuggestionDismissed(false);
    setInteractionCount(0);
    setChurchFinderDismissed(false);
    setInlinePromptShown(false);
    setInlinePromptDismissed(false);
    setInlinePromptIndex(null);
    setFeedbackGiven({});
    setFeedbackError(null);
    setMobileVersesOpen(false);
    setShowSessionLimitButton(false);
    setConversationId(generateSessionId()); // New conversation, same persistent session
  };

  const handleNewSession = () => {
    const newSessionId = resetSessionId(); // generate + persist new ID
    setSessionId(newSessionId); // update state so next API call uses it
    setMessages([]);
    setRelevantVerses([]);
    setDetectedTranslation(null);
    setLanguageSuggestion(null);
    setLanguageSuggestionDismissed(false);
    setInteractionCount(0);
    setChurchFinderDismissed(false);
    setInlinePromptShown(false);
    setInlinePromptDismissed(false);
    setInlinePromptIndex(null);
    setFeedbackGiven({});
    setFeedbackError(null);
    setMobileVersesOpen(false);
    setShowSessionLimitButton(false);
    setConversationId(generateSessionId()); // Reset conversation and session
  };

  const handleLanguageSwitch = () => {
    if (!languageSuggestion) return;
    try {
      sessionStorage.setItem(
        "preservedConversation",
        JSON.stringify({ messages, conversationId }),
      );
    } catch {
      // Storage unavailable: navigate anyway, conversation won't persist.
    }
    router.replace(pathname, { locale: languageSuggestion });
  };

  const handleLanguageSuggestionDismiss = () => {
    setLanguageSuggestionDismissed(true);
  };

  // Handle feedback submission. Called once per rating by FeedbackControls,
  // after the inline rethink window elapses (or the user sends a comment).
  const handleFeedbackSubmit = async (
    messageId: string,
    rating: "positive" | "negative",
    comment: string,
    reason?: string,
  ) => {
    const message = messages.find((m) => m.messageId === messageId);
    if (!message || message.role !== "assistant") return;

    try {
      const feedbackRequest: FeedbackRequest = {
        message_id: messageId,
        rating,
        comment: comment || undefined,
        user_message: message.userMessage || "",
        assistant_response: message.content,
        verses_cited: message.versesCited,
        model_used: message.model,
        reason,
      };

      await submitFeedback(feedbackRequest);

      // Mark feedback as given for this message
      setFeedbackGiven((prev) => ({ ...prev, [messageId]: rating }));
    } catch (error) {
      console.error("Failed to submit feedback:", error);
      // Show error but still mark as given to prevent duplicate attempts
      setFeedbackError(tFeedback("toastError"));
      setFeedbackGiven((prev) => ({ ...prev, [messageId]: rating }));
      // Auto-dismiss error after 5 seconds
      setTimeout(() => setFeedbackError(null), 5000);
    }
  };

  // Handle inline church finder prompt actions
  const handleInlinePromptClick = () => {
    setChurchFinderModalOpen(true);
    setInlinePromptDismissed(true);
  };

  const handleInlinePromptDismiss = () => {
    setInlinePromptDismissed(true);
  };

  // Determine if inline prompt should be visible
  const showInlinePrompt =
    inlinePromptIndex !== null &&
    !inlinePromptDismissed &&
    messages.length >= inlinePromptIndex;

  const [suggestedPrompts, setSuggestedPrompts] = useState<string[]>([]);
  useEffect(() => {
    const allPrompts = Array.from({ length: 100 }, (_, i) =>
      tWelcome(`prompt${i + 1}`),
    );
    const shuffled = [...allPrompts];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    setSuggestedPrompts(shuffled.slice(0, 4));
  }, [tWelcome]);

  return (
    <main className="flex h-dvh">
      {/* Main Chat Area */}
      <div className="flex-1 min-w-0 w-full flex flex-col max-w-4xl mx-auto overflow-x-hidden">
        {/* Header */}
        <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-sm border-b border-primary-100 px-3 py-3 sm:px-6 sm:py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Book className="w-8 h-8 text-primary-600" />
              <div>
                <h1 className="text-xl font-semibold text-gray-800">
                  {tHeader("title")}
                </h1>
                <p className="text-sm text-gray-500 hidden sm:block">
                  {tHeader("subtitle")}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Android beta tester recruitment — prominent call to participate */}
              <Link
                href="/tester"
                title={tHeader("testerCta")}
                className="relative flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded-full shadow-sm hover:shadow transition-all"
              >
                {/* Pinging dot draws the eye to the invitation */}
                <span className="absolute -top-1 -right-1 flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-75" />
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-teal-500" />
                </span>
                <FlaskConical className="w-4 h-4 flex-shrink-0" />
                <span className="hidden sm:inline">{tHeader("testerCta")}</span>
              </Link>

              {/* Language Switcher */}
              <LanguageSwitcher />

              {/* Bible Version Chip — prominent amber badge; click opens native translation dropdown */}
              <div
                className={`relative inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 focus-within:ring-2 focus-within:ring-amber-400 ${
                  translations.length === 0
                    ? "border-gray-200 bg-gray-100 cursor-not-allowed"
                    : "border-amber-300 bg-amber-50 hover:bg-amber-100 cursor-pointer"
                }`}
                title={tHeader("bibleVersion")}
              >
                <Book
                  className={`w-3.5 h-3.5 flex-shrink-0 ${translations.length === 0 ? "text-gray-400" : "text-amber-700"}`}
                />
                <span
                  className={`text-xs font-medium max-w-[5rem] sm:max-w-[8rem] truncate ${translations.length === 0 ? "text-gray-400" : "text-amber-800"}`}
                >
                  {activeTranslation
                    ? activeTranslation.short_name
                    : tHeader("bibleVersion")}
                </span>
                <ChevronDown
                  className={`w-3 h-3 flex-shrink-0 ${translations.length === 0 ? "text-gray-400" : "text-amber-600"}`}
                />
                {/* Native select is invisible but handles click-to-open and keyboard navigation */}
                <select
                  value={activeTranslationCode}
                  onChange={(e) => handleTranslationChange(e.target.value)}
                  disabled={translations.length === 0}
                  aria-label={tHeader("bibleVersion")}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                >
                  <option value="">{tHeader("bibleVersion")}</option>
                  {translations.map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.language} - {t.short_name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleNewChat}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                <span className="hidden md:inline">{tHeader("newChat")}</span>
              </button>
            </div>
          </div>
        </header>

        {/* Backend warming-up notification */}
        {backendReady === false && (
          <div className="mx-3 sm:mx-6 mt-3 bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-lg flex items-center gap-3">
            <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
            <span className="text-sm">{tChat("backendWarmingUp")}</span>
          </div>
        )}

        {/* Messages Area */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto px-3 py-4 sm:px-6 sm:py-6"
        >
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Book className="w-16 h-16 text-primary-300 mb-4" />
              {heroContent ?? (
                <>
                  <h2 className="text-2xl font-serif text-gray-700 mb-2">
                    {tWelcome("heading")}
                  </h2>
                  <p className="text-gray-500 max-w-md mb-8">
                    {tWelcome("description")}
                  </p>
                </>
              )}

              {/* Security check loading indicator */}
              {turnstileBlocked && (
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Preparing secure connection...</span>
                </div>
              )}

              {/* Suggested Prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                {suggestedPrompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => submitMessage(prompt)}
                    disabled={turnstileBlocked}
                    className="text-left px-4 py-3 bg-white border border-primary-200 rounded-lg text-sm text-gray-700 hover:border-primary-400 hover:bg-primary-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              {/* Beta tester invitation — call to participate */}
              <Link
                href="/tester"
                className="group mt-8 flex items-center gap-3 sm:gap-4 max-w-lg mx-auto px-4 py-3 sm:px-5 sm:py-4 bg-teal-50 border border-teal-200 rounded-xl hover:border-teal-400 hover:bg-teal-100/70 transition-colors text-left"
              >
                <span className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full bg-teal-600 text-white">
                  <FlaskConical className="w-5 h-5" />
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block font-semibold text-teal-900">
                    {tWelcome("testerTitle")}
                  </span>
                  <span className="block text-sm text-teal-700">
                    {tWelcome("testerBody")}
                  </span>
                </span>
                <ArrowRight className="w-5 h-5 text-teal-600 flex-shrink-0 group-hover:translate-x-0.5 transition-transform" />
              </Link>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message, index) => (
                <div key={index}>
                  <ChatMessage
                    message={{ role: message.role, content: message.content }}
                    messageId={message.messageId}
                    userMessage={message.userMessage}
                    onVerseClick={handleVerseClick}
                    onSubmitFeedback={
                      message.messageId
                        ? (rating, comment, reason) =>
                            handleFeedbackSubmit(
                              message.messageId!,
                              rating,
                              comment,
                              reason,
                            )
                        : undefined
                    }
                    feedbackGiven={
                      message.messageId
                        ? feedbackGiven[message.messageId] || null
                        : null
                    }
                  />
                  {/* Show inline church finder prompt after the designated message */}
                  {showInlinePrompt && index + 1 === inlinePromptIndex && (
                    <ChurchFinderInlinePrompt
                      onFindChurch={handleInlinePromptClick}
                      onDismiss={handleInlinePromptDismiss}
                    />
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex items-center gap-3 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>
                    {isWarmingUp
                      ? tChat("loadingWarmup")
                      : tChat("loadingSearch")}
                  </span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-3 py-3 sm:px-6 sm:py-4">
          {/* Session Limit Button */}
          {showSessionLimitButton && (
            <div className="mb-4 flex justify-center">
              <button
                onClick={handleNewSession}
                className="px-6 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-colors flex items-center gap-2"
              >
                <RefreshCw className="w-5 h-5" />
                {tChat("startNewSession")}
              </button>
            </div>
          )}

          {/* Language-mismatch suggestion */}
          {languageSuggestion && !languageSuggestionDismissed && (
            <LanguageSwitchSuggestion
              suggestedLocale={languageSuggestion}
              onSwitch={handleLanguageSwitch}
              onDismiss={handleLanguageSuggestionDismiss}
            />
          )}

          <form onSubmit={handleSubmit} className="flex gap-3 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder={tChat("inputPlaceholder")}
              rows={1}
              maxLength={MAX_MESSAGE_LENGTH}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none overflow-y-auto leading-6"
              disabled={showSessionLimitButton}
            />
            {isLoading ? (
              <button
                type="button"
                onClick={handleStop}
                aria-label={tChat("stopGenerating")}
                title={tChat("stopGenerating")}
                className="px-6 py-3 bg-gray-700 text-white rounded-xl hover:bg-gray-800 transition-colors flex items-center gap-2"
              >
                <Square className="w-5 h-5" fill="currentColor" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={
                  !input.trim() || showSessionLimitButton || turnstileBlocked
                }
                className="px-6 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </form>
          {/* Character counter — surfaces only as the user nears the limit so
              they understand why a long message can't grow further. */}
          {input.length >= MAX_MESSAGE_LENGTH * 0.8 && (
            <p
              className={`text-xs mt-1 text-right ${
                input.length >= MAX_MESSAGE_LENGTH
                  ? "text-red-500"
                  : "text-gray-400"
              }`}
              aria-live="polite"
            >
              {input.length}/{MAX_MESSAGE_LENGTH}
            </p>
          )}
          <p className="text-xs text-gray-400 mt-2 text-center">
            {tChat("disclaimer")}
          </p>

          {/* Church Finder Banner */}
          {showChurchFinderBanner && (
            <ChurchFinderBanner
              onFindChurch={() => setChurchFinderModalOpen(true)}
              onDismiss={() => setChurchFinderDismissed(true)}
            />
          )}

          {/* Contact Form */}
          <ContactForm />
        </div>
      </div>

      {/* Sidebar - Relevant Verses */}
      {relevantVerses.length > 0 && (
        <aside className="hidden lg:flex lg:flex-col w-80 border-l border-gray-200 bg-white/50">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-700">
                {tVerses("scriptureReferences")}
              </h3>
              <span className="text-xs text-gray-400">
                {tVerses("verseCount", { count: displayedVerses.length })}
              </span>
            </div>
            {/* Filter Toggle */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowOnlyReferenced(true)}
                className={`flex-1 text-xs px-2 py-1.5 rounded-l-md border transition-colors ${
                  showOnlyReferenced
                    ? "bg-primary-100 border-primary-300 text-primary-700 font-medium"
                    : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"
                }`}
              >
                {tVerses("referenced")}
              </button>
              <button
                onClick={() => setShowOnlyReferenced(false)}
                className={`flex-1 text-xs px-2 py-1.5 rounded-r-md border-t border-r border-b transition-colors ${
                  !showOnlyReferenced
                    ? "bg-primary-100 border-primary-300 text-primary-700 font-medium"
                    : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"
                }`}
              >
                {tVerses("allRelated", { count: relevantVerses.length })}
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {displayedVerses.length > 0 ? (
              <div className="space-y-3">
                {displayedVerses.map((verse, index) => (
                  <VerseCard
                    key={index}
                    verse={verse}
                    onClick={() =>
                      handleVerseClick(
                        verse.book,
                        verse.chapter,
                        verse.verse,
                        verse.translation,
                      )
                    }
                  />
                ))}
                <div ref={versesEndRef} />
              </div>
            ) : (
              <div className="text-center text-gray-500 text-sm py-8">
                <Filter className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p>{tVerses("noVersesReferenced")}</p>
                <p className="text-xs mt-1">
                  {tVerses("noVersesReferencedHint")}
                </p>
                {relevantVerses.length > 0 && (
                  <button
                    className="mt-3 text-xs text-amber-600 hover:text-amber-700 underline"
                    onClick={() => setShowOnlyReferenced(false)}
                  >
                    {tVerses("allRelated", { count: relevantVerses.length })}
                  </button>
                )}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* Scroll to bottom button - appears when user scrolls up during streaming */}
      {!isUserNearBottom && messages.length > 0 && (
        <button
          onClick={handleScrollToBottomClick}
          className="fixed bottom-24 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-4 py-2 bg-gray-800/90 text-white rounded-full shadow-lg hover:bg-gray-900 transition-colors backdrop-blur-sm"
          aria-label={tChat("scrollToBottom")}
        >
          <ChevronDown className="w-4 h-4" />
          <span className="text-sm font-medium">{tChat("scrollToBottom")}</span>
        </button>
      )}

      {/* Mobile FAB for verse references */}
      {relevantVerses.length > 0 && (
        <button
          onClick={() => setMobileVersesOpen(true)}
          className="lg:hidden fixed bottom-28 right-4 z-40 flex items-center gap-2 px-4 py-3 bg-primary-600 text-white rounded-full shadow-lg hover:bg-primary-700 transition-colors"
          aria-label={tVerses("showScriptureReferences")}
        >
          <BookOpen className="w-5 h-5" />
          <span className="text-sm font-medium">{displayedVerses.length}</span>
        </button>
      )}

      {/* Mobile slide-over panel for verses */}
      {mobileVersesOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setMobileVersesOpen(false)}
          />
          {/* Panel */}
          <div className="absolute right-0 top-0 bottom-0 w-80 max-w-[85vw] bg-white shadow-xl flex flex-col animate-in slide-in-from-right duration-200">
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-gray-700">
                  {tVerses("scriptureReferences")}
                </h3>
                <button
                  onClick={() => setMobileVersesOpen(false)}
                  className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                  aria-label={tVerses("close")}
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>
              <span className="text-xs text-gray-400">
                {tVerses("verseCount", { count: displayedVerses.length })}
              </span>
              {/* Filter Toggle */}
              <div className="flex items-center gap-2 mt-2">
                <button
                  onClick={() => setShowOnlyReferenced(true)}
                  className={`flex-1 text-xs px-2 py-1.5 rounded-l-md border transition-colors ${
                    showOnlyReferenced
                      ? "bg-primary-100 border-primary-300 text-primary-700 font-medium"
                      : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {tVerses("referenced")}
                </button>
                <button
                  onClick={() => setShowOnlyReferenced(false)}
                  className={`flex-1 text-xs px-2 py-1.5 rounded-r-md border-t border-r border-b transition-colors ${
                    !showOnlyReferenced
                      ? "bg-primary-100 border-primary-300 text-primary-700 font-medium"
                      : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {tVerses("allRelated", { count: relevantVerses.length })}
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {displayedVerses.length > 0 ? (
                <div className="space-y-3">
                  {displayedVerses.map((verse, index) => (
                    <VerseCard
                      key={index}
                      verse={verse}
                      onClick={() => {
                        handleVerseClick(
                          verse.book,
                          verse.chapter,
                          verse.verse,
                          verse.translation,
                        );
                        setMobileVersesOpen(false);
                      }}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-500 text-sm py-8">
                  <Filter className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                  <p>{tVerses("noVersesReferenced")}</p>
                  <p className="text-xs mt-1">
                    {tVerses("noVersesReferencedHint")}
                  </p>
                  {relevantVerses.length > 0 && (
                    <button
                      className="mt-3 text-xs text-amber-600 hover:text-amber-700 underline"
                      onClick={() => setShowOnlyReferenced(false)}
                    >
                      {tVerses("allRelated", { count: relevantVerses.length })}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Chapter Modal */}
      {modalChapter && (
        <ChapterModal
          isOpen={modalOpen}
          onClose={handleCloseModal}
          book={modalChapter.book}
          chapter={modalChapter.chapter}
          verses={modalChapter.verses}
          highlightVerse={modalChapter.highlightVerse}
          isLoading={modalLoading}
          translationName={modalChapter.translationName}
          localized_book={modalChapter.localized_book}
          error={modalError}
          onPrevChapter={
            modalChapter.chapter > 1
              ? () =>
                  handleVerseClick(
                    modalChapter.book,
                    modalChapter.chapter - 1,
                    1,
                  )
              : undefined
          }
          onNextChapter={() =>
            handleVerseClick(modalChapter.book, modalChapter.chapter + 1, 1)
          }
          hasPrevChapter={modalChapter.chapter > 1}
          hasNextChapter={true}
        />
      )}

      {/* Church Finder Modal */}
      <ChurchFinderModal
        isOpen={churchFinderModalOpen}
        onClose={() => setChurchFinderModalOpen(false)}
      />

      {/* Toast notification for errors */}
      {feedbackError && (
        <div className="fixed bottom-4 right-4 z-50 animate-in slide-in-from-bottom-2">
          <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-lg shadow-lg flex items-center gap-3">
            <span className="text-sm">{feedbackError}</span>
            <button
              onClick={() => setFeedbackError(null)}
              className="text-amber-600 hover:text-amber-800"
            >
              &times;
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
