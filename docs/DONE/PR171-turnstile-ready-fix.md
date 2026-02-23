# PR: Fix Example Sentences - Turnstile Ready Check

**Status:** ✅ Code Complete - Awaiting Human Approval & Merge
**Branch:** fix/turnstile-ready-check
**PR:** #171 - <https://github.com/zioalex/getinspiredbythebible/pull/171>
**Started:** 2026-02-23
**Completed:** 2026-02-23

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

## Testing

### Unit Tests (Vitest) ✅

**File:** `frontend/src/app/[locale]/page.test.tsx`

Added 9 new tests covering Turnstile security:

- ✅ Suggested prompts disabled when Turnstile loading
- ✅ Send button disabled when Turnstile loading
- ✅ Loading indicator shows "Preparing secure connection..."
- ✅ All buttons enabled when Turnstile ready
- ✅ Buttons work immediately when Turnstile disabled

**Results:** 196/196 tests passing

### E2E Tests (Python + httpx) ✅

**File:** `api/tests/e2e/test_frontend_e2e.py`

Added 5 new tests for suggested prompts:

- ✅ Prompts section exists on page
- ✅ Minimum number of prompts rendered
- ✅ Prompts are translatable (i18n)
- ✅ Prompts are clickable buttons
- ✅ No duplicate prompts

**Results:** 37/37 tests passing

### CI Status ✅

- ✅ Backend tests (pytest)
- ✅ Frontend tests (Vitest)
- ✅ Functional tests (E2E smoke tests)
- ✅ Pre-commit hooks
- ✅ Type checks
- ✅ Linting

## Notes

- This fix only applies when Turnstile is **enabled** (`turnstileEnabled === true`)
- When Turnstile is disabled, buttons work immediately (no wait time)
- The fix ensures UX is consistent: users can't send messages until the system is ready to handle them

## Tasks

- [x] Identify root cause
- [x] Implement fix in page.tsx
- [x] Add user feedback (loading indicator)
- [x] Add unit tests (9 new tests in page.test.tsx)
- [x] Add E2E tests (5 new tests in test_frontend_e2e.py)
- [x] Create branch and commit
- [x] Run pre-commit hooks
- [x] Push and create PR
- [x] Verify CI passes (all green ✅)
- [ ] **BLOCKED:** Awaiting human approval (branch protection requires 1 approval)
- [ ] Merge PR
- [ ] Verify production deployment
- [ ] Monitor for 403 errors (should be zero)
- [ ] Move tracking doc to docs/DONE/
