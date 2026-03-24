"use client";

import { TurnstileProvider } from "@/lib/turnstile";
import { useEffect, useState } from "react";
import { setTurnstileToken, setOnTokenConsumed } from "@/lib/api";
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
