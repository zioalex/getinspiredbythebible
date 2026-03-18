import { screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import FeedbackModal from './FeedbackModal';
import { renderWithIntl } from '@/test/i18n-helpers';

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  onSubmit: vi.fn(),
  rating: 'positive' as const,
};

describe('FeedbackModal', () => {
  it('returns null when isOpen is false', () => {
    const { container } = renderWithIntl(<FeedbackModal {...defaultProps} isOpen={false} />);
    expect(container.innerHTML).toBe('');
  });

  it('shows positive heading for positive rating', () => {
    renderWithIntl(<FeedbackModal {...defaultProps} rating="positive" />);
    expect(screen.getByText('What was helpful?')).toBeDefined();
  });

  it('shows negative heading for negative rating', () => {
    renderWithIntl(<FeedbackModal {...defaultProps} rating="negative" />);
    expect(screen.getByText('What could be improved?')).toBeDefined();
  });

  it('shows correct placeholder text based on rating', () => {
    const { unmount } = renderWithIntl(<FeedbackModal {...defaultProps} rating="positive" />);
    expect(
      screen.getByPlaceholderText('The verse suggestions were relevant to my question...')
    ).toBeDefined();
    unmount();

    renderWithIntl(<FeedbackModal {...defaultProps} rating="negative" />);
    expect(
      screen.getByPlaceholderText("The response didn't address my specific concern...")
    ).toBeDefined();
  });

  it('calls onSubmit with comment text when form submitted', () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackModal {...defaultProps} onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText(
      'The verse suggestions were relevant to my question...'
    );
    fireEvent.change(textarea, { target: { value: 'Great response!' } });
    fireEvent.submit(textarea.closest('form')!);

    expect(onSubmit).toHaveBeenCalledWith('Great response!');
  });

  it('calls onSubmit with empty string when Skip is clicked', () => {
    const onSubmit = vi.fn();
    renderWithIntl(<FeedbackModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText('Skip'));
    expect(onSubmit).toHaveBeenCalledWith('');
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    renderWithIntl(<FeedbackModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('Close'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when backdrop clicked', () => {
    const onClose = vi.fn();
    const { container } = renderWithIntl(<FeedbackModal {...defaultProps} onClose={onClose} />);
    const backdrop = container.querySelector('[aria-hidden="true"]')!;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows 'Submitting...' when isSubmitting is true", () => {
    renderWithIntl(<FeedbackModal {...defaultProps} isSubmitting={true} />);
    expect(screen.getByText('Submitting...')).toBeDefined();
  });
});
