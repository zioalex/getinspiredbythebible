"use client";

import { useEffect } from "react";
import { registerServiceWorker } from "@/lib/registerServiceWorker";

/** Mounts once to register the offline-shell service worker (BITB-102). */
export function ServiceWorkerRegistrar() {
  useEffect(() => {
    let cancelled = false;
    const run = () => {
      if (!cancelled) void registerServiceWorker();
    };
    const idleId = window.requestIdleCallback?.(run);
    const timeoutId =
      idleId === undefined ? window.setTimeout(run, 2000) : undefined;
    return () => {
      cancelled = true;
      if (idleId !== undefined) window.cancelIdleCallback?.(idleId);
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, []);

  return null;
}
