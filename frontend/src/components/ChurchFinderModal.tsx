"use client";

import { useState, useEffect } from "react";
import {
  X,
  MapPin,
  Loader2,
  Globe,
  Phone,
  Mail,
  Search,
  Building2,
} from "lucide-react";
import { searchChurches, Church } from "@/lib/api";

interface ChurchFinderModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ChurchFinderModal({
  isOpen,
  onClose,
}: ChurchFinderModalProps) {
  const [location, setLocation] = useState("");
  const [churches, setChurches] = useState<Church[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setLocation("");
      setChurches([]);
      setError(null);
      setHasSearched(false);
    }
  }, [isOpen]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!location.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await searchChurches(location.trim());
      setChurches(response.churches);
    } catch (err) {
      setError("Failed to search for churches. Please try again.");
      console.error("Church search error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col m-4">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-200 bg-teal-50/50">
          <div className="flex items-center gap-3">
            <MapPin className="w-7 h-7 text-teal-600" />
            <div>
              <h2 className="text-2xl font-serif font-bold text-gray-800">
                Find a Church
              </h2>
              <p className="text-sm text-gray-500">
                Connect with a faith community near you
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <X className="w-6 h-6 text-gray-600" />
          </button>
        </div>

        {/* Search Form */}
        <div className="p-5 border-b border-gray-200">
          <form onSubmit={handleSearch} className="flex gap-3">
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Enter city or country (e.g., Zurich, Switzerland)"
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
              disabled={isLoading}
              autoFocus
            />
            <button
              type="submit"
              disabled={isLoading || !location.trim()}
              className="px-6 py-3 bg-teal-600 text-white rounded-xl hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Search className="w-5 h-5" />
              )}
            </button>
          </form>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-teal-600 mb-3" />
              <p className="text-gray-500">Searching for churches...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-3">
                <X className="w-6 h-6 text-red-600" />
              </div>
              <p className="text-red-600 font-medium">{error}</p>
              <p className="text-sm text-gray-500 mt-1">
                Please check your connection and try again.
              </p>
            </div>
          ) : churches.length > 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-gray-500 mb-4">
                Found {churches.length} church
                {churches.length !== 1 ? "es" : ""}
              </p>
              {churches.map((church, index) => (
                <ChurchCard key={index} church={church} />
              ))}
            </div>
          ) : hasSearched ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Building2 className="w-12 h-12 text-gray-300 mb-3" />
              <p className="text-gray-600 font-medium">No churches found</p>
              <p className="text-sm text-gray-500 mt-1">
                Try a different location or broader search term.
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <MapPin className="w-12 h-12 text-gray-300 mb-3" />
              <p className="text-gray-600">Enter a location to search</p>
              <p className="text-sm text-gray-500 mt-1">
                Search by city, region, or country
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 px-6 py-4">
          <p className="text-xs text-gray-500 text-center">
            Church data provided by{" "}
            <a
              href="https://disciplestoday.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-600 hover:underline"
            >
              DisciplesToday.org
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

function ChurchCard({ church }: { church: Church }) {
  const formatAddress = () => {
    const parts = [church.address, church.city, church.state, church.country]
      .filter(Boolean)
      .join(", ");
    return parts || null;
  };

  const address = formatAddress();

  return (
    <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl hover:border-teal-300 transition-colors">
      <h3 className="font-semibold text-gray-800 mb-2">{church.name}</h3>

      {address && (
        <div className="flex items-start gap-2 text-sm text-gray-600 mb-2">
          <MapPin className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
          <span>{address}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-3 mt-3">
        {church.website && (
          <a
            href={
              church.website.startsWith("http")
                ? church.website
                : `https://${church.website}`
            }
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm text-teal-600 hover:text-teal-800 hover:underline"
          >
            <Globe className="w-4 h-4" />
            Website
          </a>
        )}

        {church.phone && (
          <a
            href={`tel:${church.phone}`}
            className="flex items-center gap-1.5 text-sm text-teal-600 hover:text-teal-800 hover:underline"
          >
            <Phone className="w-4 h-4" />
            {church.phone}
          </a>
        )}

        {church.email && (
          <a
            href={`mailto:${church.email}`}
            className="flex items-center gap-1.5 text-sm text-teal-600 hover:text-teal-800 hover:underline"
          >
            <Mail className="w-4 h-4" />
            Email
          </a>
        )}
      </div>
    </div>
  );
}
