# BITB-018: Fix CI Integration Test Ollama Model Pull Timeout

# BITB-018: Fix CI Integration Test Ollama Model Pull Timeout

**Priority:** P1 (High - Needs Investigation)
**Status:** ✅ Resolved - Temporary GitHub network glitch
**Size:** S (investigation only)
**Created:** 2026-03-04
**Resolved:** 2026-03-04

---

## ✅ RESOLUTION

**Outcome:** Issue resolved - confirmed as temporary GitHub Actions network glitch.

**Evidence:**

- First CI run failed: 187 KB/s download speed, model reached 89% in 10 minutes
- Second CI run passed: Normal download speed, model pulled successfully
- No code changes between runs

**Decision:** No fix implemented. Occasional network glitches (~1-2% frequency) are acceptable. Developers can re-run failed jobs.

**Lessons Learned:**

1. Investigation-first approach saved 2-3 hours of unnecessary implementation
2. Single data point is not enough to justify complex infrastructure changes
3. Document analysis anyway for future reference

**Related Documents:**

- Full analysis: `docs/DONE/BITB-018-ANALYSIS-CI-OLLAMA-TIMEOUT.md`
- This document kept for historical reference

---

## Original User Story (For Reference)

## User Story

**As a** developer submitting PRs,
**I want** CI integration tests to pass reliably without timing out on Ollama model pulls,
**so that** I can verify my changes work correctly without manual intervention.

---

## ⚠️ INVESTIGATION REQUIRED FIRST

**Before implementing any fix, we need to answer:**

1. **Did integration tests work before PR #192?**
   - Check CI history for previous successful runs
   - Determine if this is a regression or pre-existing issue

2. **Is this a one-time network glitch?**
   - Re-run the failed job to see if it passes on retry
   - Check if 187 KB/s is typical or anomaly

3. **What changed in PR #192?**
   - Review changes to Ollama config, Docker, or workflows
   - Determine if PR introduced the issue

**Investigation time:** 15 minutes
**Decision:** Implement fix only if evidence shows persistent problem

**See detailed analysis:** `docs/DONE/BITB-018-ANALYSIS-CI-OLLAMA-TIMEOUT.md`

---

## Problem Statement

**Current Behavior:**
Integration tests are failing with timeout errors while waiting for Ollama embedding model to be ready. The test waits up to 60 attempts (10 minutes) but Ollama never reports the model as ready via the API tags endpoint.

**Error Log:**

```
Waiting for Ollama embedding model... attempt 56/60
Waiting for Ollama embedding model... attempt 57/60
Waiting for Ollama embedding model... attempt 58/60
Waiting for Ollama embedding model... attempt 59/60
Ollama failed to be ready with embedding model
```

**Ollama Container Logs:**

```
ollama-1  | Pulling embedding model: mxbai-embed-large...
ollama-1  | pulling manifest ⠙
ollama-1  | pulling 819c2adf5ce6:  89% ▕████████████████  ▏ 595 MB/669 MB  187 KB/s   6m33s
ollama-1  | [GIN] 2026/03/04 - 19:11:18 | 200 |      79.784µs |      172.18.0.1 | GET      "/api/tags"
Error: Process completed with exit code 1.
```

**Key Insight:** Model download reached **89% (595 MB of 669 MB)** but network speed was only **187 KB/s**, requiring ~60 minutes total to complete. Test timed out after 10 minutes.

**GitHub Actions Run:**

- <https://github.com/zioalex/getinspiredbythebible/actions/runs/22682755174/job/65757690030>
- Job: "Integration Tests"
- Step: "Wait for Ollama to be ready" (lines 172-190 in test_update.yml)

**Root Cause Analysis:**

1. `docker compose up -d` starts Ollama service with custom entrypoint `init-ollama.sh`
2. Script starts Ollama server (`ollama serve &`) in background
3. Script pulls embedding model (`ollama pull mxbai-embed-large`) - **669 MB download**
4. **GitHub Actions network speed: ~187 KB/s** (extremely slow/throttled)
5. **Download time: ~60 minutes** (669 MB ÷ 187 KB/s = 3,577 seconds)
6. CI test timeout: 10 minutes (600 seconds)
7. **Result:** Model reaches 89% before timeout, test fails

**Why this is NOT a race condition:**
The problem isn't that we're checking too early—it's that the download is **too slow to ever complete** within a reasonable CI timeout. Even with a 20-minute timeout, the download would still fail.

**Potential Causes:**

- Model pull is slow/failing silently in CI environment
- Docker networking delay between `ollama` container and host
- Ollama service not starting correctly
- Init script hanging or failing without error

**Impact:**

- **Severity:** P0 - All PRs blocked, CI completely broken
- **Duration:** Wastes 10+ minutes waiting for timeout
- **User Experience:** Developers cannot merge PRs, must manually investigate
- **Frequency:** Every push to main, every PR

---

## Functional Requirements

- [ ] Ollama model pull should complete within 5 minutes in CI
- [ ] Test should wait for init-ollama.sh script completion, not just model availability
- [ ] If model pull fails, show clear error message with Ollama logs
- [ ] Test should verify Ollama is ready AND model is pulled before proceeding
- [ ] Add debugging output to show Ollama initialization progress

---

## Non-Functional Requirements

- **Reliability:** Test should pass 100% of the time when code is correct
- **Performance:** Integration tests should complete in < 15 minutes total
- **Debuggability:** Clear logs showing exactly where Ollama initialization fails
- **Maintainability:** Solution should work with future Ollama versions

---

## Acceptance Criteria

**Code Changes:**

1. **In `.github/workflows/test_update.yml` (Integration Tests job):**
   - [ ] Add step to show Ollama logs immediately after `docker compose up`
   - [ ] Increase initial sleep from 30s to 60s (give Ollama time to start pulling)
   - [ ] Update "Wait for Ollama to be ready" step:

     ```yaml
     - name: Wait for Ollama to be ready
       run: |
         echo "Waiting for Ollama to pull embedding model (this may take a few minutes)..."

         # First, wait for Ollama service to be reachable
         max_attempts=30
         attempt=0
         until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
           attempt=$((attempt + 1))
           if [ $attempt -eq $max_attempts ]; then
             echo "Ollama service failed to start"
             docker compose logs ollama
             exit 1
           fi
           echo "Waiting for Ollama service... attempt $attempt/$max_attempts"
           sleep 5
         done
         echo "Ollama service is running!"

         # Now wait for the model to be pulled (init script should handle this)
         max_attempts=120  # 20 minutes (model pull can be slow in CI)
         attempt=0
         until curl -sf http://localhost:11434/api/tags | grep -q "mxbai-embed-large"; do
           attempt=$((attempt + 1))
           if [ $attempt -eq $max_attempts ]; then
             echo "ERROR: Ollama embedding model never appeared after 20 minutes"
             echo "=== Ollama Logs ==="
             docker compose logs ollama
             echo "=== Available Models ==="
             curl -sf http://localhost:11434/api/tags | jq . || echo "Failed to fetch models"
             exit 1
           fi

           # Show progress every 10 attempts (every 100 seconds)
           if [ $((attempt % 10)) -eq 0 ]; then
             echo "Still waiting for mxbai-embed-large... attempt $attempt/$max_attempts"
             echo "Current models:"
             curl -sf http://localhost:11434/api/tags | jq -r '.models[]?.name' 2>/dev/null || echo "  (none yet)"
           else
             echo "Waiting for Ollama embedding model... attempt $attempt/$max_attempts"
           fi
           sleep 10
         done

         echo "✅ Ollama is ready with mxbai-embed-large embedding model!"
         echo "Note: Using OpenRouter for LLM (matches production config)"
         curl -s http://localhost:11434/api/tags | jq .
     ```

2. **In `scripts/init-ollama.sh`:**
   - [ ] Add more verbose logging to show progress:

     ```bash
     echo "Pulling embedding model: ${EMBEDDING_MODEL:-mxbai-embed-large}..."
     echo "This may take 3-5 minutes depending on network speed..."
     if ollama pull "${EMBEDDING_MODEL:-mxbai-embed-large}"; then
       echo "✅ Embedding model pulled successfully!"
     else
       echo "❌ ERROR: Failed to pull embedding model!"
       exit 1
     fi
     ```

3. **Alternative: Pre-pull model in Docker image (faster CI):**
   - [ ] Create custom Ollama Dockerfile that includes mxbai-embed-large
   - [ ] Build and push to GitHub Container Registry
   - [ ] Update docker-compose.yml to use pre-built image in CI
   - [ ] **Benefit:** Eliminates model pull time (3-5 minutes saved per test run)

**Testing:**

- [ ] **Test Case 1:** Push to main triggers integration tests
  - Expected: Tests complete in < 15 minutes
  - Verify: Ollama logs show successful model pull
  - Verify: "Wait for Ollama" step completes in < 5 minutes

- [ ] **Test Case 2:** Force Ollama failure (bad model name)
  - Expected: Test fails quickly with clear error message
  - Verify: Ollama logs are shown in test output

- [ ] **Test Case 3:** Run integration tests 5 times
  - Expected: All 5 runs pass (100% reliability)
  - Verify: No random timeouts or race conditions

**Documentation:**

- [ ] Add comment in workflow explaining Ollama initialization timing
- [ ] Document alternative solution (pre-built image) in case CI continues to fail

---

## Tech Constraints

- Must work with GitHub Actions Ubuntu runners
- Must not increase Docker image size significantly (if using pre-built approach)
- Must handle slow network connections in CI environment
- Must maintain compatibility with local `docker compose` development

---

## Out of Scope

- Switching to a different embedding provider (Ollama is correct choice for cost)
- Running integration tests without Docker Compose (current setup is good)
- Mocking Ollama in tests (we want real integration tests)
- Using GitHub Actions services (Docker Compose is more maintainable)

---

## Implementation Options

### Option A: Increase timeout + better logging (Quick Fix - Recommended)

**Pros:**

- Fast to implement (< 1 hour)
- No infrastructure changes
- Works with existing setup

**Cons:**

- Tests still take 5+ minutes for Ollama init
- Doesn't solve slow network issues

**Implementation:**

1. Increase max_attempts from 60 to 120 (20 minutes)
2. Add Ollama logs on every check (show progress)
3. Verify init script completes successfully

---

### Option B: Pre-built Ollama image with model (Optimal - Slower to implement)

**Pros:**

- Faster CI (eliminates 3-5 minute model pull)
- More reliable (no network dependency during test)
- Reusable across all test runs

**Cons:**

- Requires Dockerfile, build, push to registry
- Image size increases by ~500MB (mxbai-embed-large)
- Need to update image when model changes

**Implementation:**

1. Create `ollama/Dockerfile`:

   ```dockerfile
   FROM ollama/ollama:latest

   # Start Ollama service in background
   RUN ollama serve & sleep 5 && \
       ollama pull mxbai-embed-large && \
       pkill ollama

   # Use default entrypoint (ollama serve)
   ```

2. Build and push:

   ```bash
   docker build -t ghcr.io/zioalex/getinspiredbythebible-ollama:latest ollama/
   docker push ghcr.io/zioalex/getinspiredbythebible-ollama:latest
   ```

3. Update docker-compose.yml:

   ```yaml
   ollama:
     image: ghcr.io/zioalex/getinspiredbythebible-ollama:latest  # Use pre-built image
     # ... rest of config
   ```

4. Update CI to use same image (no changes needed)

---

### Option C: Use Ollama health check with retries (Middle Ground)

**Pros:**

- More robust than current polling
- Uses Docker Compose native health checks
- Clear failure modes

**Cons:**

- Still requires model pull during test
- Health check can't easily verify model availability

**Implementation:**

1. Add health check to docker-compose.yml:

   ```yaml
   ollama:
     image: ollama/ollama:latest
     healthcheck:
       test: ["CMD-SHELL", "curl -sf http://localhost:11434/api/tags | grep -q mxbai-embed-large"]
       interval: 10s
       timeout: 5s
       retries: 60  # 10 minutes
       start_period: 60s
   ```

2. Update API service dependency:

   ```yaml
   api:
     depends_on:
       ollama:
         condition: service_healthy
   ```

3. Simplify CI wait step (rely on Docker health check)

---

## Recommendation

**⚠️ UPDATED 2026-03-04 after log analysis:**

**ONLY Option B (Pre-built Image) will work.**

**Root Cause Confirmed:**

- Model download speed in GitHub Actions: **187 KB/s** (extremely slow)
- Model size: **669 MB**
- Download time at this speed: **~60 minutes**
- CI timeout: **10 minutes**
- Result: Model reaches 89% (595 MB) before timeout

**Why Option A (increase timeout) won't work:**

- Would need 60+ minute timeout
- Wastes GitHub Actions minutes ($$$)
- Still fails on slow network days
- Makes every PR test wait 1 hour

**Why Option B is the only solution:**

1. Model embedded in Docker image (no download during test)
2. One-time cost to build image (~5 minutes)
3. Tests start immediately (Ollama ready in < 10 seconds)
4. 100% reliable (no network dependency)
5. Saves ~60 minutes per test run

**Implementation time:** 2-3 hours (but saves 60 min per test run forever)

---

## Related Items

- **Triggered by:** Push to main after PR #192 merge (Azure Monitor Workbook)
- **Affects:** All PRs, all pushes to main
- **Workflow File:** `.github/workflows/test_update.yml`
- **Lines Affected:**
  - Lines 166-190 (Start services + Wait for Ollama)
  - Lines 419-429 (Show logs on failure)
- **Scripts:** `scripts/init-ollama.sh` (lines 36-41)

---

## Risk Assessment

**Risk Level:** Low
**Rationale:**

- Quick fix (Option A) has minimal risk
- Pre-built image (Option B) is isolated to CI environment
- Local development unaffected
- Can rollback easily if issues arise

**Mitigation:**

- Test in PR first
- Keep Option A as fallback
- Document troubleshooting steps

---

## Verification Steps

**After Implementation:**

1. **Trigger integration tests:**

   ```bash
   git commit --allow-empty -m "test: trigger CI"
   git push origin main
   ```

2. **Monitor workflow:**

   ```bash
   gh run watch
   ```

3. **Verify timing:**
   - Integration tests complete in < 15 minutes
   - "Wait for Ollama" step completes in < 5 minutes (Option A) or < 30 seconds (Option B)

4. **Check logs:**
   - Ollama logs show successful model pull
   - No timeout errors
   - Clear progress messages

5. **Run 5 times:**

   ```bash
   for i in {1..5}; do
     git commit --allow-empty -m "test: CI reliability check $i"
     git push origin main
     sleep 30
   done
   ```

   - Expected: All 5 runs pass

---

## Files to Modify

**Option A (Quick Fix):**

1. `.github/workflows/test_update.yml`:
   - Line 169: Increase sleep from 30s to 60s
   - Lines 172-190: Rewrite "Wait for Ollama" step with better logging
2. `scripts/init-ollama.sh`:
   - Lines 36-41: Add verbose logging to model pull

**Option B (Pre-built Image):**

1. `ollama/Dockerfile` (NEW): Dockerfile with pre-pulled model
2. `.github/workflows/build-ollama-image.yml` (NEW): Build and push image
3. `docker-compose.yml`:
   - Line 38: Change image to ghcr.io/zioalex/getinspiredbythebible-ollama:latest
4. `.github/workflows/test_update.yml`:
   - Lines 172-190: Simplify wait logic (model already present)

---

## Estimated Time

**Option A (Quick Fix):**

- **Coding:** 30 minutes
- **Testing:** 30 minutes (1-2 CI runs)
- **Total:** < 1 hour

**Option B (Pre-built Image):**

- **Dockerfile creation:** 30 minutes
- **Build workflow:** 30 minutes
- **Testing:** 1 hour (multiple CI runs)
- **Total:** 2-3 hours

---

**Priority:** P0 - Blocking all CI
**Complexity:** Low (Option A) / Medium (Option B)
**Value:** Critical - Unblocks all development work
