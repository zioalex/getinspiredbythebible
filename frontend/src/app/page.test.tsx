import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockRedirect = vi.fn();
const mockHeaders = vi.fn();

vi.mock('next/navigation', () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

vi.mock('next/headers', () => ({
  headers: () => mockHeaders(),
}));

vi.mock('@/i18n/routing', () => ({
  routing: { locales: ['en', 'it', 'de'], defaultLocale: 'en' },
}));

// Import after mocks are set up
import RootPage from './page';

function createMockHeaders(acceptLanguage: string | null) {
  return {
    get: (name: string) => {
      if (name === 'accept-language') return acceptLanguage;
      return null;
    },
  };
}

describe('RootPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('redirects to /en when no Accept-Language header', async () => {
    mockHeaders.mockResolvedValue(createMockHeaders(null));
    await RootPage();
    expect(mockRedirect).toHaveBeenCalledWith('/en');
  });

  it('redirects to /de for German browser', async () => {
    mockHeaders.mockResolvedValue(createMockHeaders('de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'));
    await RootPage();
    expect(mockRedirect).toHaveBeenCalledWith('/de');
  });

  it('redirects to /it for Italian browser', async () => {
    mockHeaders.mockResolvedValue(createMockHeaders('it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3'));
    await RootPage();
    expect(mockRedirect).toHaveBeenCalledWith('/it');
  });

  it('redirects to /en for English browser', async () => {
    mockHeaders.mockResolvedValue(createMockHeaders('en-US,en;q=0.9'));
    await RootPage();
    expect(mockRedirect).toHaveBeenCalledWith('/en');
  });

  it('falls back to /en for unsupported language', async () => {
    mockHeaders.mockResolvedValue(createMockHeaders('ja,zh;q=0.9'));
    await RootPage();
    expect(mockRedirect).toHaveBeenCalledWith('/en');
  });

  it('picks best supported locale when preferred is unsupported', async () => {
    mockHeaders.mockResolvedValue(createMockHeaders('fr;q=1.0,it;q=0.8,en;q=0.5'));
    await RootPage();
    expect(mockRedirect).toHaveBeenCalledWith('/it');
  });

  it('calls redirect exactly once', async () => {
    mockHeaders.mockResolvedValue(createMockHeaders('en'));
    await RootPage();
    expect(mockRedirect).toHaveBeenCalledTimes(1);
  });
});
