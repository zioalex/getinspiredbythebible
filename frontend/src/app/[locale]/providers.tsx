"use client";

import { TurnstileProvider } from "@/lib/turnstile";
import { useEffect, useState } from "react";
import {
  setTurnstileToken,
  setOnTokenConsumed,
  setTurnstileAwaiter,
} from "@/lib/api";
import { useTurnstile } from "@/lib/turnstile";
import { SplashScreen } from "@/components/SplashScreen";

function hasSplashCookie(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie
    .split(";")
    .some((c) => c.trim().startsWith("splash_seen=1"));
}

function setSplashCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = "splash_seen=1; path=/; max-age=31536000; SameSite=Lax";
}

function TurnstileTokenSync({ children }: { children: React.ReactNode }) {
  const { token, refreshToken, awaitToken } = useTurnstile();

  // Sync token to API client whenever it changes
  useEffect(() => {
    setTurnstileToken(token);
  }, [token]);

  // Register refresh callback so the API client can request a new token after each use
  useEffect(() => {
    setOnTokenConsumed(refreshToken);
    return () => setOnTokenConsumed(null);
  }, [refreshToken]);

  // Register awaiter so POST helpers in api.ts can briefly wait for a token
  // before firing requests (covers the "first send before /config resolves" race).
  useEffect(() => {
    setTurnstileAwaiter(awaitToken);
    return () => setTurnstileAwaiter(null);
  }, [awaitToken]);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [splashDone, setSplashDone] = useState(() => hasSplashCookie());

  return (
    <TurnstileProvider>
      <TurnstileTokenSync>
        {!splashDone && (
          <SplashScreen
            onComplete={() => {
              setSplashCookie();
              setSplashDone(true);
            }}
          />
        )}
        {children}
      </TurnstileTokenSync>
    </TurnstileProvider>
  );
}
