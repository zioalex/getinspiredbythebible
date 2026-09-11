"use client";

/**
 * BITB-080: one-tap follow-up question chips rendered under the LATEST
 * assistant message only. Deliberately generic ({ suggestions, onSelect,
 * disabled, label }) so BITB-078's clarifying-question chip UI (deferred at
 * the time this shipped -- see docs/BACKLOG.md) can reuse this same component
 * rather than a second one.
 */
interface FollowUpSuggestionsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
  disabled?: boolean;
  label: string;
}

export default function FollowUpSuggestions({
  suggestions,
  onSelect,
  disabled = false,
  label,
}: FollowUpSuggestionsProps) {
  // Degrade silently: no spinner, no empty row when there is nothing to show.
  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div
      role="group"
      aria-label={label}
      className="flex flex-wrap gap-2 mt-3 mb-2"
    >
      {suggestions.map((suggestion, index) => (
        <button
          key={index}
          type="button"
          onClick={() => onSelect(suggestion)}
          disabled={disabled}
          className="text-left px-3 py-2 bg-white border border-primary-200 rounded-lg text-sm text-gray-700 hover:border-primary-400 hover:bg-primary-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}
