# BITB-017: Skip Terraform Apply When No Changes Detected

**Priority:** P2 (Medium)
**Status:** ✅ Done (has_changes == 'true' gate in azure-deploy.yml line 738)
**Size:** S (< 2 hours)
**Created:** 2026-03-04

---

## User Story

**As a** developer running CI/CD deployments,
**I want** Terraform apply to be skipped when there are no infrastructure changes,
**so that** we save time and avoid unnecessary Azure API calls.

---

## Problem Statement

**Current Behavior:**
When `terraform plan` detects no changes (exit code 0), the workflow still runs the `deploy` job and executes `terraform apply`. This wastes time and Azure API quota.

**Technical Issue:**

1. The `terraform plan` step uses `-detailed-exitcode`:
   - Exit code 0 = no changes
   - Exit code 1 = error
   - Exit code 2 = changes detected
2. The plan step stores the exit code but never uses it
3. The `deploy` job condition only checks `needs.tf-plan.result == 'success'`
4. **Missing logic:** Should also check if exit code was 2 (changes detected)

**Example Scenario:**

- User triggers `workflow_dispatch` with `skip_build=true` (just run migrations)
- No infrastructure files changed
- `terraform plan` returns exit code 0 (no changes)
- Deploy job still runs and executes `terraform apply -auto-approve`
- Terraform applies an empty plan (wasted time)

**Impact:**

- **User Experience:** Confusing — why is deploy running when nothing changed?
- **CI Time:** 2-3 minutes wasted on unnecessary apply
- **Azure API:** Unnecessary API calls to Azure Resource Manager
- **Risk:** Low (apply with no changes is safe, but wasteful)

---

## Functional Requirements

- [ ] Capture `terraform plan` exit code in plan job output
- [ ] Pass exit code to deploy job
- [ ] Deploy job checks if exit code == 2 (changes detected) before running
- [ ] If exit code == 0 (no changes), skip deploy job with clear message
- [ ] If exit code == 1 (error), fail the plan job (already handled by continue-on-error)
- [ ] Workflow summary shows "No changes - skipped apply" when appropriate

---

## Non-Functional Requirements

- **Clarity:** Users should understand why deploy was skipped
- **Performance:** Save 2-3 minutes on deployments with no changes
- **Safety:** Must not skip deploy when changes exist
- **Maintainability:** Logic should be clear and well-documented

---

## Acceptance Criteria

**Code Changes:**

1. **In `tf-plan` job:**
   - [ ] After the `Terraform Plan` step, add explicit exit code capture:

     ```yaml
     - name: Terraform Plan
       id: plan
       run: |
         terraform plan -detailed-exitcode ... | tee plan_output.txt
         PLAN_EXIT_CODE=$?
         echo "exit_code=$PLAN_EXIT_CODE" >> $GITHUB_OUTPUT
         exit $PLAN_EXIT_CODE
       continue-on-error: true
     ```

   - [ ] Add output to job:

     ```yaml
     tf-plan:
       outputs:
         has_changes: ${{ steps.plan.outputs.exit_code == '2' }}
         plan_exit_code: ${{ steps.plan.outputs.exit_code }}
     ```

2. **In `deploy` job:**
   - [ ] Update condition to check for changes:

     ```yaml
     deploy:
       needs: [changes, build-backend, build-frontend, tf-plan]
       if: >-
         always() &&
         github.event_name != 'pull_request' &&
         needs.tf-plan.result == 'success' &&
         needs.tf-plan.outputs.has_changes == 'true' &&
         (github.event_name == 'workflow_run' ||
          (github.event_name == 'workflow_dispatch' && inputs.action == 'deploy'))
     ```

3. **Add skip notification step:**
   - [ ] After `tf-plan` job, add summary step:

     ```yaml
     - name: Plan Result Summary
       if: always()
       run: |
         EXIT_CODE="${{ steps.plan.outputs.exit_code }}"
         if [ "$EXIT_CODE" == "0" ]; then
           echo "## ℹ️ No Infrastructure Changes Detected" >> $GITHUB_STEP_SUMMARY
           echo "" >> $GITHUB_STEP_SUMMARY
           echo "Terraform plan completed with no changes. Deploy job will be skipped." >> $GITHUB_STEP_SUMMARY
         elif [ "$EXIT_CODE" == "2" ]; then
           echo "## 📝 Infrastructure Changes Detected" >> $GITHUB_STEP_SUMMARY
           echo "" >> $GITHUB_STEP_SUMMARY
           echo "Terraform plan detected changes. Deploy job will execute." >> $GITHUB_STEP_SUMMARY
         elif [ "$EXIT_CODE" == "1" ]; then
           echo "## ❌ Terraform Plan Failed" >> $GITHUB_STEP_SUMMARY
           echo "" >> $GITHUB_STEP_SUMMARY
           echo "See plan output for error details." >> $GITHUB_STEP_SUMMARY
         fi
     ```

**Testing:**

- [ ] **Test Case 1:** Push with no changes
  - Trigger workflow with `skip_build=true`, no tfvars changes
  - Expected: Plan runs, exit code 0, deploy skipped
  - Verify: Workflow summary shows "No changes - skipped apply"

- [ ] **Test Case 2:** Push with infrastructure changes
  - Modify `terraform.tfvars` (e.g., change backend replica count)
  - Expected: Plan runs, exit code 2, deploy runs
  - Verify: Apply executes and changes are deployed

- [ ] **Test Case 3:** Plan fails
  - Introduce syntax error in Terraform file
  - Expected: Plan runs, exit code 1, deploy skipped
  - Verify: Workflow fails at plan step

**Documentation:**

- [ ] Add comment in workflow explaining exit code logic
- [ ] Update `DEPLOYMENT.md` if it exists to document this behavior

---

## Tech Constraints

- Must preserve `continue-on-error: true` on plan step (needed to capture exit code)
- Must not break existing deployment workflows
- Must work with GitHub Actions conditional syntax
- Output values must be strings (GitHub Actions limitation)

---

## Out of Scope

- Automatic rollback when apply fails (separate story)
- Plan diffs in PR comments (already exists)
- Multiple Terraform workspaces/environments (future enhancement)
- Cost estimation for planned changes (future enhancement)

---

## Implementation Details

### Current Flow (Buggy)

```
tf-plan job:
  → terraform plan -detailed-exitcode (exit code 0, 1, or 2)
  → continue-on-error: true (captures all exit codes)
  → Upload plan artifact

deploy job:
  if: needs.tf-plan.result == 'success'  ← BUG: runs even with exit code 0
  → terraform apply tfplan
```

### Fixed Flow

```
tf-plan job:
  → terraform plan -detailed-exitcode
  → Capture exit code in output: has_changes=${{ exit_code == 2 }}
  → Upload plan artifact

deploy job:
  if: needs.tf-plan.result == 'success' && needs.tf-plan.outputs.has_changes == 'true'
  → terraform apply tfplan (only runs if exit code was 2)
```

### Exit Code Reference

```
0 = No changes needed (SUCCESS + skip apply)
1 = Error in plan (FAILURE)
2 = Changes detected (SUCCESS + run apply)
```

---

## Example Scenarios

### Scenario A: Migration-Only Deploy (No Infra Changes)

**Command:**

```bash
gh workflow run azure-deploy.yml --ref main \
  -f action=deploy \
  -f skip_build=true \
  -f skip_database_seed=true
```

**Expected Behavior (After Fix):**

1. `tf-plan` runs, detects no changes, exit code 0 ✅
2. `deploy` job **skipped** (saves 2-3 minutes) ✅
3. `run-migrations` job runs (migrations executed) ✅
4. Workflow summary: "No infrastructure changes - deploy skipped"

**Current Behavior (Bug):**

1. `tf-plan` runs, detects no changes, exit code 0
2. `deploy` job **runs anyway** (wastes time) ❌
3. `terraform apply` runs with empty plan
4. `run-migrations` job runs

---

### Scenario B: Infrastructure Change Deploy

**Change:** Bump backend replica count in `terraform.tfvars`

**Expected Behavior (Should Work Before & After Fix):**

1. `tf-plan` runs, detects changes, exit code 2 ✅
2. `deploy` job runs ✅
3. `terraform apply` updates replica count ✅
4. Workflow summary: "Infrastructure changes applied"

---

## Related Items

- **Discovered by:** Human (workflow observation)
- **Related:** BITB-014 (migration pipeline fix — similar job condition logic)
- **Workflow File:** `.github/workflows/azure-deploy.yml`
- **Lines Affected:**
  - Line ~537-549 (terraform plan step)
  - Line ~410-430 (tf-plan job outputs — new)
  - Line ~623-630 (deploy job condition — update)

---

## Risk Assessment

**Risk Level:** Low
**Rationale:**

- Small, surgical change (add output + update condition)
- Only affects when deploy job runs (not what it does)
- Terraform still validates plan before apply
- Easy to test without affecting production

**Mitigation:**

- Test in PR first (workflow_dispatch on feature branch)
- Verify with both "no changes" and "has changes" scenarios
- Can revert easily if issues arise

---

## Benefits

### Performance

- **Save 2-3 minutes per no-change deployment**
- Typical migration-only deploy: 10 min → 7 min

### Clarity

- **Users understand why deploy was skipped**
- Workflow summary explicitly states "no changes detected"

### Resource Efficiency

- **Fewer Azure API calls**
- Reduces load on Azure Resource Manager

### Developer Experience

- **Less confusion about why apply is running**
- Clearer workflow intent

---

## Verification Steps

**After Implementation:**

1. **Test no-changes scenario:**

   ```bash
   # Trigger deploy with no changes
   gh workflow run azure-deploy.yml --ref main \
     -f action=deploy \
     -f skip_build=true

   # Verify deploy job was skipped
   gh run view --log | grep -A 5 "deploy"
   # Expected: "Job was skipped"
   ```

2. **Test has-changes scenario:**

   ```bash
   # Modify terraform.tfvars, commit, push
   echo 'backend_min_replicas = 2' >> deployment/terraform.tfvars
   git commit -am "test: change replica count"
   git push

   # Verify deploy job ran
   gh run view --log | grep "Terraform Apply"
   # Expected: "terraform apply -auto-approve tfplan"
   ```

3. **Check workflow summary:**
   - Go to Actions tab
   - View workflow run
   - Check summary page
   - Expected: Clear message about whether changes were detected

---

## Alternatives Considered

### Alternative 1: Always run apply (current behavior)

**Pros:** Simple, no logic changes
**Cons:** Wastes time, confusing, inefficient
**Decision:** ❌ Rejected — user reported as bug

### Alternative 2: Check exit code in deploy step (not job condition)

**Pros:** Deploy job runs, first step checks and exits early
**Cons:** Job still queues, allocates runner, adds latency
**Decision:** ❌ Rejected — job-level condition is cleaner

### Alternative 3: Use workflow outputs instead of job outputs (Recommended)

**Pros:** Cleaner, job-level skip
**Cons:** None
**Decision:** ✅ **Selected** — this is the implementation

---

## Files to Modify

1. `.github/workflows/azure-deploy.yml`:
   - `tf-plan` job: Add outputs section
   - `tf-plan` job: Capture exit code in plan step
   - `tf-plan` job: Add summary step
   - `deploy` job: Update condition to check `has_changes`

---

## Estimated Time

- **Coding:** 30 minutes (add outputs, update condition)
- **Testing:** 30 minutes (test both scenarios)
- **Documentation:** 15 minutes (add comments)
- **Total:** < 2 hours

---

**Priority:** P2 - Nice to have, improves DX and efficiency
**Complexity:** Low - Small workflow change
**Value:** Medium - Saves time, improves clarity
