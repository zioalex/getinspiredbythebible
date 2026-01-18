'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Book, Loader2, RefreshCw } from 'lucide-react'
import ChatMessage from '@/components/ChatMessage'
import VerseCard from '@/components/VerseCard'
import { sendMessage, Message, Verse } from '@/lib/api'

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [relevantVerses, setRelevantVerses] = useState<Verse[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await sendMessage(userMessage.content, messages)

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.message,
      }

      setMessages((prev) => [...prev, assistantMessage])

      // Update relevant verses if returned
      if (response.scripture_context?.verses) {
        setRelevantVerses(response.scripture_context.verses)
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content:
          "I'm sorry, I encountered an error. Please make sure the API server is running and try again.",
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setRelevantVerses([])
  }

  const suggestedPrompts = [
    "I'm feeling anxious about the future",
    'What does the Bible say about forgiveness?',
    "I need encouragement today",
    'Help me understand John 3:16',
  ]

  return (
    <main className="flex min-h-screen">
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
            <button
              onClick={handleNewChat}
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              New Chat
            </button>
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
                <ChatMessage key={index} message={message} />
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
        </div>
      </div>

      {/* Sidebar - Relevant Verses */}
      {relevantVerses.length > 0 && (
        <aside className="hidden lg:block w-80 border-l border-gray-200 bg-white/50 overflow-y-auto">
          <div className="p-4">
            <h3 className="font-semibold text-gray-700 mb-4">
              Related Scripture
            </h3>
            <div className="space-y-3">
              {relevantVerses.map((verse, index) => (
                <VerseCard key={index} verse={verse} />
              ))}
            </div>
          </div>
        </aside>
      )}
    </main>
  )
}
