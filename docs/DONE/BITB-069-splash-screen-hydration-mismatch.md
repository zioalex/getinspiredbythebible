# BITB-069: Splash-Screen Cookie Check Causes SSR/CSR Hydration Mismatch

**Status:** ✅ Done (PR #TBD)
**Priority:** P2 (Medium) — cosmetic/console-only today (React recovers by regenerating the tree
client-side), but it's a real SSR/CSR divergence, not just noise, and the failure mode gets worse
if anything downstream ever depends on first-paint DOM matching (e.g. a future analytics/observer
hook, or stricter React versions that hard-fail instead of patching over mismatches).
**Size:** S (< 4 hrs)
**Created:** 2026-07-16

## User Story

As a returning visitor, I want the page to render consistently between the server-sent HTML and
the client's first paint, so that the browser console stays clean and the app doesn't silently
discard and re-render the entire tree on every load.

## Problem / Motivation

Found while manually testing PR #840 locally (`docker-up-local-prod`) — unrelated to that PR, which
touches zero frontend files. On load, the browser console showed:

```
Uncaught Error: Hydration failed because the server rendered HTML didn't match the client.
```

The React diff pointed at the root layout tree, one render showing the splash overlay:

```
className="fixed inset-0 z-50"        (+ data-splash-phrase="true", lang="en", background style)
```

and the other showing the main app shell instead:

```
className="min-h-screen bg-gradient-to-b from-primary-50 to-white flex flex-col overflow..."
```

**Root cause:** `frontend/src/app/[locale]/providers.tsx:76`

```tsx
const [splashDone, setSplashDone] = useState(() => hasSplashCookie());
```

`hasSplashCookie()` (`providers.tsx:14-19`) reads `document.cookie` for `splash_seen=1`, guarded by
`typeof document === "undefined"` so it returns `false` during SSR (no `document` on the server).
That guard is correct, but the consequence is the bug: the **server** always renders with
`splashDone = false` (splash shown), while the **client's** lazy `useState` initializer runs for
real on hydration and can see a `splash_seen=1` cookie set by a *previous* visit — giving
`splashDone = true` (splash skipped) on that very first client render. Server and client render
different trees on the same pass, which is exactly what triggers a hydration-mismatch error. This
only reproduces for **returning visitors** (cookie already set) — a first-time visitor has no
cookie yet, so both server and client agree on `splashDone = false` and there's no mismatch, which
is likely why this wasn't caught earlier.

React recovers by discarding the server-rendered tree and re-rendering fully client-side (per the
error text), so the app still functions — but every returning visitor pays for a full client
re-render on first paint, and the console error is a real signal of the underlying issue.

## Suggested Fix

Don't gate the initial render on a client-only value. Standard pattern: keep the `useState`
initializer deterministic (`false`) on both server and client, and apply the cookie check in a
`useEffect` after mount, e.g.:

```tsx
const [splashDone, setSplashDone] = useState(false);

useEffect(() => {
  if (hasSplashCookie()) setSplashDone(true);
}, []);
```

This makes the server's and the client's *first* render agree (splash shown), then the effect
flips it immediately post-hydration for returning visitors — no mismatch, and the visible splash
flash for returning visitors should be sub-frame since the effect fires before paint settles.
Alternative: read the cookie server-side (Next.js `cookies()` in a Server Component higher up) and
pass `splashSeen` down as a prop, avoiding the client-only read entirely — more invasive since
`Providers` and its children are already `"use client"`.

## Acceptance Criteria

- [x] No hydration-mismatch error/warning on load for a returning visitor (cookie already set)
- [x] First-time visitor still sees the full splash screen unchanged
- [x] Returning visitor doesn't see a visible splash flash before it's skipped
- [x] Manual verification: load once (first-time splash), reload (returning visitor, no console
      error)
