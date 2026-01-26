"use client";

import { MapPin, X } from "lucide-react";

interface ChurchFinderBannerProps {
  onFindChurch: () => void;
  onDismiss: () => void;
}

export default function ChurchFinderBanner({
  onFindChurch,
  onDismiss,
}: ChurchFinderBannerProps) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 bg-teal-50 border border-teal-200 rounded-xl mt-3">
      <div className="flex items-center gap-3">
        <MapPin className="w-5 h-5 text-teal-600 flex-shrink-0" />
        <p className="text-sm text-teal-800">Looking for a faith community?</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onFindChurch}
          className="px-3 py-1.5 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors"
        >
          Find a Church
        </button>
        <button
          onClick={onDismiss}
          className="p-1.5 text-teal-600 hover:bg-teal-100 rounded-lg transition-colors"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
