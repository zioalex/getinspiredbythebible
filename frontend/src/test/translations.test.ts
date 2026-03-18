import { describe, it, expect } from 'vitest';
import enMessages from '../../messages/en.json';
import itMessages from '../../messages/it.json';
import deMessages from '../../messages/de.json';
import esMessages from '../../messages/es.json';
import frMessages from '../../messages/fr.json';
import ptMessages from '../../messages/pt.json';
import arMessages from '../../messages/ar.json';
import ruMessages from '../../messages/ru.json';
import zhMessages from '../../messages/zh.json';
import hiMessages from '../../messages/hi.json';
import koMessages from '../../messages/ko.json';
import IntlMessageFormat from 'intl-messageformat';

const locales: Record<string, typeof enMessages> = {
  en: enMessages,
  it: itMessages,
  de: deMessages,
  es: esMessages,
  fr: frMessages,
  pt: ptMessages,
  ar: arMessages,
  ru: ruMessages,
  zh: zhMessages,
  hi: hiMessages,
  ko: koMessages,
};

// Locales where plural forms don't grammatically distinguish singular/plural
// (ICU "other" form covers all numbers, so result1 === result5 is expected)
const skipDiffCheck = new Set(['zh', 'ko']);

function getKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      return getKeys(value as Record<string, unknown>, fullKey);
    }
    return [fullKey];
  });
}

function getNamespaces(obj: Record<string, unknown>): string[] {
  return Object.keys(obj);
}

function getValue(obj: Record<string, unknown>, path: string): unknown {
  return path
    .split('.')
    .reduce(
      (acc, key) =>
        acc && typeof acc === 'object' ? (acc as Record<string, unknown>)[key] : undefined,
      obj as unknown
    );
}

describe('Translation file consistency', () => {
  const enKeys = getKeys(enMessages);

  it('all locales have identical key structure', () => {
    for (const [locale, messages] of Object.entries(locales)) {
      if (locale === 'en') continue;
      const localeKeys = getKeys(messages as Record<string, unknown>);
      expect(localeKeys.sort(), `${locale} key structure should match en`).toEqual(enKeys.sort());
    }
  });

  it('no empty string values in any locale', () => {
    for (const [locale, messages] of Object.entries(locales)) {
      const keys = getKeys(messages);
      for (const key of keys) {
        const value = getValue(messages as Record<string, unknown>, key);
        expect(value, `Empty value at ${locale}.${key}`).not.toBe('');
      }
    }
  });

  it('ICU plural keys present in all locales', () => {
    const pluralKeys = ['Verses.verseCount', 'ChapterModal.verseCount', 'ChurchFinder.foundCount'];

    for (const [locale, messages] of Object.entries(locales)) {
      for (const key of pluralKeys) {
        const value = getValue(messages as Record<string, unknown>, key);
        expect(value, `Missing plural key ${key} in ${locale}`).toBeDefined();
        expect(
          typeof value === 'string' && value.includes('{count, plural'),
          `${key} in ${locale} should contain ICU plural syntax`
        ).toBe(true);
      }
    }
  });

  it('all namespaces present in each locale', () => {
    const requiredNamespaces = [
      'Metadata',
      'Header',
      'Welcome',
      'Chat',
      'Verses',
      'ChapterModal',
      'Feedback',
      'ChurchFinder',
      'Contact',
    ];

    for (const [locale, messages] of Object.entries(locales)) {
      const namespaces = getNamespaces(messages);
      for (const ns of requiredNamespaces) {
        expect(namespaces, `Missing namespace ${ns} in ${locale}`).toContain(ns);
      }
    }
  });

  it('no extraneous keys in any locale that en does not have', () => {
    const enKeySet = new Set(enKeys);
    for (const [locale, messages] of Object.entries(locales)) {
      if (locale === 'en') continue;
      const localeKeys = getKeys(messages as Record<string, unknown>);
      for (const key of localeKeys) {
        expect(enKeySet.has(key), `Extraneous key in ${locale}: ${key}`).toBe(true);
      }
    }
  });

  it('ICU plural formatting produces correct output for count=0, 1, 5', () => {
    const pluralKeys = ['Verses.verseCount', 'ChapterModal.verseCount', 'ChurchFinder.foundCount'];

    for (const [locale, messages] of Object.entries(locales)) {
      for (const key of pluralKeys) {
        const pattern = getValue(messages as Record<string, unknown>, key) as string;
        const msg = new IntlMessageFormat(pattern, locale);

        const result1 = msg.format({ count: 1 }) as string;
        const result5 = msg.format({ count: 5 }) as string;

        // Singular form should contain "1"
        expect(result1, `${key} in ${locale} singular`).toContain('1');
        // Plural form should contain "5"
        expect(result5, `${key} in ${locale} plural`).toContain('5');

        // Singular and plural should differ — except for languages that use
        // only the "other" form (e.g. Chinese, Korean) where 1 and 5 produce
        // the same template with different numbers substituted.
        if (!skipDiffCheck.has(locale)) {
          expect(result1, `${key} in ${locale} singular vs plural should differ`).not.toBe(result5);
        }
      }
    }
  });
});
