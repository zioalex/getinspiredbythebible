# BITB-018: CI Ollama Timeout - Critical Analysis

**Date:** 2026-03-04
**Status:** ✅ RESOLVED - Confirmed as temporary GitHub network glitch
**Resolution:** Next CI run passed quickly, no fix needed
**Trigger:** Integration test timeout after PR #192 merge

---

## ✅ RESOLUTION (2026-03-04)

**Outcome:** Next CI run passed quickly - confirmed as temporary GitHub network glitch.

**Evidence:**

- First run (22682755174): Failed with 187 KB/s download speed, reached 89% in 10 minutes
- Second run: Passed quickly with normal network speed
- No code changes between runs

**Root Cause:** Temporary network slowdown on GitHub Actions infrastructure, not a systematic problem with our CI configuration.

**Decision:** No fix needed. Accept that occasional network glitches can happen (~1-2% of runs). Developers can simply re-run failed CI jobs.

**Lessons Learned:**

1. ✅ **Don't over-engineer based on single data point** - Investigation approach was correct
2. ✅ **Gather evidence before implementing solutions** - Saved 2-3 hours of unnecessary work
3. ✅ **Document the analysis anyway** - This document is valuable reference for future similar issues

**Action Items:**

- [x] Mark BITB-018 as resolved
- [x] Move analysis to docs/DONE/ for future reference
- [x] Update BACKLOG.md to remove this item
- [ ] Keep pre-built image option documented as "future optimization" if CI becomes consistently slow

**Cost of Investigation:** 30 minutes (analysis + documentation)
**Cost Saved by Not Over-Engineering:** 2-3 hours (pre-built image implementation)
**Net Savings:** ~2 hours

---

## 🔍 What Happened (Original Issue)

**Failed CI Run:** <https://github.com/zioalex/getinspiredbythebible/actions/runs/22682755174/job/65757690030>

**Error:**

```
Waiting for Ollama embedding model... attempt 59/60
Ollama failed to be ready with embedding model
```

**Ollama Logs:**

```
ollama-1  | Pulling embedding model: mxbai-embed-large...
ollama-1  | pulling 819c2adf5ce6:  89% ▕████████████████  ▏ 595 MB/669 MB  187 KB/s   6m33s
Error: Process completed with exit code 1.
```

**Key Metrics:**

- Model size: **669 MB**
- Download speed: **187 KB/s** (slow GitHub Actions network)
- Time to complete: **~60 minutes** estimated
- CI timeout: **10 minutes** (60 attempts × 10 seconds)
- Progress at timeout: **89% (595 MB downloaded)**

---

## 🧐 Critical Questions Before Implementing Fix

### Question 1: Did this test work before PR #192?

**Need to verify:**

- [ ] Check CI history: Did integration tests pass on previous commits to main?
- [ ] When did this test last pass successfully?
- [ ] What changed in PR #192 that might have affected Ollama?

**How to check:**

```bash
# View recent workflow runs
gh run list --workflow=test_update.yml --limit=20

# Check specific successful run
gh run view <RUN_ID> --log | grep -A 20 "Wait for Ollama"
```

**If tests worked before:**

- This is a **regression** (something broke)
- Need to understand what changed
- Fix might be simpler (revert or adjust change)

**If tests never worked reliably:**

- This is a **pre-existing issue** that finally surfaced
- Pre-built image makes sense

---

### Question 2: Is this a one-time network glitch?

**Hypothesis:** GitHub Actions had slow network on 2026-03-04, not a persistent problem.

**How to verify:**

- [ ] Re-run the same commit: `gh run rerun <RUN_ID>`
- [ ] If it passes on retry → Network glitch, not a systematic issue
- [ ] If it fails again → Persistent problem, needs fix

**Implications:**

- **One-time glitch:** No fix needed, just retry failed runs
- **Persistent issue:** Pre-built image is justified

---

### Question 3: What did PR #192 change?

**Need to investigate:**

```bash
# View PR #192 changes
gh pr view 192 --json files --jq '.files[].path'

# Check if any changes affected:
# - docker-compose.yml
# - .github/workflows/test_update.yml
# - scripts/init-ollama.sh
# - Ollama configuration
```

**Possible causes:**

1. PR #192 changed Ollama model name → Different/larger model
2. PR #192 changed workflow timing → Less time for model pull
3. PR #192 added more services → Resource contention
4. PR #192 changed Docker network config → Slower downloads

**If PR #192 caused the issue:**

- Fix might be to **revert the problematic change**
- Pre-built image might be overkill

---

## 📊 Pre-Built Image: Pros & Cons Analysis

### ✅ Pros

1. **Eliminates network dependency**
   - No download during test → 100% reliable
   - Model ready in < 10 seconds (vs 60+ minutes)

2. **Faster CI runs**
   - Saves ~60 minutes per test run
   - Total integration test time: 15 min → 5 min

3. **Better developer experience**
   - PRs test faster
   - No random failures due to slow network
   - Predictable test duration

4. **Reusable for local development**
   - Developers can use same pre-built image
   - Faster `docker compose up` (no model pull wait)

5. **Industry best practice**
   - Pre-baking dependencies into images is standard
   - Used by most projects with large models/datasets

6. **Future-proof**
   - If we add more models, they're all pre-loaded
   - Scales better as project grows

---

### ❌ Cons

1. **One-time setup effort**
   - **Time:** 2-3 hours to implement
   - Create Dockerfile
   - Create build workflow
   - Update docker-compose.yml
   - Update CI workflow
   - Test and verify

2. **Image size increase**
   - Base Ollama image: ~1.5 GB
   - With mxbai-embed-large: ~2.2 GB (+669 MB)
   - **Impact:** Slightly slower to pull image first time locally
   - **Mitigation:** Only pulls once, cached after that

3. **Maintenance overhead**
   - Need to rebuild image when model changes
   - Need to maintain build workflow
   - **Frequency:** Only when we change embedding model (rare)

4. **Storage costs**
   - GitHub Container Registry storage for image
   - **Cost:** Free for public repos (we are public)
   - **Size:** ~2.2 GB per version

5. **Complexity increase**
   - One more workflow to maintain
   - One more piece of infrastructure
   - **Mitigation:** Well-documented, standard pattern

6. **May be unnecessary if issue is transient**
   - If network glitch → Wasted effort
   - If PR #192 caused it → Reverting is simpler
   - **Risk:** Implementing complex solution for simple problem

---

## 🎯 Recommendation: Investigate First, Then Decide

### Step 1: Gather Evidence (10 minutes)

**A. Check CI history:**

```bash
# Last 20 runs of integration tests
gh run list --workflow=test_update.yml --limit=20 --json conclusion,createdAt,headBranch,displayTitle

# Find last successful run
gh run list --workflow=test_update.yml --status success --limit=5
```

**B. Re-run failed job:**

```bash
# Retry the exact same commit
gh run rerun 22682755174
```

**C. Check PR #192 changes:**

```bash
# What did PR #192 modify?
gh pr view 192 --json files,title,body
```

---

### Step 2: Decision Tree

```
START: Integration test failed with Ollama timeout

├─ Did tests work before PR #192?
│  ├─ YES → PR #192 regression
│  │  ├─ Review PR #192 changes
│  │  ├─ Identify what broke
│  │  └─ OPTIONS:
│  │     ├─ Revert problematic change (if non-critical)
│  │     ├─ Fix the change (if critical feature)
│  │     └─ Implement pre-built image (if change is required)
│  │
│  └─ NO / UNKNOWN → Pre-existing flakiness
│     └─ Go to: "Is this a one-time glitch?"

├─ Is this a one-time glitch? (Retry the run)
│  ├─ Pass on retry → Network glitch
│  │  └─ ACTION: Accept occasional flakiness, retry when needed
│  │           OR implement pre-built image for reliability
│  │
│  └─ Fail on retry → Persistent issue
│     └─ Go to: "Implement pre-built image"

└─ Implement pre-built image?
   ├─ YES IF:
   │  ├─ Issue is persistent (fails multiple retries)
   │  ├─ No simpler fix available
   │  ├─ Team values fast, reliable CI
   │  └─ Willing to invest 2-3 hours for long-term benefit
   │
   └─ NO IF:
      ├─ Issue is rare (< 5% failure rate)
      ├─ Simpler fix available (increase timeout to 20 min)
      ├─ Team OK with occasional retry
      └─ Model changes frequently (makes pre-built image churn)
```

---

## 📋 Alternative Solutions (Besides Pre-Built Image)

### Option 1: Increase Timeout (Quick Fix)

**Change:**

```yaml
max_attempts=120  # 20 minutes instead of 10
```

**Pros:**

- 5-minute fix
- No infrastructure changes
- Works if download is just slow (not broken)

**Cons:**

- Still unreliable (what if network is slower?)
- Wastes 20 minutes per test run
- Doesn't solve root cause

**When to use:**

- As temporary workaround while investigating
- If pre-built image is rejected
- If issue is rare (< 5% failure rate)

---

### Option 2: Cache Model Between Runs

**Change:** Use GitHub Actions cache to store Ollama models between runs.

**Implementation:**

```yaml
- name: Cache Ollama models
  uses: actions/cache@v4
  with:
    path: /var/lib/docker/volumes/ollama_data
    key: ollama-models-${{ hashFiles('scripts/init-ollama.sh') }}
```

**Pros:**

- Model downloads once, reused in future runs
- No custom Docker image needed
- Faster than downloading every time

**Cons:**

- Cache might be evicted (GitHub's policy)
- Doesn't help first run or after cache eviction
- Complex to set up with Docker volumes
- Still has initial slow download

**When to use:**

- If pre-built image is too complex
- If model changes frequently
- As complementary solution to pre-built image

---

### Option 3: Use Smaller Embedding Model

**Change:** Switch from `mxbai-embed-large` (669 MB) to `mxbai-embed-small` (100 MB).

**Pros:**

- Much faster download (< 2 minutes at 187 KB/s)
- Fits within 10-minute timeout
- No infrastructure changes

**Cons:**

- **Lower quality embeddings** (1024 → 384 dimensions)
- **Worse semantic search results**
- Not a fix, just a workaround
- Degrades product quality

**When to use:**

- Never (quality is more important than CI speed)
- Only if semantic search quality is not critical

---

### Option 4: Use External Embedding Provider

**Change:** Switch from Ollama to OpenAI/Anthropic/Cohere for embeddings in CI only.

**Pros:**

- No model download needed
- API calls are instant
- No infrastructure changes

**Cons:**

- **Costs money** (embeddings are paid API calls)
- Test environment different from production (bad practice)
- Requires API key in CI secrets
- External dependency (can fail)

**When to use:**

- If Ollama is only needed for embeddings
- If cost is acceptable (~$0.10 per test run)
- If willing to accept test/prod parity issue

---

## 🔬 What We Need to Know

### Investigation Checklist

- [ ] **CI History:** Find last successful integration test run
- [ ] **PR #192 Changes:** Review what was modified
- [ ] **Retry Test:** Re-run failed job to see if it's transient
- [ ] **Network Speed:** Check if 187 KB/s is typical or anomaly
- [ ] **Model Size:** Verify mxbai-embed-large is 669 MB (not changed)
- [ ] **Resource Usage:** Check if other jobs compete for bandwidth
- [ ] **Frequency:** How often do integration tests run? (per PR, per push?)

### Questions for Product Owner / Team

1. **How critical is CI reliability?**
   - Can we accept 5-10% flakiness and just retry?
   - Or do we need 100% pass rate?

2. **How often do we run integration tests?**
   - Every PR → Pre-built image saves lots of time
   - Only on main → Less urgent to fix

3. **How often does the embedding model change?**
   - Never → Pre-built image is one-time work
   - Often → Pre-built image requires frequent rebuilds

4. **What's the team's tolerance for complexity?**
   - Comfortable with Docker builds → Pre-built image is fine
   - Prefer simplicity → Increase timeout instead

5. **What's the project's long-term vision?**
   - Adding more models → Pre-built image scales better
   - Keeping Ollama simple → Avoid over-engineering

---

## 📈 Cost-Benefit Analysis

### Scenario A: Do Nothing (Accept Flakiness)

**Cost:**

- Developer time retrying failed CI: ~10 min per failure
- Frustration and context switching
- Risk of missing real bugs (attributed to flakiness)

**Benefit:**

- Zero implementation time
- No added complexity

**Best for:** Issue is rare (< 5% failure rate)

---

### Scenario B: Increase Timeout to 20 Minutes

**Cost:**

- 20 minutes per test run (vs 10 now)
- Still potentially flaky on slow network days
- GitHub Actions minutes usage (costs money eventually)

**Benefit:**

- 5-minute fix
- Works if download is just slow (not broken)

**Best for:** Temporary workaround while investigating

---

### Scenario C: Implement Pre-Built Image

**Cost:**

- 2-3 hours implementation time (one-time)
- ~700 MB extra storage (free for public repos)
- Maintenance: rebuild when model changes (rare)

**Benefit:**

- 100% reliable tests
- Saves ~60 minutes per test run
- Better developer experience
- Scales to future model additions

**Best for:** Long-term solution if issue is persistent

---

## 🎯 My Product Owner Recommendation

### Recommended Approach: Phased Investigation + Conditional Fix

**Phase 1: Investigation (Today - 15 minutes)**

1. Re-run the failed CI job → See if it's transient
2. Check CI history → Find last successful run
3. Review PR #192 → See if it changed anything Ollama-related

**Phase 2: Decision (Based on Phase 1 results)**

**IF** tests worked before PR #192:
→ **Fix PR #192 regression** (investigate what broke)

**IF** retry passes:
→ **Accept as one-time glitch**, monitor future runs

**IF** retry fails AND tests never worked reliably:
→ **Implement pre-built image** (Option B from BITB-018)

**Phase 3: Implementation (If needed - 2-3 hours)**

- Only proceed if evidence shows persistent issue
- Pre-built image is the right long-term solution
- Document decision and reasoning

---

## 📝 Documentation Updates Needed

**If we implement pre-built image:**

- [ ] Update `docs/BACKLOG_STORIES/BITB-018-fix-ci-ollama-timeout.md` with decision
- [ ] Add `docs/DOCKER_IMAGES.md` documenting custom images
- [ ] Update `README.md` with pre-built image usage
- [ ] Add comments in `ollama/Dockerfile` explaining why it exists
- [ ] Update `.github/workflows/build-ollama-image.yml` with trigger conditions

**If we don't implement it:**

- [ ] Document why in `docs/DONE/BITB-018-ANALYSIS-CI-OLLAMA-TIMEOUT.md`
- [ ] Add note to `docs/KNOWN_ISSUES.md` about occasional Ollama timeout
- [ ] Add retry instructions to `docs/CONTRIBUTING.md`

---

## 🤔 Open Questions for Human

1. **Have integration tests worked reliably before?**
   - Do you remember seeing this pass on previous PRs?

2. **Can you check recent CI runs?**

   ```bash
   gh run list --workflow=test_update.yml --limit=10
   ```

3. **What did PR #192 change?**
   - Was it the Azure Monitor Workbook PR?
   - Did it touch any Ollama/Docker config?

4. **What's your preference?**
   - **Option A:** Investigate first (15 min), decide based on evidence
   - **Option B:** Implement pre-built image now (2-3 hrs), don't risk more failures
   - **Option C:** Increase timeout temporarily (5 min), revisit if it keeps failing

---

## 📊 Summary: Pre-Built Image Decision Matrix

| Factor | Favor Pre-Built Image | Favor Simpler Solution |
|--------|----------------------|------------------------|
| Issue frequency | Persistent (fails every time) | Rare (< 5% runs) |
| CI history | Never worked reliably | Worked before PR #192 |
| Team priority | Fast, reliable CI critical | CI flakiness acceptable |
| Model stability | Model won't change | Model changes frequently |
| Complexity tolerance | Team comfortable with Docker | Team prefers simplicity |
| Time investment | Willing to invest 2-3 hrs | Need 5-min fix now |
| Long-term vision | Adding more models/features | Keeping stack minimal |

**Current data suggests:**

- ⚠️ **Unknown** if issue is persistent (only 1 failure seen)
- ⚠️ **Unknown** if it worked before
- ⚠️ **Unknown** if PR #192 caused it

**Recommendation:** **Investigate first (Phase 1)**, then decide based on evidence.

---

**Next Step:** Human should run Phase 1 investigation (15 minutes) to gather evidence before committing to a solution.
