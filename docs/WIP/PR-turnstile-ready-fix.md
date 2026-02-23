# PR: Fix Example Sentences - Turnstile Ready Check

**Status:** In Progress
**Branch:** fix/turnstile-ready-check
**Started:** 2026-02-23

## Summary

Users clicking example sentences on page load were getting errors because the Turnstile bot protection
widget hadn't finished initializing yet. The frontend was sending API requests without a valid
Turnstile token, causing 403 Forbidden errors.

## Root Cause

The `page.tsx` component was NOT checking if Turnstile was ready (`isReady` from `useTurnstile()`)
before allowing message submission. When users clicked suggested prompt buttons immediately on page
load, the Turnstile widget hadn't generated a token yet, causing API calls to fail.

## Changes Made

**File: `frontend/src/app/[locale]/page.tsx`**

1. **Import Turnstile hook:**

   ```tsx
   import { useTurnstile } from "@/lib/turnstile";
   ```

2. **Use Turnstile state in component:**

   ```tsx
   const { isReady: turnstileReady, isEnabled: turnstileEnabled } = useTurnstile();
   ```

3. **Disable suggested prompt buttons when Turnstile is loading:**

   ```tsx
   disabled={turnstileEnabled && !turnstileReady}
   ```

4. **Disable send button when Turnstile is loading:**

   ```tsx
   disabled={isLoading || !input.trim() || (turnstileEnabled && !turnstileReady)}
   ```

5. **Add loading indicator in welcome banner:**

   ```tsx
   {turnstileEnabled && !turnstileReady && (
     <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
       <Loader2 className="w-4 h-4 animate-spin" />
       <span>Preparing secure connection...</span>
     </div>
   )}
   ```

## User Impact

**Before:** Users clicking example sentences immediately on page load would see an error (403 Forbidden from backend API).

**After:**

- Buttons are disabled (grayed out) until Turnstile widget is ready
- Loading message shows "Preparing secure connection..."
- Once Turnstile is ready (~1-2 seconds), buttons become clickable
- No more 403 errors on first interaction

## Testing Plan

- [ ] Local testing: Start frontend dev server, verify buttons are initially disabled
- [ ] Verify loading message appears briefly
- [ ] Verify buttons become enabled after ~1-2 seconds
- [ ] Click example sentence and verify it sends successfully
- [ ] Test manual input submission also respects Turnstile ready state
- [ ] Test with Turnstile disabled (`TURNSTILE_ENABLED=false`) - buttons should work immediately

## Notes

- This fix only applies when Turnstile is **enabled** (`turnstileEnabled === true`)
- When Turnstile is disabled, buttons work immediately (no wait time)
- The fix ensures UX is consistent: users can't send messages until the system is ready to handle them

## Tasks

- [x] Identify root cause
- [x] Implement fix in page.tsx
- [x] Add user feedback (loading indicator)
- [ ] Test locally
- [ ] Create branch and commit
- [ ] Run pre-commit hooks
- [ ] Push and create PR
- [ ] Verify CI passes
- [ ] Deploy to production
