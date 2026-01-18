'use client'

import { BookOpen, ExternalLink } from 'lucide-react'
import { Verse } from '@/lib/api'

interface VerseCardProps {
  verse: Verse
  onClick?: () => void
}

export default function VerseCard({ verse, onClick }: VerseCardProps) {
  // Calculate relevance indicator color based on similarity
  const getRelevanceColor = (similarity?: number) => {
    if (!similarity) return 'bg-gray-200'
    if (similarity > 0.7) return 'bg-green-400'
    if (similarity > 0.5) return 'bg-yellow-400'
    return 'bg-orange-400'
  }

  return (
    <div
      className={`bg-white border border-gray-200 rounded-lg p-4 shadow-sm transition-all ${
        onClick ? 'cursor-pointer hover:shadow-md hover:border-primary-300 hover:bg-primary-50/30' : ''
      }`}
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-primary-500" />
          <span className="font-bold text-primary-700 text-sm">
            {verse.reference}
          </span>
        </div>
        {verse.similarity && (
          <div className="flex items-center gap-1">
            <div
              className={`w-2 h-2 rounded-full ${getRelevanceColor(
                verse.similarity
              )}`}
            />
            <span className="text-xs text-gray-400">
              {Math.round(verse.similarity * 100)}%
            </span>
          </div>
        )}
      </div>

      {/* Verse Text */}
      <p className="text-gray-700 text-sm scripture-text leading-relaxed italic">
        "{verse.text}"
      </p>

      {/* Footer */}
      {onClick && (
        <div className="mt-3 flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-800">
          <span>Read full chapter</span>
          <ExternalLink className="w-3 h-3" />
        </div>
      )}
    </div>
  )
}
