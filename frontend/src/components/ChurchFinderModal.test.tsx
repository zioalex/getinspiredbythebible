import { screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChurchFinderModal from './ChurchFinderModal';
import { renderWithIntl } from '@/test/i18n-helpers';
import { searchChurches, Church } from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  searchChurches: vi.fn(),
}));

const mockSearchChurches = vi.mocked(searchChurches);

describe('ChurchFinderModal responsive layout', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  it('renders modal with responsive rounded corners (full screen on mobile)', () => {
    const { container } = renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const modal = container.querySelector('[class*="shadow-2xl"]');
    expect(modal).not.toBeNull();
    expect(modal!.className).toContain('sm:rounded-2xl');
    // Should not have standalone rounded-2xl (only sm: prefixed)
    const classes = modal!.className.split(' ');
    expect(classes).not.toContain('rounded-2xl');
  });

  it('renders modal with responsive max-height', () => {
    const { container } = renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const modal = container.querySelector('[class*="shadow-2xl"]');
    expect(modal!.className).toContain('max-h-screen');
    expect(modal!.className).toContain('sm:max-h-[85vh]');
  });

  it('renders search form with responsive flex direction', () => {
    const { container } = renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const form = container.querySelector('form');
    expect(form).not.toBeNull();
    expect(form!.className).toContain('flex-col');
    expect(form!.className).toContain('sm:flex-row');
  });

  it('renders header with responsive text sizes', () => {
    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const heading = screen.getByText('Find a Church');
    expect(heading.className).toContain('text-xl');
    expect(heading.className).toContain('sm:text-2xl');
  });

  it('does not render when isOpen is false', () => {
    const { container } = renderWithIntl(<ChurchFinderModal isOpen={false} onClose={vi.fn()} />);
    expect(container.innerHTML).toBe('');
  });
});

describe('ChurchFinderModal functional behavior', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  const sampleChurch: Church = {
    name: 'Grace Community Church',
    address: '123 Main St',
    city: 'Springfield',
    state: 'IL',
    country: 'USA',
    website: 'https://gracechurch.org',
    phone: '+1-555-1234',
    email: 'info@gracechurch.org',
  };

  beforeEach(() => {
    mockSearchChurches.mockReset();
    defaultProps.onClose = vi.fn();
  });

  it("shows initial state with 'Enter a location to search' text", () => {
    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    expect(screen.getByText('Enter a location to search')).toBeDefined();
  });

  it('search with results renders church cards', async () => {
    mockSearchChurches.mockResolvedValue({
      churches: [sampleChurch],
      total: 1,
      location: 'Springfield',
    });

    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/City in English/);
    fireEvent.change(input, { target: { value: 'Springfield' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Grace Community Church')).toBeDefined();
      expect(screen.getByText(/123 Main St/)).toBeDefined();
      expect(screen.getByText('Website')).toBeDefined();
      expect(screen.getByText('Email')).toBeDefined();
    });
  });

  it("search with no results shows 'No churches found'", async () => {
    mockSearchChurches.mockResolvedValue({
      churches: [],
      total: 0,
      location: 'Nowhere',
    });

    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/City in English/);
    fireEvent.change(input, { target: { value: 'Nowhere' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('No churches found')).toBeDefined();
    });
  });

  it('search error shows error message', async () => {
    mockSearchChurches.mockRejectedValue(new Error('Network error'));

    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/City in English/);
    fireEvent.change(input, { target: { value: 'Test' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Failed to search for churches. Please try again.')).toBeDefined();
    });
  });

  it('shows correct plural form for found count', async () => {
    const threeChurches = [
      sampleChurch,
      { ...sampleChurch, name: 'Second Church' },
      { ...sampleChurch, name: 'Third Church' },
    ];
    mockSearchChurches.mockResolvedValue({
      churches: threeChurches,
      total: 3,
      location: 'Rome',
    });

    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/City in English/);
    fireEvent.change(input, { target: { value: 'Rome' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Found 3 churches')).toBeDefined();
    });
  });

  it('singular form for one church found', async () => {
    mockSearchChurches.mockResolvedValue({
      churches: [sampleChurch],
      total: 1,
      location: 'Rome',
    });

    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/City in English/);
    fireEvent.change(input, { target: { value: 'Rome' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Found 1 church')).toBeDefined();
    });
  });

  it('closes on Escape key', () => {
    const onClose = vi.fn();
    renderWithIntl(<ChurchFinderModal isOpen={true} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('input is disabled while loading', async () => {
    // Create a promise that we control resolution of
    let resolveSearch: (value: unknown) => void;
    mockSearchChurches.mockImplementation(
      () =>
        new Promise(resolve => {
          resolveSearch = resolve;
        })
    );

    renderWithIntl(<ChurchFinderModal {...defaultProps} />);
    const input = screen.getByPlaceholderText(/City in English/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Test' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(input.disabled).toBe(true);
    });

    // Resolve to clean up
    resolveSearch!({ churches: [], total: 0, location: 'Test' });
    await waitFor(() => {
      expect(input.disabled).toBe(false);
    });
  });
});
