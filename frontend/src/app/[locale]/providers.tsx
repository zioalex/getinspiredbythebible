"use client";

import { TurnstileProvider } from "@/lib/turnstile";
import { useEffect, useState } from "react";
import {
  setTurnstileToken,
  setOnTokenConsumed,
  setTurnstileAwaiter,
} from "@/lib/api";
import { useTurnstile } from "@/lib/turnstile";
import { reportClientError } from "@/lib/clientErrorReporter";
import { SplashScreen } from "@/components/SplashScreen";
import AboutIntroModal from "@/components/AboutIntroModal";
import {
  AboutIntroGateProvider,
  type AboutIntroGateState,
} from "@/lib/aboutIntroGate";

// BITB-077: bump only on a deliberate re-announcement, not on every release.
const ABOUT_INTRO_KEY = "vq:aboutIntroSeen";
const ABOUT_INTRO_VERSION = "1";

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

  // Global client-error reporting (BITB-066): surface uncaught JS errors and
  // unhandled promise rejections to the backend so a browser-side outage is
  // observable. Registered once for the app lifetime.
  useEffect(() => {
    const onError = (e: ErrorEvent) => {
      const detail =
        e.error?.stack || e.message || String(e.error ?? "unknown");
      reportClientError("window_onerror", detail);
    };
    const onRejection = (e: PromiseRejectionEvent) => {
      const reason = e.reason;
      const detail =
        (reason instanceof Error
          ? reason.stack || reason.message
          : String(reason)) || "unknown";
      reportClientError("unhandledrejection", detail);
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  // Seed deterministically to `false` on BOTH server and client so the first
  // client render matches the server-rendered HTML (no hydration mismatch).
  // The cookie is a client-only value, so read it after mount in an effect:
  // for a returning visitor this flips splashDone to true immediately
  // post-hydration, skipping the splash without diverging the initial tree.
  // See BITB-069.
  const [splashDone, setSplashDone] = useState(false);

  // BITB-077: whether to render the intro modal, and the gate WhatsNewModal
  // reads to know whether it's safe to show itself this load. Both start
  // "unknown" and are resolved together once splashDone flips true — never
  // read from localStorage before then, so there's no race with the modal
  // that mounts deep inside `children`.
  const [showAboutIntro, setShowAboutIntro] = useState(false);
  const [introGate, setIntroGate] = useState<AboutIntroGateState>("pending");

  useEffect(() => {
    if (hasSplashCookie()) {
      setSplashDone(true);
    }
  }, []);

  useEffect(() => {
    if (!splashDone) return;
    const seen = localStorage.getItem(ABOUT_INTRO_KEY);
    if (seen === null || seen < ABOUT_INTRO_VERSION) {
      setShowAboutIntro(true);
      setIntroGate("show-intro");
    } else {
      setIntroGate("clear");
    }
  }, [splashDone]);

  function dismissAboutIntro() {
    localStorage.setItem(ABOUT_INTRO_KEY, ABOUT_INTRO_VERSION);
    setShowAboutIntro(false);
    // introGate deliberately stays "show-intro" — WhatsNewModal defers to
    // the next visit rather than appearing right after this dismissal.
  }

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
        <AboutIntroGateProvider value={introGate}>
          {children}
        </AboutIntroGateProvider>
        {splashDone && showAboutIntro && (
          <AboutIntroModal onDismiss={dismissAboutIntro} />
        )}
      </TurnstileTokenSync>
    </TurnstileProvider>
  );
}
