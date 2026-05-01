# Product Owner - Git Worktree Directive

**Added:** 2026-02-24

## Directive: Use Git Worktrees for Parallel PR Work

When working on multiple PRs in parallel as Product Owner:

### Use Git Worktrees

- Create a separate worktree for each PR/feature branch
- Keep PRs simple and focused on a single change
- Work in worktrees to avoid branch-switching conflicts

### Workflow

1. **Create worktree from main:**

   ```bash
   git worktree add -b fix/description .claude/worktrees/fix-description main
   ```

2. **Work in the worktree:**
   - Make focused, single-purpose changes
   - Commit with clear, conventional commit messages
   - Run pre-commit hooks before pushing

3. **Create PR from worktree:**
   - Push branch from worktree
   - Create PR with clear title and description
   - Reference issue/bug report in PR body

4. **Clean up after merge:**

   ```bash
   git worktree remove .claude/worktrees/fix-description
   git branch -d fix/description
   ```

### Benefits

- No need to stash/unstash changes
- Can work on multiple PRs simultaneously
- Cleaner git history
- Avoids accidental commits to wrong branch

### Worktree Location

- Standard location: `.claude/worktrees/<branch-name>/`
- This directory is gitignored
- Each worktree is a separate working directory

### When NOT to Use Worktrees

- Single sequential PR (just work in main tree)
- Branch is already checked out in main tree
- Very quick fixes (< 5 minute changes)
