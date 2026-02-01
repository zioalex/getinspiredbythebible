"use client";

import { TurnstileProvider } from "@/lib/turnstile";
import { useEffect } from "react";
import { setTurnstileToken } from "@/lib/api";
import { useTurnstile } from "@/lib/turnstile";

function TurnstileTokenSync({ children }: { children: React.ReactNode }) {
  const { token } = useTurnstile();

  // Sync token to API client whenever it changes
  useEffect(() => {
    setTurnstileToken(token);
  }, [token]);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <TurnstileProvider>
      <TurnstileTokenSync>{children}</TurnstileTokenSync>
    </TurnstileProvider>
  );
}
