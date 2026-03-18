import { screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChatMessage from './ChatMessage';
import { renderWithIntl } from '@/test/i18n-helpers';

// Mock react-markdown to avoid complex rendering
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));

describe('ChatMessage responsive classes', () => {
  it('renders user message with responsive gap and avatar sizes', () => {
    const { container } = renderWithIntl(
      <ChatMessage message={{ role: 'user', content: 'Hello' }} />
    );

    // Outer flex container should have responsive gap
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain('gap-2');
    expect(wrapper.className).toContain('sm:gap-4');
  });

  it('renders user avatar with responsive size', () => {
    renderWithIntl(<ChatMessage message={{ role: 'user', content: 'Hello' }} />);
    const avatars = document.querySelectorAll('[class*="rounded-full"]');
    const userAvatar = avatars[0];
    expect(userAvatar.className).toContain('w-8');
    expect(userAvatar.className).toContain('h-8');
    expect(userAvatar.className).toContain('sm:w-10');
    expect(userAvatar.className).toContain('sm:h-10');
  });

  it('renders assistant avatar with responsive size', () => {
    renderWithIntl(<ChatMessage message={{ role: 'assistant', content: 'Peace be with you' }} />);
    const avatars = document.querySelectorAll('[class*="rounded-full"]');
    const assistantAvatar = avatars[0];
    expect(assistantAvatar.className).toContain('w-8');
    expect(assistantAvatar.className).toContain('h-8');
    expect(assistantAvatar.className).toContain('sm:w-10');
    expect(assistantAvatar.className).toContain('sm:h-10');
  });

  it('renders message bubble with responsive max-width and padding', () => {
    const { container } = renderWithIntl(
      <ChatMessage message={{ role: 'user', content: 'Hello' }} />
    );
    const bubble = container.querySelector('[class*="rounded-2xl"]');
    expect(bubble).not.toBeNull();
    expect(bubble!.className).toContain('max-w-[90%]');
    expect(bubble!.className).toContain('sm:max-w-[80%]');
    expect(bubble!.className).toContain('px-4');
    expect(bubble!.className).toContain('py-3');
    expect(bubble!.className).toContain('sm:px-5');
    expect(bubble!.className).toContain('sm:py-4');
  });
});
