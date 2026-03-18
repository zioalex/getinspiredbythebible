'use client';

import { TurnstileProvider } from '@/lib/turnstile';
import { useEffect } from 'react';
import { setTurnstileToken, setOnTokenConsumed } from '@/lib/api';
import { useTurnstile } from '@/lib/turnstile';

function TurnstileTokenSync({ children }: { children: React.ReactNode }) {
  const { token, refreshToken } = useTurnstile();

  // Sync token to API client whenever it changes
  useEffect(() => {
    setTurnstileToken(token);
  }, [token]);

  // Register refresh callback so the API client can request a new token after each use
  useEffect(() => {
    setOnTokenConsumed(refreshToken);
    return () => setOnTokenConsumed(null);
  }, [refreshToken]);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <TurnstileProvider>
      <TurnstileTokenSync>{children}</TurnstileTokenSync>
    </TurnstileProvider>
  );
}
