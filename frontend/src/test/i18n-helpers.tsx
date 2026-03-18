import React from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import enMessages from '../../messages/en.json';
import itMessages from '../../messages/it.json';
import deMessages from '../../messages/de.json';

const allMessages: Record<string, typeof enMessages> = {
  en: enMessages,
  it: itMessages,
  de: deMessages,
};

function IntlWrapper({ children }: { children: React.ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages}>
      {children}
    </NextIntlClientProvider>
  );
}

export function renderWithIntl(ui: React.ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  return render(ui, { wrapper: IntlWrapper, ...options });
}

export function renderWithIntlLocale(
  ui: React.ReactElement,
  locale: string,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  const messages = allMessages[locale] ?? enMessages;
  return render(ui, {
    wrapper: ({ children }) => (
      <NextIntlClientProvider locale={locale} messages={messages}>
        {children}
      </NextIntlClientProvider>
    ),
    ...options,
  });
}
