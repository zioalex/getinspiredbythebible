"use client";

import { useEffect, useState } from "react";
import { Smartphone } from "lucide-react";
import { isIOSUserAgent } from "@/lib/platformDetection";

interface AppInstallCtaProps {
  iconAlt: string;
  ctaSub: string;
  ctaButton: string;
  iosCtaTitle: string;
  iosCtaBody: string;
  iosCtaSub: string;
  playStoreUrl: string;
}

/**
 * Primary call to action on the /app story page — Google Play on
 * Android/desktop, iOS "Add to Home Screen" instructions on iPhone.
 *
 * The iOS/non-iOS branch is detected client-side (rather than server-side
 * via the User-Agent request header) so that the page this renders inside
 * of can stay a fully static server component. `isIOS` defaults to `false`
 * so the very first render — both server-rendered HTML and the client's
 * initial hydration pass — always matches: the non-iOS (Play Store) CTA.
 * The iOS variant only swaps in after the `useEffect` below runs on the
 * client, avoiding any hydration mismatch.
 */
export default function AppInstallCta({
  iconAlt,
  ctaSub,
  ctaButton,
  iosCtaTitle,
  iosCtaBody,
  iosCtaSub,
  playStoreUrl,
}: AppInstallCtaProps) {
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    setIsIOS(isIOSUserAgent(navigator.userAgent));
  }, []);

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-5 bg-white border border-primary-100 rounded-xl mb-12">
      <img
        src="/app-icon.png"
        alt={iconAlt}
        width={64}
        height={64}
        className="w-16 h-16 rounded-2xl flex-shrink-0"
      />
      {isIOS ? (
        <div className="flex-1">
          <p className="font-semibold text-primary-900">Vox Quieta</p>
          <p className="text-sm font-medium text-gray-800">{iosCtaTitle}</p>
          <p className="text-sm text-gray-500 mb-2">{iosCtaSub}</p>
          <p className="text-sm text-gray-600">{iosCtaBody}</p>
        </div>
      ) : (
        <>
          <div className="flex-1">
            <p className="font-semibold text-primary-900">Vox Quieta</p>
            <p className="text-sm text-gray-500">{ctaSub}</p>
          </div>
          <a
            href={playStoreUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 inline-flex items-center justify-center gap-2 px-5 py-3 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded-full shadow-sm hover:shadow transition-all whitespace-nowrap"
          >
            <Smartphone className="w-4 h-4" />
            {ctaButton}
          </a>
        </>
      )}
    </div>
  );
}
