'use client';

import { MapPin, X } from 'lucide-react';
import { useTranslations } from 'next-intl';

interface ChurchFinderBannerProps {
  onFindChurch: () => void;
  onDismiss: () => void;
}

export default function ChurchFinderBanner({ onFindChurch, onDismiss }: ChurchFinderBannerProps) {
  const t = useTranslations('ChurchFinder');

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-3 px-4 py-3 bg-teal-50 border border-teal-200 rounded-xl mt-3">
      <div className="flex items-center gap-3">
        <MapPin className="w-5 h-5 text-teal-600 flex-shrink-0" />
        <p className="text-sm text-teal-800">{t('bannerText')}</p>
      </div>
      <div className="flex items-center gap-2 self-end sm:self-auto">
        <button
          onClick={onFindChurch}
          className="px-3 py-1.5 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors"
        >
          {t('findChurch')}
        </button>
        <button
          onClick={onDismiss}
          className="p-1.5 text-teal-600 hover:bg-teal-100 rounded-lg transition-colors"
          aria-label={t('dismiss')}
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
