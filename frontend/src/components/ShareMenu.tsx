'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Share2, Copy, Check } from 'lucide-react';
import { useTranslations } from 'next-intl';

interface ShareMenuProps {
  /** The user's question */
  question: string;
  /** The assistant's answer */
  answer: string;
}

export default function ShareMenu({ question, answer }: ShareMenuProps) {
  const t = useTranslations('Share');
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const shareText = `${t('sharePrefix')}\n\nQ: ${question}\n\n${answer}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = shareText;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Truncate for URL-safe sharing (most platforms have limits)
  const truncatedText = shareText.length > 500 ? shareText.slice(0, 497) + '...' : shareText;
  const encodedText = encodeURIComponent(truncatedText);

  const shareLinks = [
    {
      key: 'copy',
      label: copied ? t('copied') : t('copyToClipboard'),
      icon: copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />,
      onClick: handleCopy,
    },
    {
      key: 'whatsapp',
      label: t('shareOnWhatsApp'),
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
        </svg>
      ),
      href: `https://wa.me/?text=${encodedText}`,
    },
    {
      key: 'twitter',
      label: t('shareOnTwitter'),
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      ),
      href: `https://twitter.com/intent/tweet?text=${encodedText}`,
    },
    {
      key: 'facebook',
      label: t('shareOnFacebook'),
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
        </svg>
      ),
      href: `https://www.facebook.com/sharer/sharer.php?quote=${encodedText}`,
    },
    {
      key: 'bluesky',
      label: t('shareOnBluesky'),
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 568 501" fill="currentColor">
          <path d="M123.121 33.6637C188.241 82.5526 258.281 181.681 284 234.873C309.719 181.681 379.759 82.5526 444.879 33.6637C491.866 -1.61183 568 -28.9064 568 57.9464C568 75.2916 558.055 189.434 552 208.099C531.963 272.676 462.381 287.674 399.326 276.827C507.222 295.344 536.444 388.672 473.333 428.073C364.946 494.268 324.525 345.504 288.912 254.58C285.764 246.955 284.382 242.699 284 240.971C283.618 242.699 282.236 246.955 279.088 254.58C243.475 345.504 203.054 494.268 94.6667 428.073C31.5556 388.672 60.7778 295.344 168.674 276.827C105.619 287.674 36.0373 272.676 16 208.099C9.94533 189.434 0 75.2916 0 57.9464C0 -28.9064 76.1338 -1.61183 123.121 33.6637Z" />
        </svg>
      ),
      href: `https://bsky.app/intent/compose?text=${encodedText}`,
    },
  ];

  return (
    <div ref={menuRef} className="relative inline-block">
      <button
        onClick={() => setOpen(!open)}
        className="p-1.5 rounded-lg text-gray-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
        aria-label={t('share')}
        title={t('share')}
      >
        <Share2 className="w-4 h-4" />
      </button>

      {open && (
        <div className="absolute bottom-full right-0 mb-1 w-52 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
          {shareLinks.map(item =>
            item.href ? (
              <a
                key={item.key}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                onClick={() => setOpen(false)}
              >
                {item.icon}
                {item.label}
              </a>
            ) : (
              <button
                key={item.key}
                onClick={() => {
                  item.onClick?.();
                }}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {item.icon}
                {item.label}
              </button>
            )
          )}
        </div>
      )}
    </div>
  );
}
