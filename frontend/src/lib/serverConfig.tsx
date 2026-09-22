"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { MAX_MESSAGE_LENGTH, MAX_SESSION_REQUESTS } from "@/lib/api";

// BITB-075/BITB-118: publishes server-controlled chat configuration (the
// effective message-length limit and the per-session message cap) to the
// client tree. Deliberately does its OWN unconditional /config fetch rather
// than reusing/extending TurnstileProvider: that provider skips its /config
// round-trip whenever a build-time Turnstile site key is present, which is
// always true in production (baked in via frontend/Dockerfile), so
// piggybacking on it would make this feature silently dead in prod. Fails
// open on any error and keeps the compiled-in fallback, matching the rest of
// the app's config-fetch style.
interface ServerConfigValue {
  maxMessageLength: number;
  sessionMaxRequests: number;
}

const ServerConfigContext = createContext<ServerConfigValue>({
  maxMessageLength: MAX_MESSAGE_LENGTH,
  sessionMaxRequests: MAX_SESSION_REQUESTS,
});

export function useServerConfig(): ServerConfigValue {
  return useContext(ServerConfigContext);
}

interface ServerConfigProviderProps {
  children: React.ReactNode;
  apiUrl?: string;
}

export function ServerConfigProvider({
  children,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
}: ServerConfigProviderProps) {
  const [maxMessageLength, setMaxMessageLength] =
    useState<number>(MAX_MESSAGE_LENGTH);
  const [sessionMaxRequests, setSessionMaxRequests] =
    useState<number>(MAX_SESSION_REQUESTS);

  useEffect(() => {
    let cancelled = false;

    const fetchConfig = async () => {
      try {
        const response = await fetch(`${apiUrl}/config`);
        if (!response.ok) return;
        const config = await response.json();
        const value = config?.chat?.max_message_length;
        if (!cancelled && Number.isInteger(value) && value > 0) {
          setMaxMessageLength(value);
        }
        const sessionLimit = config?.chat?.session_max_requests;
        if (!cancelled && Number.isInteger(sessionLimit) && sessionLimit > 0) {
          setSessionMaxRequests(sessionLimit);
        }
      } catch {
        // Fail open: keep the compiled-in fallback.
      }
    };

    fetchConfig();

    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  return (
    <ServerConfigContext.Provider
      value={{ maxMessageLength, sessionMaxRequests }}
    >
      {children}
    </ServerConfigContext.Provider>
  );
}
