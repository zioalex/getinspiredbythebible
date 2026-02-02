"use client";

import { MapPin, X } from "lucide-react";

interface ChurchFinderInlinePromptProps {
  onFindChurch: () => void;
  onDismiss: () => void;
}

export default function ChurchFinderInlinePrompt({
  onFindChurch,
  onDismiss,
}: ChurchFinderInlinePromptProps) {
  return (
    <div className="flex justify-center my-4">
      <div className="inline-flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-teal-50 to-blue-50 border border-teal-100 rounded-2xl shadow-sm max-w-md">
        <MapPin className="w-5 h-5 text-teal-500 flex-shrink-0" />
        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
          <p className="text-sm text-gray-600">
            Looking for a prayer community or church?
          </p>
          <button
            onClick={onFindChurch}
            className="text-sm font-medium text-teal-600 hover:text-teal-700 hover:underline transition-colors whitespace-nowrap"
          >
            Find one nearby
          </button>
        </div>
        <button
          onClick={onDismiss}
          className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
