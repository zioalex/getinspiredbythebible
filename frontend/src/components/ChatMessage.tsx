'use client'

import React from 'react'
import { User, BookOpen } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Message } from '@/lib/api'

interface ChatMessageProps {
  message: Message
  onVerseClick?: (book: string, chapter: number, verse: number) => void
}

export default function ChatMessage({ message, onVerseClick }: ChatMessageProps) {
  const isUser = message.role === 'user'

  // Parse verse references like "John 3:16" or "Genesis 1:1"
  const handleTextClick = (e: React.MouseEvent) => {
    if (!onVerseClick) return

    const target = e.target as HTMLElement
    const text = target.textContent || ''
    
    // Match patterns like "John 3:16", "1 John 2:3", "Psalms 143:4"
    const versePattern = /(\d?\s?[A-Za-z]+)\s+(\d+):(\d+)/
    const match = text.match(versePattern)
    
    if (match) {
      const book = match[1].trim()
      const chapter = parseInt(match[2])
      const verse = parseInt(match[3])
      onVerseClick(book, chapter, verse)
    }
  }

  // Helper function to highlight verse references and quoted text in a string
  const highlightText = (text: string, key: number): React.ReactNode => {
    // Pattern to match verse references like "Psalms 143:4:" at the start of text
    const verseRefPattern = /^(\d?\s?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\d+:\d+):/
    const match = text.match(verseRefPattern)
    
    if (match) {
      const verseRef = match[1]
      const afterRef = text.slice(match[0].length)
      
      return (
        <React.Fragment key={key}>
          <span 
            className="text-amber-800 font-bold cursor-pointer hover:underline"
            onClick={handleTextClick}
          >
            {verseRef}:
          </span>
          {highlightQuotes(afterRef, key + 1000)}
        </React.Fragment>
      )
    }
    
    return highlightQuotes(text, key)
  }

  // Helper function to highlight quoted scripture text
  const highlightQuotes = (text: string, key: number): React.ReactNode => {
    const parts: React.ReactNode[] = []
    const quotePattern = /"([^"]+)"/g
    let lastIndex = 0
    let match
    let partKey = 0

    while ((match = quotePattern.exec(text)) !== null) {
      // Add text before the quote
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index))
      }
      // Add the quoted text with highlighting
      parts.push(
        <span 
          key={`${key}-quote-${partKey++}`} 
          className="bg-amber-50 text-amber-900 px-1 py-0.5 rounded italic font-serif border-l-2 border-amber-400"
        >
          "{match[1]}"
        </span>
      )
      lastIndex = match.index + match[0].length
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }
    
    return parts.length > 0 ? <React.Fragment key={key}>{parts}</React.Fragment> : text
  }

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
                // Custom paragraph renderer to highlight verse references
                p: ({ children }) => {
                  const processedChildren = React.Children.map(children, (child, idx) => {
                    if (typeof child === 'string') {
                      return highlightText(child, idx)
                    }
                    return child
                  })
                  return <p className="my-2 leading-relaxed">{processedChildren}</p>
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
                // Ensure lists look good
                ul: ({ children }) => (
                  <ul className="list-disc pl-5 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-5 space-y-1">{children}</ol>
                ),
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
