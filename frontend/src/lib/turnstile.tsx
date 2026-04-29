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
  configLoaded: boolean;
  refreshToken: () => void;
  // Resolves with the current token (or null if Turnstile is disabled / unavailable).
  // Waits up to timeoutMs for config to load and a token to arrive; on timeout
  // returns whatever is currently cached (typically null) so the caller can
  // fail open and let the backend respond.
  awaitToken: (timeoutMs?: number) => Promise<string | null>;
}

const TurnstileContext = createContext<TurnstileContextValue>({
  token: null,
  isReady: false,
  isEnabled: false,
  configLoaded: false,
  refreshToken: () => {},
  awaitToken: async () => null,
});

export function useTurnstile() {
  return useContext(TurnstileContext);
}

interface TurnstileProviderProps {
  children: React.ReactNode;
  apiUrl?: string;
  // Build-time site key. When provided (or when NEXT_PUBLIC_TURNSTILE_SITE_KEY
  // is set at build time), the provider skips the runtime /config round-trip
  // and starts the Turnstile widget immediately. Pass an empty string to
  // explicitly disable Turnstile without falling through to /config.
  siteKeyOverride?: string;
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

function reportTurnstileError(type: string, detail: string, apiUrl: string) {
  fetch(`${apiUrl}/api/v1/client-errors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: `turnstile_${type}`, detail }),
  }).catch(() => {}); // fire-and-forget
}

export function TurnstileProvider({
  children,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  siteKeyOverride,
}: TurnstileProviderProps) {
  // Build-time site key takes precedence over the runtime /config fetch.
  // An empty string is treated as "explicitly disabled at build time" so the
  // /config round-trip is also skipped.
  const buildTimeSiteKey =
    siteKeyOverride ?? process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  const hasBuildTimeConfig = buildTimeSiteKey !== undefined;
  const buildTimeEnabled = !!buildTimeSiteKey;

  const [token, setToken] = useState<string | null>(null);
  // When Turnstile is disabled at build time, we're already "ready" — no
  // widget needs to render and no /config response is needed.
  const [isReady, setIsReady] = useState(
    hasBuildTimeConfig && !buildTimeEnabled,
  );
  const [isEnabled, setIsEnabled] = useState(buildTimeEnabled);
  const [configLoaded, setConfigLoaded] = useState(hasBuildTimeConfig);
  const [siteKey, setSiteKey] = useState<string | null>(
    buildTimeEnabled ? (buildTimeSiteKey as string) : null,
  );
  const widgetIdRef = useRef<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const retryCountRef = useRef(0);
  const MAX_RETRIES = 3;

  // Refs mirror state so awaitToken (called outside React) can read live values
  // and notify any pending waiters whenever the relevant state changes.
  const tokenRef = useRef<string | null>(null);
  const isEnabledRef = useRef(false);
  const configLoadedRef = useRef(false);
  const waitersRef = useRef<Set<() => void>>(new Set());

  const notifyWaiters = useCallback(() => {
    waitersRef.current.forEach((cb) => cb());
  }, []);

  useEffect(() => {
    tokenRef.current = token;
    notifyWaiters();
  }, [token, notifyWaiters]);
  useEffect(() => {
    isEnabledRef.current = isEnabled;
    notifyWaiters();
  }, [isEnabled, notifyWaiters]);
  useEffect(() => {
    configLoadedRef.current = configLoaded;
    notifyWaiters();
  }, [configLoaded, notifyWaiters]);

  const awaitToken = useCallback(
    (timeoutMs: number = 5000): Promise<string | null> => {
      return new Promise((resolve) => {
        // Returns the token (or null) when we know enough to proceed,
        // otherwise undefined to keep waiting.
        const peek = (): string | null | undefined => {
          if (configLoadedRef.current && !isEnabledRef.current) return null;
          if (tokenRef.current) return tokenRef.current;
          return undefined;
        };

        const immediate = peek();
        if (immediate !== undefined) {
          resolve(immediate);
          return;
        }

        const onChange = () => {
          const v = peek();
          if (v !== undefined) {
            cleanup();
            resolve(v);
          }
        };
        const onTimeout = () => {
          cleanup();
          resolve(tokenRef.current);
        };
        const handle = setTimeout(onTimeout, timeoutMs);
        const cleanup = () => {
          clearTimeout(handle);
          waitersRef.current.delete(onChange);
        };
        waitersRef.current.add(onChange);
      });
    },
    [],
  );

  // Fetch config to get Turnstile settings (skipped when build-time config is set)
  useEffect(() => {
    if (hasBuildTimeConfig) {
      return;
    }
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
        reportTurnstileError("config_fetch", String(error), apiUrl);
        // Proceed without Turnstile on error
        setIsReady(true);
      } finally {
        setConfigLoaded(true);
      }
    };

    fetchConfig();
  }, [apiUrl, hasBuildTimeConfig]);

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
            reportTurnstileError(
              "challenge_failed",
              "max retries exceeded",
              apiUrl,
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
      reportTurnstileError("render_failed", String(error), apiUrl);
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
      reportTurnstileError(
        "script_load",
        "failed to load turnstile script",
        apiUrl,
      );
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
      value={{
        token,
        isReady,
        isEnabled,
        configLoaded,
        refreshToken,
        awaitToken,
      }}
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
