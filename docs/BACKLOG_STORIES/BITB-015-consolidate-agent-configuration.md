# BITB-015: Consolidate Agent Configuration

**Priority:** P1 (High)
**Status:** 🎯 Todo
**Size:** S (< 3 hours)
**Created:** 2026-03-04

---

## User Story

**As a** product owner and team member,
**I want** agent configurations to follow best practices with clear separation of concerns,
**so that** agents have consistent instructions and don't duplicate configuration across files.

---

## Problem Statement

**Current Issues:**

1. **Duplicate Instructions:** `CLAUDE.md` contains agent instructions that should be in `opencode.json`
2. **Configuration Duplication:** Both `~/.config/opencode/opencode.json` (global) and `./opencode.json` (project) contain identical agent definitions
3. **Unclear Boundaries:** Product-owner agent sometimes attempts to make code changes instead of delegating
4. **Non-Standard Setup:** `CLAUDE.md` is not part of OpenCode's standard configuration pattern

**Root Cause:**

- Configuration evolved organically without following OpenCode best practices
- Global config was used as a testing ground, then duplicated to project config
- Agent prompts lack explicit "DO NOT CODE" guardrails

**Impact:**

- **Maintenance burden:** Changes must be made in multiple places
- **Risk of divergence:** Global and project configs can drift out of sync
- **Role confusion:** Product-owner might bypass delegation protocol

---

## Functional Requirements

**Agent Configuration:**

- [ ] Product-owner agent prompt moved entirely to `./opencode.json`
- [ ] Product-owner prompt includes "=== CRITICAL RULE: YOU ARE NOT AN ENGINEER ===" section
- [ ] Product-owner prompt includes "=== DELEGATION PROTOCOL (MANDATORY) ===" with concrete examples
- [ ] Product-owner prompt includes "=== PROGRESS MONITORING (MANDATORY) ===" (30-min check-ins)
- [ ] Product-owner prompt includes "=== PROJECT-SPECIFIC KNOWLEDGE ===" section
- [ ] Agent prompt emphasizes: EMBED full user stories when delegating (don't reference external files)

**File Cleanup:**

- [ ] `CLAUDE.md` deleted (functionality moved to opencode.json)
- [ ] `~/.config/opencode/opencode.json` (global config) cleaned up:
  - Remove all agent definitions
  - Keep ONLY provider configuration (Ollama, model settings)
  - Reduce file size (93 lines → ~20 lines)

**Configuration Architecture:**

- [ ] Project config (`./opencode.json`) = single source of truth for agents (committed to Git)
- [ ] Global config (`~/.config/opencode/opencode.json`) = user-wide provider/model preferences (NOT in Git)
- [ ] No duplication between global and project configs

---

## Non-Functional Requirements

- **Clarity:** Agent roles and boundaries must be explicit and unambiguous
- **Maintainability:** Configuration in one place (project config), committed to Git
- **Team Consistency:** All team members use same agent definitions from project repo
- **Documentation:** Inline comments explain configuration decisions

---

## Acceptance Criteria

**Code Changes:**

- [ ] `./opencode.json` updated with enhanced product-owner agent prompt:
  - "YOU ARE NOT AN ENGINEER" section added
  - Delegation protocol with concrete example
  - Progress monitoring rules (30-min check-ins)
  - Project-specific context (Turnstile status, Android SDK, open PRs)
  - Emphasis on embedding full user stories in delegation prompts
- [ ] `CLAUDE.md` deleted
- [ ] `~/.config/opencode/opencode.json` cleaned up (local change, not in Git):
  - All agent definitions removed
  - Only provider/model config remains
  - File size reduced significantly

**Testing:**

- [ ] Pre-commit checks pass (validate JSON syntax)
- [ ] Product-owner agent loads correctly from `./opencode.json`
- [ ] Verify agent follows delegation protocol (doesn't make code changes)
- [ ] Verify agent embeds full user stories when delegating

**Documentation:**

- [ ] Tracking doc: `docs/WIP/PR226-consolidate-agent-config.md`
- [ ] Comments in `opencode.json` explain configuration structure
- [ ] README or docs mention project config is source of truth

---

## Tech Constraints

- **OpenCode Config Precedence:** Project config (`./opencode.json`) has highest precedence
- **Git Tracking:** Project config is committed; global config is NOT committed
- **JSON Validity:** All changes must maintain valid JSON syntax
- **Backward Compatibility:** Changes must not break existing agent functionality

---

## Out of Scope

- Creating new agent types (only modifying existing product-owner agent)
- Reorganizing other agents (orchestrator, engineer, etc.)
- Changing provider/model configuration (only moving config location)
- Adding new OpenCode features or plugins

---

## Implementation Plan

### Phase 1: Enhance Project Config

1. Edit `./opencode.json`
2. Expand product-owner agent prompt with critical rules
3. Add delegation protocol section with examples
4. Add progress monitoring requirements
5. Add project-specific knowledge section

### Phase 2: Clean Up Global Config

1. Edit `~/.config/opencode/opencode.json` (local file)
2. Remove all agent definitions (93 lines → 22 lines)
3. Keep only provider configuration (Ollama + qwen models)

### Phase 3: Remove Duplicate File

1. Delete `CLAUDE.md`
2. Verify functionality moved to opencode.json

### Phase 4: Testing

1. Run pre-commit checks
2. Test product-owner agent behavior
3. Verify delegation protocol works correctly

---

## Verification Steps

**Before:**

```bash
# Check current state
wc -l CLAUDE.md  # Should show ~100 lines
wc -l ~/.config/opencode/opencode.json  # Should show ~93 lines
grep -c "agent" ~/.config/opencode/opencode.json  # Should show multiple matches
```

**After:**

```bash
# Verify changes
ls CLAUDE.md  # Should NOT exist
wc -l ~/.config/opencode/opencode.json  # Should show ~20 lines
grep -c "agent" ~/.config/opencode/opencode.json  # Should show 0 matches
jq '.agents["product-owner"]' ./opencode.json | wc -l  # Should show enhanced prompt
```

---

## Expected Benefits

1. **Single Source of Truth:** All agents defined in project config (committed to Git)
2. **Team Alignment:** Everyone uses same agent definitions
3. **Clearer Boundaries:** Product-owner knows NOT to make code changes
4. **Better Delegation:** Full user stories embedded in delegation prompts (prevents file access issues)
5. **Easier Maintenance:** Update one file instead of three
6. **Follows Best Practices:** Aligns with OpenCode's recommended configuration pattern

---

## Related Items

- **Related Work:** Investigation into OpenCode config precedence (completed)
- **Configuration Files:**
  - `./opencode.json` (project config - modified)
  - `~/.config/opencode/opencode.json` (global config - cleaned up)
  - `CLAUDE.md` (to be deleted)

---

## Risk Assessment

**Risk Level:** Low
**Rationale:**

- No code changes (only configuration)
- Changes are reversible (Git history + manual undo for global config)
- Agent behavior improves (clearer instructions)
- No user-facing impact

**Mitigation:**

- Test agent behavior before committing
- Keep backup of global config before cleanup
- Verify JSON syntax with pre-commit hooks
- Validate agent loads correctly after changes

---

## Branch & PR Details

**Branch:** `refactor/consolidate-agent-config`
**PR:** #226 (to be created)

**Files Modified:**

- `./opencode.json` (enhanced product-owner agent prompt)
- `CLAUDE.md` (deleted)
- `~/.config/opencode/opencode.json` (local cleanup, not in PR)
