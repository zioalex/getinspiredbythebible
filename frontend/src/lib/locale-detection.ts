import { routing } from '@/i18n/routing';

/**
 * Parse the Accept-Language header and return the best matching locale.
 * Falls back to the default locale if no match is found.
 */
export function getPreferredLocale(acceptLanguage: string | null): string {
  if (!acceptLanguage) return routing.defaultLocale;

  const preferred = acceptLanguage
    .split(',')
    .map(part => {
      const [lang, q] = part.trim().split(';q=');
      return {
        lang: lang.split('-')[0].toLowerCase(),
        q: q ? parseFloat(q) : 1,
      };
    })
    .sort((a, b) => b.q - a.q);

  for (const { lang } of preferred) {
    if (routing.locales.includes(lang as (typeof routing.locales)[number])) {
      return lang;
    }
  }

  return routing.defaultLocale;
}
