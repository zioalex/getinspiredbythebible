"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Send, Book, Loader2, RefreshCw, Filter } from "lucide-react";
import ChatMessage from "@/components/ChatMessage";
import VerseCard from "@/components/VerseCard";
import ChapterModal from "@/components/ChapterModal";
import ChurchFinderBanner from "@/components/ChurchFinderBanner";
import ChurchFinderModal from "@/components/ChurchFinderModal";
import {
  sendMessage,
  Message,
  Verse,
  getChapter,
  getTranslations,
  TranslationInfo,
} from "@/lib/api";
import {
  extractVerseReferences,
  isVerseReferenced,
} from "@/lib/verseExtraction";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [relevantVerses, setRelevantVerses] = useState<Verse[]>([]);
  const [showOnlyReferenced, setShowOnlyReferenced] = useState(true); // Default to showing only referenced verses
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const versesEndRef = useRef<HTMLDivElement>(null);

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

  // Track detected translation from chat
  const [detectedTranslation, setDetectedTranslation] = useState<string | null>(
    null,
  );

  // Church finder state
  const [interactionCount, setInteractionCount] = useState(0);
  const [churchFinderDismissed, setChurchFinderDismissed] = useState(false);
  const [churchFinderModalOpen, setChurchFinderModalOpen] = useState(false);

  // Show church finder banner after 3+ messages and not dismissed
  const showChurchFinderBanner =
    interactionCount >= 3 && !churchFinderDismissed && messages.length > 0;

  // Translation preference
  const [translations, setTranslations] = useState<TranslationInfo[]>([]);
  const [selectedTranslation, setSelectedTranslation] = useState<string>("");

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
    loadTranslations();
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

  const scrollVersesToBottom = () => {
    versesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    scrollVersesToBottom();
  }, [relevantVerses]);

  // Extract verse references mentioned in chat messages
  const referencedVerses = useMemo(() => {
    const allText = messages
      .filter((m) => m.role === "assistant")
      .map((m) => m.content)
      .join(" ");

    return extractVerseReferences(allText);
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

    setModalOpen(true);
    setModalLoading(true);
    setModalChapter({ book, chapter, verses: [], highlightVerse: verse });

    try {
      const chapterData = await getChapter(book, chapter, useTranslation);
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
    } finally {
      setModalLoading(false);
    }
  };

  const handleCloseModal = () => {
    setModalOpen(false);
    setModalChapter(null);
  };
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await sendMessage(
        userMessage.content,
        messages,
        selectedTranslation || undefined,
      );

      const assistantMessage: Message = {
        role: "assistant",
        content: response.message,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Update detected translation from response
      if (response.detected_translation) {
        setDetectedTranslation(response.detected_translation);
      }

      // Append relevant verses if returned
      if (response.scripture_context?.verses) {
        setRelevantVerses((prev) => [
          ...prev,
          ...(response.scripture_context?.verses || []),
        ]);
      }

      // Increment interaction count for church finder
      setInteractionCount((prev) => prev + 1);
    } catch (error) {
      console.error("Failed to send message:", error);
      const errorMessage: Message = {
        role: "assistant",
        content:
          "I'm sorry, it's taking longer than expected to respond. This can happen when the system is warming up. Please try sending your message again in a moment.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setRelevantVerses([]);
    setDetectedTranslation(null);
    setInteractionCount(0);
    setChurchFinderDismissed(false);
  };

  const suggestedPrompts = [
    "I'm feeling anxious about the future",
    "What does the Bible say about forgiveness?",
    "I need encouragement today",
    "Help me understand John 3:16",
  ];

  return (
    <main className="flex h-screen">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col max-w-4xl mx-auto">
        {/* Header */}
        <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-sm border-b border-primary-100 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Book className="w-8 h-8 text-primary-600" />
              <div>
                <h1 className="text-xl font-semibold text-gray-800">
                  Bible Inspiration
                </h1>
                <p className="text-sm text-gray-500">
                  Find encouragement through Scripture
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {/* Translation Selector */}
              {translations.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Bible version:</span>
                  <select
                    value={selectedTranslation}
                    onChange={(e) => handleTranslationChange(e.target.value)}
                    className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="">Auto-detect</option>
                    {translations.map((t) => (
                      <option key={t.code} value={t.code}>
                        {t.language} - {t.short_name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <button
                onClick={handleNewChat}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                New Chat
              </button>
            </div>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Book className="w-16 h-16 text-primary-300 mb-4" />
              <h2 className="text-2xl font-serif text-gray-700 mb-2">
                Welcome
              </h2>
              <p className="text-gray-500 max-w-md mb-8">
                Share what's on your heart, ask questions about Scripture, or
                simply seek encouragement. I'm here to help you find wisdom and
                comfort in God's Word.
              </p>

              {/* Suggested Prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                {suggestedPrompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => setInput(prompt)}
                    className="text-left px-4 py-3 bg-white border border-primary-200 rounded-lg text-sm text-gray-700 hover:border-primary-400 hover:bg-primary-50 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message, index) => (
                <ChatMessage
                  key={index}
                  message={message}
                  onVerseClick={handleVerseClick}
                />
              ))}

              {isLoading && (
                <div className="flex items-center gap-3 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Searching Scripture and reflecting...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Share what's on your heart..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="px-6 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
          <p className="text-xs text-gray-400 mt-2 text-center">
            Responses are AI-generated. For serious concerns, please seek
            pastoral or professional guidance.
          </p>

          {/* Church Finder Banner */}
          {showChurchFinderBanner && (
            <ChurchFinderBanner
              onFindChurch={() => setChurchFinderModalOpen(true)}
              onDismiss={() => setChurchFinderDismissed(true)}
            />
          )}
        </div>
      </div>

      {/* Sidebar - Relevant Verses */}
      {relevantVerses.length > 0 && (
        <aside className="hidden lg:flex lg:flex-col w-80 border-l border-gray-200 bg-white/50">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-700">
                Scripture References
              </h3>
              <span className="text-xs text-gray-400">
                {displayedVerses.length} verse
                {displayedVerses.length !== 1 ? "s" : ""}
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
                Referenced
              </button>
              <button
                onClick={() => setShowOnlyReferenced(false)}
                className={`flex-1 text-xs px-2 py-1.5 rounded-r-md border-t border-r border-b transition-colors ${
                  !showOnlyReferenced
                    ? "bg-primary-100 border-primary-300 text-primary-700 font-medium"
                    : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"
                }`}
              >
                All Related ({relevantVerses.length})
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
                <p>No verses referenced yet.</p>
                <p className="text-xs mt-1">
                  Verses will appear here when mentioned in the chat.
                </p>
              </div>
            )}
          </div>
        </aside>
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
        />
      )}

      {/* Church Finder Modal */}
      <ChurchFinderModal
        isOpen={churchFinderModalOpen}
        onClose={() => setChurchFinderModalOpen(false)}
      />
    </main>
  );
}
