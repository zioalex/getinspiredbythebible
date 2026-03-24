"use client";

import { TurnstileProvider } from "@/lib/turnstile";
import { useEffect, useState } from "react";
import { setTurnstileToken, setOnTokenConsumed } from "@/lib/api";
import { useTurnstile } from "@/lib/turnstile";
import { SplashScreen } from "@/components/SplashScreen";

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
  const [splashDone, setSplashDone] = useState(false);

  return (
    <TurnstileProvider>
      <TurnstileTokenSync>
        {!splashDone && <SplashScreen onComplete={() => setSplashDone(true)} />}
        {children}
      </TurnstileTokenSync>
    </TurnstileProvider>
  );
}
