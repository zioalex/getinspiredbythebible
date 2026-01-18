'use client'

import { User, BookOpen } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Message } from '@/lib/api'

interface ChatMessageProps {
  message: Message
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div
      className={`flex gap-4 message-enter ${
        isUser ? 'justify-end' : 'justify-start'
      }`}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
          <BookOpen className="w-5 h-5 text-primary-600" />
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-2xl px-5 py-4 ${
          isUser
            ? 'bg-primary-600 text-white rounded-br-md'
            : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md shadow-sm'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none prose-p:my-2 prose-headings:mt-4 prose-headings:mb-2">
            <ReactMarkdown
              components={{
                // Style scripture references
                strong: ({ children }) => (
                  <strong className="text-primary-700 font-semibold">
                    {children}
                  </strong>
                ),
                // Style blockquotes as scripture
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-primary-300 pl-4 py-1 my-3 bg-primary-50 rounded-r-lg italic scripture-text">
                    {children}
                  </blockquote>
                ),
                // Style inline code as verse references
                code: ({ children }) => (
                  <code className="px-1.5 py-0.5 bg-primary-100 text-primary-700 rounded text-sm font-medium not-italic">
                    {children}
                  </code>
                ),
                // Ensure lists look good
                ul: ({ children }) => (
                  <ul className="list-disc pl-5 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-5 space-y-1">{children}</ol>
                ),
                // Paragraphs
                p: ({ children }) => <p className="my-2">{children}</p>,
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary-600 flex items-center justify-center">
          <User className="w-5 h-5 text-white" />
        </div>
      )}
    </div>
  )
}
