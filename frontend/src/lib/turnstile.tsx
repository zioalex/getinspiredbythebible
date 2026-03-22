"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";

interface TurnstileContextValue {
  token: string | null;
  isReady: boolean;
  isEnabled: boolean;
  refreshToken: () => void;
}

const TurnstileContext = createContext<TurnstileContextValue>({
  token: null,
  isReady: false,
  isEnabled: false,
  refreshToken: () => {},
});

export function useTurnstile() {
  return useContext(TurnstileContext);
}

interface TurnstileProviderProps {
  children: React.ReactNode;
  apiUrl?: string;
}

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: string | HTMLElement,
        options: {
          sitekey: string;
          callback?: (token: string) => void;
          "error-callback"?: (error: unknown) => void;
          "expired-callback"?: () => void;
          theme?: "light" | "dark" | "auto";
          size?: "normal" | "compact" | "invisible";
        },
      ) => string;
      reset: (widgetId: string) => void;
      remove: (widgetId: string) => void;
    };
  }
}

export function TurnstileProvider({
  children,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
}: TurnstileProviderProps) {
  const [token, setToken] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [isEnabled, setIsEnabled] = useState(false);
  const [siteKey, setSiteKey] = useState<string | null>(null);
  const widgetIdRef = useRef<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const retryCountRef = useRef(0);
  const MAX_RETRIES = 3;

  // Fetch config to get Turnstile settings
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch(`${apiUrl}/config`);
        if (response.ok) {
          const config = await response.json();
          if (
            config.security?.turnstile_enabled &&
            config.security?.turnstile_site_key
          ) {
            setIsEnabled(true);
            setSiteKey(config.security.turnstile_site_key);
          } else {
            // Turnstile not enabled, mark as ready without it
            setIsReady(true);
          }
        } else {
          // Config fetch failed, proceed without Turnstile
          setIsReady(true);
        }
      } catch (error) {
        console.warn("Failed to fetch config for Turnstile:", error);
        // Proceed without Turnstile on error
        setIsReady(true);
      }
    };

    fetchConfig();
  }, [apiUrl]);

  // Define refreshToken first so it can be used in renderWidget
  const refreshToken = useCallback(() => {
    if (widgetIdRef.current && window.turnstile) {
      setToken(null);
      setIsReady(false); // ADD THIS LINE
      window.turnstile.reset(widgetIdRef.current);
    }
  }, []);

  // renderWidget depends on refreshToken
  const renderWidget = useCallback(() => {
    if (!window.turnstile || !siteKey || !containerRef.current) {
      // Retry after a short delay if not ready
      setTimeout(renderWidget, 100);
      return;
    }

    // Remove existing widget if any
    if (widgetIdRef.current) {
      window.turnstile.remove(widgetIdRef.current);
    }

    try {
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        callback: (newToken: string) => {
          retryCountRef.current = 0;
          setToken(newToken);
          setIsReady(true);
        },
        "error-callback": (error: unknown) => {
          console.warn("Turnstile challenge error:", error);
          if (retryCountRef.current < MAX_RETRIES) {
            retryCountRef.current += 1;
            const delay = 1000 * retryCountRef.current;
            console.warn(
              `Retrying Turnstile (${retryCountRef.current}/${MAX_RETRIES}) in ${delay}ms`,
            );
            setTimeout(() => refreshToken(), delay);
          } else {
            console.error(
              "Turnstile failed after retries, proceeding without token",
            );
            setIsReady(true);
          }
        },
        "expired-callback": () => {
          setToken(null);
          // Auto-refresh on expiry
          refreshToken();
        },
        size: "invisible",
        theme: "light",
      });
    } catch (error) {
      console.error("Failed to render Turnstile widget:", error);
      setIsReady(true);
    }
  }, [siteKey, refreshToken]);

  // Load Turnstile script when we have a site key
  useEffect(() => {
    if (!siteKey) return;

    // Check if script is already loaded
    if (window.turnstile) {
      renderWidget();
      return;
    }

    // Load the Turnstile script
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
    script.async = true;
    script.onload = () => {
      renderWidget();
    };
    script.onerror = () => {
      console.error("Failed to load Turnstile script");
      setIsReady(true); // Proceed without Turnstile
    };

    document.head.appendChild(script);

    return () => {
      // Cleanup widget on unmount
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
      }
    };
  }, [siteKey, renderWidget]);

  return (
    <TurnstileContext.Provider
      value={{ token, isReady, isEnabled, refreshToken }}
    >
      {/* Hidden container for the invisible Turnstile widget */}
      {isEnabled && (
        <div
          ref={containerRef}
          style={{
            position: "fixed",
            bottom: 0,
            right: 0,
            visibility: "hidden",
          }}
          aria-hidden="true"
        />
      )}
      {children}
    </TurnstileContext.Provider>
  );
}
