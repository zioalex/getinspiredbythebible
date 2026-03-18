import { describe, it, expect, vi } from 'vitest';
import { getPreferredLocale } from './locale-detection';

vi.mock('@/i18n/routing', () => ({
  routing: { locales: ['en', 'it', 'de'], defaultLocale: 'en' },
}));

describe('getPreferredLocale', () => {
  describe('returns default locale', () => {
    it('when Accept-Language is null', () => {
      expect(getPreferredLocale(null)).toBe('en');
    });

    it('when Accept-Language is empty string', () => {
      expect(getPreferredLocale('')).toBe('en');
    });

    it('when no supported locale is found', () => {
      expect(getPreferredLocale('fr,es;q=0.9,pt;q=0.8')).toBe('en');
    });
  });

  describe('detects single locale', () => {
    it('matches exact locale code', () => {
      expect(getPreferredLocale('it')).toBe('it');
    });

    it('matches locale with region subtag', () => {
      expect(getPreferredLocale('de-DE')).toBe('de');
    });

    it('matches locale with region subtag (Italian)', () => {
      expect(getPreferredLocale('it-IT')).toBe('it');
    });

    it('matches English explicitly', () => {
      expect(getPreferredLocale('en-US')).toBe('en');
    });
  });

  describe('respects quality weights', () => {
    it('picks highest quality supported locale', () => {
      expect(getPreferredLocale('fr;q=1.0,de;q=0.9,en;q=0.8')).toBe('de');
    });

    it('picks Italian when it has highest quality among supported', () => {
      expect(getPreferredLocale('fr;q=1.0,it;q=0.9,en;q=0.5')).toBe('it');
    });

    it('treats missing quality as q=1.0', () => {
      expect(getPreferredLocale('de,en;q=0.9')).toBe('de');
    });

    it('handles wildcard with lower quality', () => {
      expect(getPreferredLocale('it;q=0.8,*;q=0.1')).toBe('it');
    });
  });

  describe('handles realistic browser Accept-Language headers', () => {
    it('Chrome German user', () => {
      expect(getPreferredLocale('de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7')).toBe('de');
    });

    it('Firefox Italian user', () => {
      expect(getPreferredLocale('it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3')).toBe('it');
    });

    it('Safari English user', () => {
      expect(getPreferredLocale('en-US,en;q=0.9')).toBe('en');
    });

    it('multilingual user preferring unsupported language falls to first supported', () => {
      expect(getPreferredLocale('ja;q=1.0,zh;q=0.9,de;q=0.8,en;q=0.7')).toBe('de');
    });

    it('handles spaces in header values', () => {
      expect(getPreferredLocale('it-IT, en-US;q=0.9, de;q=0.8')).toBe('it');
    });
  });

  describe('case insensitivity', () => {
    it('handles uppercase locale codes', () => {
      expect(getPreferredLocale('DE-DE')).toBe('de');
    });

    it('handles mixed case', () => {
      expect(getPreferredLocale('It-IT,En;q=0.5')).toBe('it');
    });
  });
});
